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
        self.sleep = kwargs.get('sleep', gevent.sleep)
        self.spawn = kwargs.get('spawn', gevent.spawn)
    
    def __call__(self, instruction, control_flag):
        """Parse the instruction to transactionally get-and-incr the task."""
        
        # Parse the instruction to transactionally get-and-incr the task.
        task_id, retry_count = map(int, instruction.split(':'))
        task_data = self.task_manager.acquire(task_id, retry_count)
        if not task_data:
            return
        
        # Unpack the task data.
        url = task_data['url']
        body = task_data['body']
        timeout = task_data['timeout']
        headers = task_data['headers']
        headers['content-type'] = '{0}; charset={1}'.format(
                task_data['enctype'], task_data['charset'])
        
        # Spawn a POST to the web hook in a greenlet -- so we can monitor
        # the control flag in case we want to exit whilst waiting.
        kwargs = dict(data=body, headers=headers, timeout=timeout)
        greenlet = self.spawn(self.post, url, **kwargs)
        
        # Wait for the request to complete, checking the greenlet's progress
        # increasingly less frequently.
        response = None
        delay = 0.1 # secs
        max_delay = 2 # secs
        backoff = self.backoff_cls(delay, max_value=max_delay)
        while control_flag.is_set():
            self.sleep(delay)
            if greenlet.ready():
                response = greenlet.value
                break
            delay = backoff.exponential(1.5) # 0.15, 0.225, 0.3375, 0.50625 ... 5
        
        # If we didn't get a response, or if the response was not successful,
        # exit gracefully, leaving the task to be retried in due course.
        if response is None or response.status_code > 499:
            # Note that rescheduling *accelerates* the due date -- doing nothing
            # here would leave the task to be retried at the same delay, plus
            # the timeout.
            # XXX what we could also do here are:
            # - set a more informative status flag (even if only descriptive)
            # - noop if the greenlet request timed out
            status = self.task_manager.reschedule()
        elif response.status_code > 201:
            status = self.task_manager.fail()
        else:
            status = self.task_manager.complete()
        return status
    

