#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Provides methods for adding and fetching tasks
  to and from a redis_ backed queue.
  
  .. _redis: http://code.google.com/p/redis
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
    'queue_name', default='default', 
    help='which queue are we processing?'
)
define(
    'limit', default=10, type=int,
    help='how many tasks do you want to process concurrently?'
)

KEY_PREFIX = u'thruflo.torque.'
def _get_redis_key(s):
    """Adds ``KEY_PREFIX`` to the start of all redis keys, to lower
      the risk of a namespace collision.
    """
    
    return u'%s%s' % (KEY_PREFIX, s)
    


class Task(object):
    """A task consists of a ``url`` to post some ``params`` to::
          
          >>> n = clear_queue()
          >>> t = Task(url='http://localhost/do/foo', params={'a': 1})
      
      If you want to put the task in a queue that's not the default,
      specify it when creating the task instance::
          
          >>> t = Task(
          ...     url='http://localhost/do/foo', 
          ...     params={'a': 1}, 
          ...     queue_name='doctests'
          ... )
      
      A ``Task`` instance has ``id``, ``url`` and ``params`` properties::
      
          >>> t.id
          '189d29c7e6d63d810d307203a37e204999a5ffbefa8ff4bc40554a2c'
          >>> t.url
          'http://localhost/do/foo'
          >>> t.params
          {'a': 1}
      
      You can add it to the queue::
      
          >>> t.add()
          1
      
      If it wasn't in the queue already, ``add`` returns ``1``.  Otherwise
      ``add`` returns ``0``::
          
          >>> t.add()
          0
      
      You can schedule the task to be executed *after* ``delay`` number of
      seconds in the future::
          
          >>> t.add(delay=5)
          0
      
      You can remove it from the queue.  This returns ``1`` if the task was 
      queued, or ``0`` if not::
          
          >>> t.remove()
          1
          >>> t.remove()
          0
      
      And you can increment an error count::
          
          >>> t.get_and_increment_error_count()
          1
          >>> t.get_and_increment_error_count()
          2
          >>> t.get_and_increment_error_count()
          3
      
      A task, once added, is actually persisted in redis via three
      entries.  The task_string is stored against ``_k``, which is generated
      from the ``queue_name`` and ``id``::
          
          >>> t._k
          u'thruflo.torque.doctests.189d29c7e6d63d810d307203a37e204999a5ffbefa8ff4bc40554a2c'
      
      And error count is stored against ``_ek``::
      
          >>> t._ek
          u'thruflo.torque.doctests.189d29c7e6d63d810d307203a37e204999a5ffbefa8ff4bc40554a2c.errors'
          
      The id is stored in a redis SortedSet_, scored (i.e.: sorted) by timestamp,
      where the set has the key ``_qk``::
      
          >>> t.add()
          1
          >>> ts = r.zscore(t._qk, t._id)
          
      .. _SortedSet: http://code.google.com/p/redis/wiki/SortedSets
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
        """Remove_ the id from the sorted set, delete_ the error count
          and then the task_string.
          
          .. _Remove: http://code.google.com/p/redis/wiki/ZremCommand
          .. _delete: http://code.google.com/p/redis/wiki/DelCommand
        """
        
        # remove the task
        result = r.zrem(self._qk, self._id)
        
        # delete the error count
        r.delete(self._ek)
        
        # delete the task_string last
        r.delete(self._k)
        
        return result
        
    
    def get_and_increment_error_count(self):
        """Increment_ and return the error count.
          
          .. _Increment: http://code.google.com/p/redis/wiki/IncrCommand
        """
        
        return r.incr(self._ek)
        
    
    
    def __repr__(self):
        return u'<torque.client.Task %s>' % (self._k)
    
    


def add_task(url, params={}, queue_name=None, delay=0):
    """Shortcut function to create and add a ``Task``::
      
          >>> n = clear_queue()
          >>> t = add_task(url='http://localhost/do/foo', params={'a': 1}, delay=2)
          >>> t.id
          '189d29c7e6d63d810d307203a37e204999a5ffbefa8ff4bc40554a2c'
          >>> t.remove()
          1
      
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    
    t = Task(url, params=params, queue_name=queue_name)
    t.add(delay=delay)
    return t
    

