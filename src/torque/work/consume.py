# -*- coding: utf-8 -*-

"""Provides ``ChannelConsumer``, a utility that consumes task instructions from
  a redis channel and spawns a new (green) thread to perform each task.
"""

__all__ = [
    'ChannelConsumer',
]

import logging
logger = logging.getLogger(__name__)

import threading
import time

from pyramid_redis.hooks import RedisFactory

from .main import BootstrapRegistry
from .perform import TaskPerformer

class ChannelConsumer(object):
    """Takes instructions from one or more redis channels. Calls a handle
      function in a new thread, passing through a flag that the handle
      function can periodically check to exit.
    """
    
    def __init__(self, redis, channels, delay=0.001, timeout=10, **kwargs):
        self.redis = redis_client
        self.channels = channels
        self.connect_delay = delay
        self.timeout = timeout
        self.handler = kw.get('handler', TaskPerformer())
        self.logger = kw.get('logger', logger)
        self.sleep = kw.get('sleep', time.sleep)
        self.thread_cls = kw.get('thread_cls', threading.Thread)
        self.flag_cls = kw.get('flag_cls', threading.Event)
    
    def start(self):
        self.control_flag = self.flag_cls()
        self.control_flag.set()
        try:
            self.consume()
        finally:
            self.control_flag.clear()
    
    def consume(self):
        """Consume the redis channel ad-infinitum."""
        
        while True:
            try:
                return_value = self.redis.blpop(self.channels, timeout=self.timeout)
            except Exception as err:
                self.logger.warn(err, exc_info=True)
                self.sleep(self.timeout)
            else:
                if return_value is not None:
                    channel, data = return_value
                    self.spawn(data)
                    self.sleep(self.reconnect_delay)
    
    def spawn(self, data):
        """Handle the ``data`` in a new thread."""
        
        args = (data, self.control_flag)
        thread = self.thread_cls(target=self.handler, args=args)
        thread.start()
    

class ConsoleScript(object):
    """Bootstrap the environment and run the consumer."""
    
    def __init__(self, **kwargs):
        self.consumer_cls = kwargs.get('consumer_cls', ChannelConsumer)
        self.get_redis = kwargs.get('get_registry', RedisFactory())
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
        input_channels = settings.get('torque.redis_channel').strip().split()
        
        # Instantiate and start the consumer.
        consumer = self.consumer_cls(redis_client, input_channels)
        consumer.start()
    

main = ConsoleScript()
