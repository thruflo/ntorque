# -*- coding: utf-8 -*-

"""Provides ``RequeuePoller``, a utility that polls the db and add tasks
  to the queue.
"""

__all__ = [
    'RequeuePoller',
]

from . import patch
patch.green_threads()

import logging
logger = logging.getLogger(__name__)

import time

from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from pyramid_redis.hooks import RedisFactory
from ntorque import model
from .main import Bootstrap

class RequeuePoller(object):
    """Polls the database for tasks that should be re-queued."""

    def __init__(self, redis, channel, delay=0.001, interval=5, **kwargs):
        self.redis = redis
        self.channel = channel
        self.delay = delay
        self.interval = interval
        self.get_tasks = kwargs.get('get_tasks', model.GetDueTasks())
        self.logger = kwargs.get('logger', logger)
        self.session = kwargs.get('session', model.Session)
        self.time = kwargs.get('time', time)

    def start(self):
        self.poll()

    def poll(self):
        """Poll the db ad-infinitum."""

        while True:
            t1 = self.time.time()
            try:
                tasks = self.get_tasks()
            except SQLAlchemyError as err:
                self.logger.warn(err, exc_info=True)
            else:
                if tasks:
                    for task in tasks:
                        try:
                            self.enqueue(task)
                        except RedisError as err:
                            self.logger.warn(err, exc_info=True)
                        self.time.sleep(self.delay)
            finally:
                self.session.remove()
            current_time = self.time.time()
            due_time = t1 + self.interval
            if current_time < due_time:
                self.time.sleep(due_time - current_time)

    def enqueue(self, task):
        """Push an instruction to re-try the task on the redis channel."""

        instruction = '{0}:{1}'.format(task.id, task.retry_count)
        self.redis.rpush(self.channel, instruction)

class ConsoleScript(object):
    """Bootstrap the environment and run the consumer."""

    def __init__(self, **kwargs):
        self.requeue_cls = kwargs.get('requeue_cls', RequeuePoller)
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
        settings = config.registry.settings
        redis_client = self.get_redis(settings, registry=config.registry)
        channel = settings.get('ntorque.redis_channel')

        # Get the requeue interval.
        interval = int(settings.get('ntorque.requeue_interval'))

        # Instantiate and start the consumer.
        poller = self.requeue_cls(redis_client, channel, interval=interval)
        try:
            poller.start()
        finally:
            self.session.remove()

main = ConsoleScript()
