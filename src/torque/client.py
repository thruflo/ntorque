#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Provides methods for adding and fetching tasks
  to and from a redis backed queue.
  
  The data is persisted using a `redis sorted set
  <http://code.google.com/p/redis/wiki/SortedSets>`_
"""

import hashlib
import logging
import time

try:
    import json
except ImportError:
    import simplejson as json

from tornado.options import options

import config
from utils import normalise_url

from redis import Redis
r = Redis()

_KEY_PREFIX = u'thruflo.torque.'
def _get_redis_key(s):
    """Adds ``KEY_PREFIX`` to the start of all redis keys, to lower
      the risk of a namespace collision.
    """
    return u'%s%s' % (_KEY_PREFIX, s)


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
    
    def __init__(self, url, params={}):
        self.doc = {
            'url': normalise_url(url), 
            'params': params
        }
    
    
    @property
    def url(self):
        return self.doc['url']
    
    @property
    def params(self):
        return self.doc['params']
    
    
    @property
    def id(self):
        task_string = json.dumps(self.doc)
        return hashlib.sha1(task_string).hexdigest()
    
    
    def add(self, queue_name=options.queue_name, delay=0):
        """Adds a task to the queue.
          
          See http://code.google.com/p/redis/wiki/ZaddCommand
          
          @@ because this is a sorted set, if the task is a
          duplicate, it has its timestamp updated.  This means:
          
          #. feature: that we can just re-add a task to amend it's ts
          #. bug: that if a task is duplicated, e.g.: by different
             processes adding it for two different reasons, the 
             execution will be delayed until after the latter ts
          
          This second consequence means that, in some cases, a task
          may be constantly delayed for ever through re-adding.
        """
        
        task_string = json.dumps(self.doc)
        ts = time.time() + delay
        return r.zadd(_get_redis_key(queue_name), task_string, ts)
    
    def remove(self, queue_name=options.queue_name):
        """http://code.google.com/p/redis/wiki/ZremCommand
        """
        
        task_string = json.dumps(self.doc)
        return r.zrem(_get_redis_key(queue_name), task_string)
    
    
    def get_and_increment_error_count(self):
        error_key = _get_redis_key(u'%s_error_count' % self.id)
        error_count = r.exists(error_key) and int(r.get(error_key)) or 0
        error_count += 1
        r.set(error_key, str(error_count))
        r.expire(error_key, 86400)
        return error_count
    
    
    def __repr__(self):
        return u'<torque.client.Task url=%s, params=%s>' % (
            self.doc['url'],
            self.doc['params']
        )
    
    


def add_task(url, params={}, queue_name=options.queue_name, delay=0):
    t = Task(url, params=params)
    return t.add(queue_name=queue_name, delay=delay)


def fetch_tasks(
        ts=None, 
        delay=0, 
        limit=options.max_tasks,
        queue_name=options.queue_name
    ):
    """Gets upto ``limit`` tasks from the queue, in timestamp order.
      
      See http://code.google.com/p/redis/wiki/ZrangebyscoreCommand
    """
    
    if ts is None and delay == 0:
        ts = time.time()
    elif ts is None:
        ts = time.time() + delay
    results = r.send_command(
        'ZRANGEBYSCORE %s 0 %s LIMIT 0 %s\r\n' % (
            _get_redis_key(queue_name),
            ts,
            limit
        )
    )
    return [Task(**eval(item)) for item in results]


def clear_queue(queue_name=options.queue_name):
    r.delete(_get_redis_key(queue_name))


def create_n_tasks(n, url, params={}):
    i = n
    while i > 0:
        params.update({'i': i})
        add_task(url, params=params)
        i -= 1
    

