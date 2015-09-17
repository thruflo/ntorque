# -*- coding: utf-8 -*-

"""Provide a convienient import api and a Pyramid entry point that configures
  the SQLAlchemy database engine, connection pool and metadata.
"""

import logging
logger = logging.getLogger(__name__)

import os

from .api import *
from .constants import *
from .orm import *

DEFAULTS = {
    'max_overflow': os.environ.get('SQLALCHEMY_MAX_OVERFLOW'),
    'pool_class': os.environ.get('SQLALCHEMY_POOL_CLASS'),
    'pool_size': os.environ.get('SQLALCHEMY_POOL_SIZE'),
    'pool_recycle': os.environ.get('SQLALCHEMY_POOL_RECYCLE'),
    'url': os.environ.get('DATABASE_URL', 'postgresql:///ntorque'),
}
DEFAULT_INTS = ('max_overflow', 'pool_size', 'pool_recycle')

class IncludeMe(object):
    """Configure the db engine and provide ``request.db_session``."""

    def __init__(self, **kwargs):
        self.base = kwargs.get('base', Base)
        self.default_settings = kwargs.get('default_settings', DEFAULTS)
        self.default_ints = kwargs.get('default_ints', DEFAULT_INTS)
        self.session_cls = kwargs.get('session_cls', Session)

    def __call__(self, config):
        """Read any env var configuration into the Pyramid settings and then
          use the pyramid_basemodel includeme function to create and bind the
          db engine, and then add a reified ``request.db_session`` property.
        """

        # Unpack settings.
        settings = config.get_settings()
        for key, value in self.default_settings.items():
            if value:
                if key in self.default_ints:
                    value = int(value)
                settings.setdefault('sqlalchemy.{0}'.format(key), value)

        # Create and bind using the basemodel configuration.
        config.include('pyramid_basemodel')

        # Provide ``request.db_session``.
        get_session = lambda request: self.session_cls()
        config.add_request_method(get_session, 'db_session', reify=True)

includeme = IncludeMe().__call__
