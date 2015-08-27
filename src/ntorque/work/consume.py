# -*- coding: utf-8 -*-

"""Provides ``ChannelConsumer``, a utility that consumes task instructions from
  a redis channel and spawns a new (green) thread to perform each task.
"""

__all__ = [
    'ChannelConsumer',
]

from . import patch
patch.green_threads()

import logging
logger = logging.getLogger(__name__)

import threading
import time

from redis.exceptions import RedisError
from pyramid_redis.hooks import RedisFactory

from ntorque import model

from .main import Bootstrap
from .perform import TaskPerformer

class ChannelConsumer(object):
    """Takes instructions from one or more redis channels. Calls a handle
      function in a new thread, passing through a flag that the handle
      function can periodically check to exit.
    """

    def __init__(self, redis, channels, delay=0.001, timeout=10, **kwargs):
        self.redis = redis
        self.channels = channels
        self.connect_delay = delay
        self.timeout = timeout
        self.handler_cls = kwargs.get('handler_cls', TaskPerformer)
        self.logger = kwargs.get('logger', logger)
        self.sleep = kwargs.get('sleep', time.sleep)
        self.thread_cls = kwargs.get('thread_cls', threading.Thread)
        self.flag_cls = kwargs.get('flag_cls', threading.Event)

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
            except RedisError as err:
                self.logger.warn(err, exc_info=True)
                self.sleep(self.timeout)
            else:
                if return_value is not None:
                    channel, data = return_value
                    self.spawn(data)
                    self.sleep(self.connect_delay)

    def spawn(self, data):
        """Handle the ``data`` in a new thread."""

        args = (data, self.control_flag)
        handler = self.handler_cls()
        thread = self.thread_cls(target=handler, args=args)
        thread.start()

class ConsoleScript(object):
    """Bootstrap the environment and run the consumer."""

    def __init__(self, **kwargs):
        self.consumer_cls = kwargs.get('consumer_cls', ChannelConsumer)
        self.get_redis = kwargs.get('get_redis', RedisFactory())
        self.get_config = kwargs.get('get_config', Bootstrap())
        self.session = kwargs.get('session', model.Session)

    def __call__(self):
        """Get the configured registry. Unpack the redis client and input
          channel(s), instantiate and start the consumer.
        """

        # Get the configured registry.
        config = self.get_config()

        # Unpack the redis client and input channels.
        settings = config.get_settings()
        delay = settings.get('ntorque.consume_delay')
        timeout = settings.get('ntorque.consume_timeout')
        redis_client = self.get_redis(settings, registry=config.registry)
        input_channels = settings.get('ntorque.redis_channel').strip().split()

        # Instantiate and start the consumer.
        consumer = self.consumer_cls(redis_client, input_channels, delay=delay,
                timeout=timeout)
        try:
            consumer.start()
        finally:
            self.session.remove()

main = ConsoleScript()
