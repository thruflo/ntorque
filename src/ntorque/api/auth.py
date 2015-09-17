# -*- coding: utf-8 -*-

"""Authenticate applications using API keys."""

__all__ = [
    'AuthenticationPolicy',
    'GetAuthenticatedApplication',
]

import logging
logger = logging.getLogger(__name__)

import os
import re

from zope.interface import implementer

from pyramid.authentication import CallbackAuthenticationPolicy
from pyramid.interfaces import IAuthenticationPolicy
from pyramid.security import unauthenticated_userid
from pyramid.settings import asbool

from ntorque import model

VALID_API_KEY = re.compile(r'^\w{40}$')

@implementer(IAuthenticationPolicy)
class AuthenticationPolicy(CallbackAuthenticationPolicy):
    """A Pyramid authentication policy which obtains credential data from the
      ``request.headers['NTORQUE_API_KEY']``.
    """

    def __init__(self, header_key='NTORQUE_API_KEY', **kwargs):
        self.header_key = header_key
        self.valid_key = kwargs.get('valid_key', VALID_API_KEY)

    def unauthenticated_userid(self, request):
        """The ``api_key`` value found within the ``request.headers``."""

        api_key = request.headers.get(self.header_key, None)
        if api_key and self.valid_key.match(api_key):
            return api_key.decode('utf8')

    def remember(self, request, principal, **kw):
        """A no-op. There's no way to remember the user.

              >>> policy = AuthenticationPolicy()
              >>> policy.remember('req', 'ppl')
              []

        """

        return []

    def forget(self, request):
        """A no-op. There's no user to forget.

              >>> policy = AuthenticationPolicy()
              >>> policy.forget('req')
              []

        """

        return []


class GetAuthenticatedApplication(object):
    """A Pyramid request method that looks up ``model.Application``s from the
      ``api_key`` provided by the ``AuthenticationPolicy``.
    """

    def __init__(self, **kwargs):
        self.get_app = kwargs.get('get_app', model.LookupApplication())
        self.get_userid = kwargs.get('get_userid', unauthenticated_userid)

    def __call__(self, request):
        api_key = self.get_userid(request)
        if api_key:
            return self.get_app(api_key)


