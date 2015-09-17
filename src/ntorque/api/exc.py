# -*- coding: utf-8 -*-

"""Exception views."""

__all__ = [
    'MethodNotSupportedView',
    'HTTPErrorView',
    'SystemErrorView',
]

import logging
logger = logging.getLogger(__name__)

from pyramid import httpexceptions
from pyramid.view import view_config

from ntorque import model
from . import tree

@view_config(context=tree.APIRoot)
@view_config(context=tree.TaskRoot)
@view_config(context=model.Task)
class MethodNotSupportedView(object):
    """Generic view exposed to throw 405 errors when endpoints are requested
      with an unsupported request method.
    """

    def __init__(self, request, **kwargs):
        self.request = request
        self.exc_cls = kwargs.get('exc_cls', httpexceptions.HTTPMethodNotAllowed)

    def __call__(self):
        raise self.exc_cls



@view_config(context=httpexceptions.HTTPError, renderer='string')
class HTTPErrorView(object):
    def __init__(self, request):
        self.request = request

    def __call__(self):
        request = self.request
        settings = request.registry.settings
        if settings.get('ntorque.mode') == 'development':
            raise
        return request.exception



@view_config(context=Exception, renderer='string')
class SystemErrorView(object):
    """Handle an internal system error."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.exc_cls = kwargs.get('exc_cls', httpexceptions.HTTPInternalServerError)

    def __call__(self):
        request = self.request
        settings = request.registry.settings
        if request.exception:
            if settings.get('ntorque.mode') == 'development':
                raise
            logger.error(request.exception, exc_info=True)
        return self.exc_cls()


