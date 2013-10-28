# -*- coding: utf-8 -*-

"""Provides ``ConsoleEnvironment``, a callable utility that sets up a gevent
  patched environment for long running console scripts.
"""

__all__ = [
    'ConsoleEnvironment',
]

# Patch everything with gevent.
import gevent.monkey
gevent.monkey.patch_all()
import gevent_psycopg2
gevent_psycopg2.monkey_patch()

import logging
import os

from pyramid.config import Configurator

from torque import model

DEFAULTS = {
    'mode': os.environ.get('MODE', 'development'),
    'redis_channel': os.environ.get('TORQUE_REDIS_CHANNEL', 'torque'),
}

class BootstrapRegistry(object):
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
            settings.setdefault('torque.{0}'.format(key), value)
        
        # Configure redis and the db connection.
        config.include('torque.model')
        config.include('pyramid_redis')
        config.commit()
        
        # Explicitly remove any db connections.
        self.session.remove()
        
        # Return the registry (the only part of the "environment" we're
        # interested in).
        return config.registry
    

