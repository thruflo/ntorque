# -*- coding: utf-8 -*-

"""Configure the Pyramid web application and provide a WSGI entry point."""

__all__ = [
    'IncludeMe',
    'WSGIAppFactory',
]

import logging
logger = logging.getLogger(__name__)

import os

from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.settings import asbool

from pyramid_weblayer.main import make_wsgi_app

from ntorque import model

from . import auth
from . import tree

DEFAULTS = {
    'authenticate': os.environ.get('NTORQUE_AUTHENTICATE', True),
    'default_timeout': os.environ.get('NTORQUE_DEFAULT_TIMEOUT', 60),
    'enable_hsts': os.environ.get('NTORQUE_ENABLE_HSTS', False),
    'mode': os.environ.get('MODE', 'development'),
    'redis_channel': os.environ.get('NTORQUE_REDIS_CHANNEL', 'ntorque'),
}

class IncludeMe(object):
    """Configure the Pyramid web application."""

    def __init__(self, **kwargs):
        self.authn_policy = kwargs.get('authn_policy', auth.AuthenticationPolicy())
        self.authz_policy = kwargs.get('authz_policy', ACLAuthorizationPolicy())
        self.default_settings = kwargs.get('default_settings', DEFAULTS)
        self.get_app = kwargs.get('get_app', auth.GetAuthenticatedApplication())

    def __call__(self, config):
        """Configure, lock down and expose the API."""

        # Unpack settings.
        settings = config.get_settings()
        for key, value in self.default_settings.items():
            settings.setdefault('ntorque.{0}'.format(key), value)

        # Configure db access.
        config.include('ntorque.model')

        # Configure redis.
        config.include('pyramid_redis')

        # Wrap everything with the transaction manager.
        config.include('pyramid_tm')

        # If configured, enforce HSTS.
        should_enable_hsts = settings.get('ntorque.enable_hsts')
        if asbool(should_enable_hsts):
            config.include('pyramid_hsts')

        # If configured, enforce authentication.
        should_authenticate = settings.get('ntorque.authenticate')
        if asbool(should_authenticate):
            config.set_authorization_policy(self.authz_policy)
            config.set_authentication_policy(self.authn_policy)
        config.add_request_method(self.get_app, 'application', reify=True)

        # Expose the API using traversal from the APIRoot.
        config.add_route('api', '/*traverse', use_global_views=True)

        # And scan this package to pick up view configuration.
        config.scan()

includeme = IncludeMe().__call__

class WSGIAppFactory(object):
    """Provide a WSGI application factory."""

    def __init__(self, **kwargs):
        self.includeme = kwargs.get('includeme_func', IncludeMe())
        self.make_wsgi_app = kwargs.get('make_app', make_wsgi_app)
        self.root_factory = kwargs.get('root_factory', tree.APIRoot)

    def __call__(self, global_config, **settings):
        return self.make_wsgi_app(self.root_factory, self.includeme, **settings)

# Provide a ``main`` wsgi app entrypoint.
factory = WSGIAppFactory()
main = factory(None).__call__