def get_task(task_id, queue_name=None):
    """Returns a queued ``Task`` instance corresponding to the ``task_id``.
      
      Raises a ``KeyError`` if the task is not in the queue::
          
          >>> n = clear_queue()
          >>> t = Task(url='http://localhost/do/foo', params={'a': 1})
          >>> t.add()
          1
          >>> get_task(t.id)
          <torque.client.Task thruflo.torque.doctests.189d29c7e6d63d810d307203a37e204999a5ffbefa8ff4bc40554a2c>
          >>> t.remove()
          1
          >>> get_task(t.id)
          Traceback (most recent call last):
          ...
          KeyError: 'Task id ``189d29c7e6d63d810d307203a37e204999a5ffbefa8ff4bc40554a2c`` is not in queue ``doctests``'
      
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    qk = _get_redis_key(queue_name)
    k = u'%s.%s' % (qk, task_id)
    
    # get the task_string corresponding to the task_id provided
    task_string = r.get(k)
    if task_string is None:
        raise KeyError('Task id ``%s`` is not in queue ``%s``' % (task_id, queue_name))
    
    # decode into a python dict
    data = json_decode(task_string)
    
    # return a Task using the data
    return Task(data['url'], params=data['params'], queue_name=queue_name)
    

def fetch_tasks(ts=None, delay=0, limit=None, queue_name=None):
    """Gets upto ``limit`` tasks from the queue, in timestamp order,
      using the ZRANGEBYSCORE_ command.
      
      No tasks pending returns an empty list::
          
          >>> n = clear_queue()
          >>> fetch_tasks()
          []
      
      Create three tasks, ``a``, ``b`` and ``c``::
          
          >>> a = Task('a')
          >>> b = Task('b')
          >>> c = Task('c')
      
      Add task ``a`` scheduled immediately::
          
          >>> a.add()
          1
          
      Add task ``b`` scheduled after 2 seconds time::
          
          >>> b.add(delay=2)
          1
      
      Add task ``c`` scheduled after 1 seconds::
          
          >>> c.add(delay=1)
          1
      
      ``a`` is the only immediate pending task::
          
          >>> pending = fetch_tasks()
          >>> pending
          [<torque.client.Task thruflo.torque.doctests.b1ae1ca8c4af1d10b7606ed5e49ad88b9e0d35e89a435893414976c4>]
          >>> [t.id for t in pending] == [a.id]
          True
      
      Wait 1 second and now ``a`` and ``c`` are pending, in that order::
          
          >>> time.sleep(1)
          >>> [t.id for t in fetch_tasks()] == [a.id, c.id]
          True
          
      Wait another second::
          
          >>> time.sleep(1)
          >>> [t.id for t in fetch_tasks()] == [a.id, c.id, b.id]
          True
      
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
          
          >>> n = clear_queue()
          >>> count_tasks()
          0
          >>> t = add_task('a')
          >>> count_tasks()
          1
      
      .. _any: http://code.google.com/p/redis/wiki/ZcardCommand
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    
    qk = _get_redis_key(queue_name)
    return r.zcard(qk)
    


def clear_queue(queue_name=None):
    """Remove all of the tasks from a queue::
      
          >>> n = clear_queue()
          >>> add_task('a')
          <torque.client.Task thruflo.torque.doctests.b1ae1ca8c4af1d10b7606ed5e49ad88b9e0d35e89a435893414976c4>
          >>> add_task('b')
          <torque.client.Task thruflo.torque.doctests.f84ff8757572c751e8e54ca7b1351906ec6260ac944d5f0d2728c188>
          >>> clear_queue()
          2
      
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    
    # delete the sorted set
    qk = _get_redis_key(queue_name)
    r.delete(qk)
    
    # delete any associated task strings and error counts
    ks = r.keys(u'%s*' % qk)
    if ks:
        return r.send_command(u'DEL %s\r\n' % u' '.join(ks))
    return 0
    

def create_n_tasks(n, url, params={}, queue_name=None):
    """Function designed to ease manual testing.
    """
    
    queue_name = queue_name and queue_name or options.queue_name
    
    i = n
    while i > 0:
        params.update({'i': i})
        add_task(url, params=params, queue_name=queue_name)
        i -= 1
    
    


def setup():
    options.queue_name = 'doctests'

def teardown():
    clear_queue()

