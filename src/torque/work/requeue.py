# -*- coding: utf-8 -*-

"""Provides ``RequeuePoller``, a utility that polls the db and add tasks
  to the queue.
"""

__all__ = [
    'RequeuePoller',
]

import logging
logger = logging.getLogger(__name__)

import time

from pyramid_redis.hooks import RedisFactory
from torque import model
from .main import BootstrapRegistry

class RequeuePoller(object):
    """Takes instructions from one or more redis channels. Calls a handle
      function in a new thread, passing through a flag that the handle
      function can periodically check to exit.
      
      if due > self.datetime.utcnow() and status == self.statuses['pending']
      
    """
    
    def __init__(self, redis, channel, interval=20, **kwargs):
        self.redis = redis
        self.channel = channel
        self.interval = interval
        self.get_tasks = kwargs.get('get_tasks', model.GetDueTasks())
        self.logger = kwargs.get('logger', logger)
        self.time = kwargs.get('time', time)
    
    def start(self):
        self.poll()
    
    def poll(self):
        """Poll the db ad-infinitum."""
        
        while True:
            t1 = self.time.time()
            try:
                tasks = self.get_tasks()
            except Exception as err:
                self.logger.warn(err, exc_info=True)
            else:
                for task in tasks:
                    self.enqueue(task)
            current_time = self.time.time()
            due_time = t1 + self.interval
            if current_time < due_time:
                self.time.sleep(due_time - current_time)
    
    def enqueue(self, task):
        """Push an instruction to re-try the task on the redis channel."""
        
        instruction = '{0}:{0}'.format(task.id, task.retry_count)
        self.redis.rpush(self.channel, instruction)
    

class ConsoleScript(object):
    """Bootstrap the environment and run the consumer."""
    
    def __init__(self, **kwargs):
        self.requeue_cls = kwargs.get('requeue_cls', RequeuePoller)
        self.get_redis = kwargs.get('get_redis', RedisFactory())
        self.get_registry = kwargs.get('get_registry', BootstrapRegistry())
    
    def __call__(self):
        """Get the configured registry. Unpack the redis client and input
          channel(s), instantiate and start the consumer.
        """
        
        # Get the configured registry.
        registry = self.get_registry()
        
        # Unpack the redis client and input channels.
        settings = registry.settings
        redis_client = self.get_redis(settings, registry=registry)
        channel = settings.get('torque.redis_channel')
        
        # Instantiate and start the consumer.
        poller = self.requeue_cls(redis_client, channel)
        try:
            poller.start()
        except KeyboardInterrupt:
            pass
    

main = ConsoleScript()
