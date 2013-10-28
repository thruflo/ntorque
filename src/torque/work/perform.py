# -*- coding: utf-8 -*-

"""Provides ``TaskPerformer``, a utility that aquires a task from the db,
  and performs it by making a POST request to the task's web hook url.
"""

__all__ = [
    'TaskPerformer',
]

import logging
logger = logging.getLogger(__name__)

import gevent
import requests

from torque import backoff
from torque import model

class TaskPerformer(object):
    def __init__(self, **kwargs):
        self.task_manager = kwargs.get('acquire_task', model.TaskManager())
        self.backoff_cls = kwargs.get('backoff', backoff.Backoff)
        self.post = kwargs.get('post', requests.post)
        self.sleep = kwargs.get('spawn', gevent.sleep)
        self.spawn = kwargs.get('spawn', gevent.spawn)
    
    def __call__(self, instruction, control_flag):
        """Parse the instruction to transactionally get-and-incr the task."""
        
        # Parse the instruction to transactionally get-and-incr the task.
        task_id, retry_count = map(int, instruction.split(':'))
        task_data = self.task_manager.acquire(task_id, retry_count)
        
        # Unpack the task data.
        url = task_data['url']
        body = task_data['body']
        timeout = task_data['timeout']
        headers = {'content-type': '{0}; charset={1}'.format(
                task_data['enctype'], task_data['charset'])}
        
        # Spawn a POST to the web hook in a greenlet -- so we can monitor
        # the control flag in case we want to exit whilst waiting.
        kwargs = dict(data=body, headers=headers, timeout=timeout)
        greenlet = self.spawn(self.post, url, **kwargs)
        
        # Wait for the request to complete, checking the greenlet's progress
        # increasingly less frequently.
        response = None
        delay = 0.1 # secs
        max_delay = 5 # secs
        backoff = self.backoff_cls(start_delay, max_value=max_delay)
        while control_flag.is_set():
            self.sleep(delay)
            if greenlet.ready():
                response = greenlet.value
                break
            delay = backoff.exponential(1.5) # 0.15, 0.225, 0.3375, 0.50625 ... 5
        
        # If we didn't get a response, or if the response was not successful,
        # exit gracefully, leaving the task to be retried in due course.
        if response is None or response.status_code > 200:
            current_retry_count = task_data['retry_count']
            self.task_manager.reschedule(task_id, current_retry_count)
        else: # Flag the task as complete.
            self.task_manager.complete(task_id)
    


"""
  
  * get and set `in_progress` and `due` and incr retry count transactionally
    ^ this means that if the handler goes awol, we can know when to retry
    ^^ due is the max timeout + the backoff alg time for a timeout error
  * if not 200, use backoff algs to set status and due
  * if 200, set status
  
  XXX need mechanism to ensure a task can never be missed, e.g.: dropped
  between the task_id coming off redis and the due date being set.
  
  This means that when the task is first stored, it needs a status and
  due date that mean it will be retried. Question then is how do we
  minimise duplicate execution?
  
  Ideas:
  
  * fundamentally, for us, the db is the truth
  * pushing immediately to redis is an optimisation
  * we can't say how quickly a task_id pushed onto the queue will come off it
  * we can use BRPOPLPUSH to maintain an `in_progress` list: so we know
    when a task has come off the queue
  * however, this is not transactional with the db
  * an error between redis bpop and tx getset db would be very very rare
  
  So, what would be the model to store a task, so that it will be picked up
  if the handler falls over?
  
  -> save the task with a future due date
  -> immediately notify via redis
  -> normally, the task id is picked up and the tx-get-set can shift the due
     date into the future again
  -> in error cases, the due date stands
  -> the background requeue process picks up the task and adds the id to the
     queue again
  -> the task is retried
  
  Key points:
  
  - the tx-get-set means its impossible to perform a task without setting its
    due date past the timeout + execution margin
  - the performer can get a task no matter what the due date
  - the requeue process ignores until due
  
  So far so good but:
  
  - we need a mechanism to invalidate previously enqueued taskids at the
    tx-get-set moment
  - this is fine, as we can enqueue `taskid:something` where something can
    be used to make the get part of the tx-get-set miss
  - this could be the retry count
  
  I.e.:
  
  - `task1234` comes along, is stored with retry_count=0 
  - either the immediate notifier or the background retrier adds `task1234:0`
    to the queue
  - a worker picks up this instruction and get-sets `task(id=1234, retry_count=0)`
  - this sets retry_count to 1
  - if, somehow, the task had been on the redis queue for so long that it was
    re-enqueued, subsequent `task1234:0`s would be ignored
  
  
"""

