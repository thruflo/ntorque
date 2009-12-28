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

import re
starts_with_some_text_a_colon_and_two_fwd_slashes = re.compile(r'^[a-zA-Z]+:\/\/')

from redis import Redis
r = Redis()

from tornado.escape import json_decode, json_encode
from tornado.options import define, options

define(
    'base_task_url', default='http://localhost:8888', 
    help='stub to expand relative task urls with'
)
define(
    'queue_name', default='default_taskqueue', 
    help='which queue are we processing?'
)
define(
    'limit', default=10, type=int,
    help='how many tasks do you want to process concurrently?'
)

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
      
      A task, once added, is actually persisted in redis via three
      entries:
      
      #. the task_string is stored against the id
      #. an error count is stored against id_errors
      #. the id is stored in a sorted set, scored (i.e.: sorted) by timestamp
    """
    
    def __init__(self, url, params={}, queue_name=None):
        queue_name = queue_name and queue_name or options.queue_name
        self._task = {
            'url': self._normalise_url(url),
            'params': params
        }
        self._task_string = json_encode(self._task)
        self._id = hashlib.sha224(self._task_string).hexdigest()
        self._qk = _get_redis_key(queue_name)
        self._k = u'%s.%s' % (self._qk, self._id)
        self._ek = u'%s.errors' % self._k
        
    
    
    def _normalise_url(self, url, base_task_url=None):
        if starts_with_some_text_a_colon_and_two_fwd_slashes.match(url):
            return url
        base_task_url = base_task_url and base_task_url or options.base_task_url
        url = url.startswith('/') and url or unicode(u'/' + url)
        return u'%s%s' % (base_task_url, url)
        
    
    
    @property
    def id(self):
        return self._id
        
    
    @property
    def url(self):
        return self._task['url']
        
    
    @property
    def params(self):
        return self._task['params']
        
    
    
    def add(self, delay=0):
        """Adds a task to the queue.
          
          See http://code.google.com/p/redis/wiki/ZaddCommand
          
          @@ because this is a sorted set, if the task is a
          duplicate, it has its timestamp updated.  This means:
          
          #. feature: that we can just re-add a task to amend it's ts
          #. bug: that if a task is duplicated, e.g.: by different
             processes adding it for two different reasons, the 
             execution will be delayed until after the latter ts
          
          This second consequence means that, in an extreme case, a 
          task may be constantly delayed for ever through re-adding.
        """
        
        # if the task_string isn't stored, store it
        k = self._k
        if not r.exists(k):
            r.set(k, self._task_string)
        
        # add to or update the entry in the queue
        ts = time.time() + delay
        return r.zadd(self._qk, self._id, ts)
        
    
    def remove(self):
        """Delete_ the task_string and error count and remove_ the id 
          from the sorted set.
          
          .. _Delete: http://code.google.com/p/redis/wiki/DelCommand
          .. _remove: http://code.google.com/p/redis/wiki/ZremCommand
        """
        
        # delete the task_string & error count
        r.delete(self._k)
        r.delete(self._ek)
        
        # remove the task
        return r.zrem(self._qk, self._id)
        
    
    def get_and_increment_error_count(self):
        """Increment_ and return the error count.
          
          .. _Increment: http://code.google.com/p/redis/wiki/IncrCommand
        """
        
        return r.incr(self._ek)
        
    
    
    def __repr__(self):
        return u'<torque.client.Task %s %s>' % (self._id, self._task['url'])
    
    


def add_task(url, params={}, queue_name=None, delay=0):
    """Shortcut function to create and add a task.
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    
    t = Task(url, params=params, queue_name=queue_name)
    return t.add(delay=delay)
    

def get_task(task_id, queue_name=None):
    """Returns a ``Task`` instance corresponding to the ``task_id``.
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    qk = _get_redis_key(queue_name)
    k = u'%s.%s' % (qk, task_id)
    
    # get the task_string corresponding to the task_id provided
    task_string = r.get(k)
    
    # decode into a python dict
    data = json_decode(task_string)
    
    # return a Task using the data
    return Task(data['url'], params=data['params'], queue_name=queue_name)
    

def fetch_tasks(ts=None, delay=0, limit=None, queue_name=None):
    """Gets upto ``limit`` tasks from the queue, in timestamp order,
      using the ZRANGEBYSCORE_ command.
      
      .. _ZRANGEBYSCORE: http://code.google.com/p/redis/wiki/ZrangebyscoreCommand
    """
    
    limit = limit and limit or options.limit
    queue_name = queue_name and queue_name or options.queue_name
    qk = _get_redis_key(queue_name)
    
    # work out the timestamp we need tasks to be scheduled after
    if ts is None and delay == 0:
        ts = time.time()
    elif ts is None:
        ts = time.time() + delay
    
    # query redis
    results = r.send_command(
        'ZRANGEBYSCORE %s 0 %s LIMIT 0 %s\r\n' % (
            qk,
            ts,
            limit
        )
    )
    
    # unpack into a list of Task instances
    return [get_task(task_id, queue_name=queue_name) for task_id in results]
    

def count_tasks(queue_name=None):
    """Returns whether there are any_ tasks in a queue.
      
      .. _any: http://code.google.com/p/redis/wiki/ZcardCommand
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    
    qk = _get_redis_key(queue_name)
    return r.zcard(qk)
    


def clear_queue(queue_name=None):
    
    queue_name = queue_name and queue_name or options.queue_name
    
    qk = _get_redis_key(queue_name)
    r.delete(qk)
    

def create_n_tasks(n, url, params={}, queue_name=None):
    
    queue_name = queue_name and queue_name or options.queue_name
    
    i = n
    while i > 0:
        params.update({'i': i})
        add_task(url, params=params, queue_name=queue_name)
        i -= 1
    
    

