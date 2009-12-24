#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Provides helper methods for adding tasks to and fetching
  tasks from a redis backed queue.
  
  Trivial thanks to http://code.google.com/p/redis/wiki/SortedSets
"""

import time

import redis as redis
r = redis.Redis()

try:
    import json
except ImportError:
    import simplejson as json

from config import options
from utils import normalise_url

class Task(object):
    """A task consists of a ``url`` to post some ``params`` to::
      
          >>> task = Task(url='/hooks/foo', params={'a': 1})
      
      Add it to the queue::
      
          >>> task.add()
      
      You can schedule the task to be executed *after* a number of
      seconds in the future::
      
          >>> task.add(delay=2)
      
      And you can specify which queue to stick it in::
      
          >>> task.add(queue_name='foo')
      
    """
    
    def __init__(self, url, params={}, queue_name=options.queue_name):
        self.doc = {
            'url': normalise_url(url), 
            'params': params
        }
        self.queue_name = queue_name
    
    
    def add(self, queue_name=None, delay=0):
        """Adds a task to the queue.
          
          See http://code.google.com/p/redis/wiki/ZaddCommand
          
          @@ because this is a sorted set, if the task is a
          duplicate, it has its timestamp updated.  This may
          or may not be quite what we want task-delay wise
          but it certainly helps minimise processing.
        """
        
        task_string = json.dumps(self.doc)
        ts = time.time() + delay
        queue_name = queue_name and queue_name or self.queue_name
        return r.zadd(queue_name, task_string, ts)
    
    def remove(self, queue_name=None):
        """http://code.google.com/p/redis/wiki/ZremCommand
        """
        
        task_string = json.dumps(self.doc)
        queue_name = queue_name and queue_name or self.queue_name
        return r.zrem(queue_name, task_string)
    
    
    def __repr__(self):
        return u'<torque.client.Task queue=%s, url=%s, params=%s>' % (
            self.queue_name,
            self.doc['url'],
            self.doc['params']
        )
    


def _ensure_task_string(what):
    if isinstance(what, Task):
        return json.dumps(what.doc)
    elif isinstance(what, dict):
        return json.dumps(what)
    else: # isinstance(task, basestring)
        return what
    


def add(url, params, delay=0, queue_name=options.queue_name):
    t = Task(url=url, params=params, queue_name=queue_name)
    return t.add(delay=delay)

def update(task, delay=0, queue_name=options.queue_name):
    task_string = _ensure_task_string(task)
    ts = time.time() + delay
    return r.zadd(queue_name, task_string, ts)

def remove(task_string, queue_name=options.queue_name):
    task_string = _ensure_task_string(task)
    return r.zrem(queue_name, task_string)


def fetch(
        ts=None, 
        delay=0, 
        decode=True, 
        limit=options.max_concurrent_tasks, 
        queue_name=options.queue_name
    ):
    """Gets upto ``limit`` tasks from the queue, in timestamp order.
      
      If ``decode`` is true, returns the tasks as dicts.
      
      See http://code.google.com/p/redis/wiki/ZrangebyscoreCommand
    """
    
    if ts is None and delay == 0:
        ts = time.time()
    elif ts is None:
        ts = time.time() + delay
    if limit is None:
        limit = 'inf'
    results = r.send_command(
        'ZRANGEBYSCORE %s 0 %s LIMIT 0 %s\r\n' % (
            queue_name,
            ts,
            limit
        )
    )
    if not decode:
        return results
    return [json.loads(item) for item in results]


def get_and_increment_error_count(task_string):
    task_string = _ensure_task_string(task_string)
    error_key = u'%s_error_count'
    if r.exists(error_key):
        error_count = int(r.get(error_key))
    else:
        error_count = 0
    error_count += 1
    r.set(error_key, str(error_count))
    r.expire(error_key, 172800)
    return error_count


