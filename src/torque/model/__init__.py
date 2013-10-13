# -*- coding: utf-8 -*-

"""Provide a convienient import api and a Pyramid entry point that configures
  the SQLAlchemy database engine, connection pool and metadata.
"""

import logging
logger = logging.getLogger(__name__)

import os

from sqlalchemy import engine_from_config

from .api import *
from .orm import *

DEFAULTS = {
    'max_overflow': os.environ.get('DATABASE_MAX_OVERFLOW', 3),
    'pool_size': os.environ.get('DATABASE_POOL_SIZE', 3),
    'pool_recycle': os.environ.get('DATABASE_POOL_RECYCLE', 300),
    'url': os.environ.get('DATABASE_URL', 'postgresql:///torque'),
}

class IncludeMe(object):
    """Configure the db engine and provide ``request.db_session``."""
    
    def __init__(self, **kwargs):
        self.base = kwargs.get('base', Base)
        self.default_settings = kwargs.get('default_settings', DEFAULTS)
        self.engine_factory = kwargs.get('engine_factory', engine_from_config)
        self.session_cls = kwargs.get('session_cls', Session)
    
    def __call__(self, config):
        """"""
        
        # Unpack settings.
        settings = config.get_settings()
        for key, value in self.default_settings.items():
            settings.setdefault('sqlalchemy.{0}'.format(key), value)
        
        # Create db engine.
        engine = self.engine_factory(settings, 'sqlalchemy.')
        
        # Bind session and declarative base to the db engine.
        self.session_cls.configure(bind=engine)
        self.base.metadata.bind = engine
        
        # Wrap everything with the transaction manager.
        config.include('pyramid_tm')
        
        # Provide ``request.db_session``.
        get_session = lambda request: self.session_cls()
        config.add_request_method(get_session, 'db_session', reify=True)
    

includeme = IncludeMe().__call__
