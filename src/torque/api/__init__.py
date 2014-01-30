# -*- coding: utf-8 -*-

"""Configure the Pyramid web application and provide a WSGI entry point."""

__all__ = [
    'WSGIAppFactory',
]

import logging
logger = logging.getLogger(__name__)

import os

from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.settings import asbool

from torque import model

from . import auth
from . import tree

DEFAULTS = {
    'authenticate': os.environ.get('TORQUE_AUTHENTICATE', True),
    'default_timeout': os.environ.get('TORQUE_DEFAULT_TIMEOUT', 60),
    'enable_hsts': os.environ.get('TORQUE_ENABLE_HSTS', False),
    'hsts.protocol_header': os.environ.get('HSTS_PROTOCOL_HEADER', None),
    'mode': os.environ.get('MODE', 'development'),
    'redis_channel': os.environ.get('TORQUE_REDIS_CHANNEL', 'torque'),
}

class IncludeMe(object):
    """Configure the Pyramid web application."""
    
    def __init__(self, **kwargs):
        self.authn_policy = kwargs.get('authn_policy', auth.AuthenticationPolicy())
        self.authz_policy = kwargs.get('authz_policy', ACLAuthorizationPolicy())
        self.default_settings = kwargs.get('default_settings', DEFAULTS)
        self.get_app = kwargs.get('get_app', auth.GetAuthenticatedApplication())
        self.root_factory = kwargs.get('root_factory', tree.APIRoot)
        self.tasks_root = kwargs.get('tasks_root', tree.TaskRoot)
    
    def __call__(self, config):
        """Configure, lock down and expose the API."""
        
        # Unpack settings.
        settings = config.get_settings()
        for key, value in self.default_settings.items():
            settings.setdefault('torque.{0}'.format(key), value)
        
        # Configure db access.
        config.include('torque.model')
        
        # Configure redis.
        config.include('pyramid_redis')
        
        # Wrap everything with the transaction manager.
        config.include('pyramid_tm')
        
        # If configured, enforce HSTS.
        should_enable_hsts = settings.get('torque.enable_hsts')
        if asbool(should_enable_hsts):
            config.include('pyramid_hsts')
        
        # If configured, enforce authentication.
        should_authenticate = settings.get('torque.authenticate')
        if asbool(should_authenticate):
            config.set_authorization_policy(self.authz_policy)
            config.set_authentication_policy(self.authn_policy)
        config.add_request_method(self.get_app, 'application', reify=True)
        
        # Expose the API using traversal from the APIRoot.
        config.add_route('api', '/*traverse', factory=self.root_factory,
                use_global_views=True)
        
        # And scan this package to pick up view configuration.
        config.scan()
    

includeme = IncludeMe().__call__

class WSGIAppFactory(object):
    """Instantiate a Pyramid Configurator, include this package and return
      a WSGI app.
    """
    
    def __init__(self, **kwargs):
        self.configurator_cls = kwargs.get('configurator_cls', Configurator)
        self.includeme = kwargs.get('includeme', IncludeMe())
        self.session = kwargs.get('session', model.Session)
    
    def __call__(self, **kwargs):
        """Configure and return the app, making sure to explicitly close any
          db connections opened by the thread local session.
        """
        
        # Configure the app.
        config = self.configurator_cls(**kwargs)
        self.includeme(config)
        
        # Explicitly close any db connections.
        self.session.remove()
        
        # Return a WSGI app.
        return config.make_wsgi_app()
    

wsgi_app_factory = WSGIAppFactory()

# Provide a ``main`` wsgi app entrypoint.
main = wsgi_app_factory()
