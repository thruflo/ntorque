# -*- coding: utf-8 -*-

"""Provides ``Cleaner``, a utility that polls the db and deletes old tasks."""

__all__ = [
    'Cleaner',
]

from . import patch
patch.green_threads()

import logging
logger = logging.getLogger(__name__)

import time
from datetime import timedelta

from sqlalchemy.exc import SQLAlchemyError

from ntorque import model
from .main import Bootstrap

class Cleaner(object):
    """Polls the db and delete old tasks."""

    def __init__(self, days, interval=7200, **kwargs):
        self.days = days
        self.interval = interval
        self.delete_tasks = kwargs.get('delete_tasks', model.DeleteOldTasks())
        self.logger = kwargs.get('logger', logger)
        self.session = kwargs.get('session', model.Session)
        self.time = kwargs.get('time', time)
        self.timedelta = kwargs.get('timedelta', timedelta)

    def start(self):
        self.poll()

    def poll(self):
        """Poll the db ad-infinitum."""

        delta = self.timedelta(days=self.days)
        while True:
            t1 = self.time.time()
            try:
                self.delete_tasks(delta)
            except SQLAlchemyError as err:
                self.logger.warn(err, exc_info=True)
            finally:
                self.session.remove()
            self.time.sleep(self.interval)


class ConsoleScript(object):
    """Bootstrap the environment and run the consumer."""

    def __init__(self, **kwargs):
        self.cleaner_cls = kwargs.get('cleaner_cls', Cleaner)
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
        days = int(settings.get('ntorque.cleanup_after_days'))

        # Instantiate and start the consumer.
        cleaner = self.cleaner_cls(days)
        try:
            cleaner.start()
        finally:
            self.session.remove()


main = ConsoleScript()
