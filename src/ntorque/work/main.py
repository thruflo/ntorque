# -*- coding: utf-8 -*-

"""Provides ``ConsoleEnvironment``, a callable utility that sets up a gevent
  patched environment for long running console scripts.
"""

__all__ = [
    'ConsoleEnvironment',
]

from . import patch
patch.green_threads()

# Enable logging to stderr
import logging
logging.basicConfig()

import os
from pyramid.config import Configurator

import pyramid_basemodel as model

DEFAULTS = {
    'mode': os.environ.get('MODE', 'development'),
    'redis_channel': os.environ.get('NTORQUE_REDIS_CHANNEL', 'ntorque'),
    'cleanup_after_days': os.environ.get('NTORQUE_CLEANUP_AFTER_DAYS', 7),
    'consume_delay': float(os.environ.get('NTORQUE_CONSUME_DELAY', 0.001)),
    'consume_timeout': int(os.environ.get('NTORQUE_CONSUME_TIMEOUT', 10)),
    'requeue_interval': os.environ.get('NTORQUE_REQUEUE_INTERVAL', 5),
}

class Bootstrap(object):
    """Bootstrap Pyramid dependencies and return the configured registry."""

    def __init__(self, **kwargs):
        self.configurator_cls = kwargs.get('configurator_cls', Configurator)
        self.default_settings = kwargs.get('default_settings', DEFAULTS)
        self.session = kwargs.get('session', model.Session)

    def __call__(self, **kwargs):
        """Configure and patch, making sure to explicitly close any connections
          opened by the thread local session.
        """

        # Unpack settings.
        config = self.configurator_cls(**kwargs)
        settings = config.get_settings()
        for key, value in self.default_settings.items():
            settings.setdefault('ntorque.{0}'.format(key), value)

        # Configure redis and the db connection.
        config.include('ntorque.model')
        config.include('pyramid_redis')
        config.commit()

        # Explicitly remove any db connections.
        self.session.remove()

        # Return the configurator instance.
        return config
