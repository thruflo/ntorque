# -*- coding: utf-8 -*-

"""Expose and implement the Torque API endpoints."""

__all__ = [
    'EnqueTask',
]

import logging
logger = logging.getLogger(__name__)

import re

from pyramid import httpexceptions
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.view import view_config

from ntorque import model
from ntorque.model import constants
from . import tree

# From `colander.url`.
URL_PATTERN = r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))"""

VALID_INT = re.compile(r'^[0-9]+$')
VALID_URL = re.compile(URL_PATTERN)

@view_config(context=tree.APIRoot, permission=NO_PERMISSION_REQUIRED,
        request_method='GET', renderer='string')
def installed_view(object):
    """``POST /`` endpoint."""

    return u'Torque installed and reporting for duty, sir!'

@view_config(context=tree.APIRoot, permission='create', request_method='POST',
        renderer='string')
class EnqueTask(object):
    """``POST /`` endpoint."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.bad_request = kwargs.get('bad_request', httpexceptions.HTTPBadRequest)
        self.create_task = kwargs.get('create_task', model.CreateTask(request))
        self.default_method = kwargs.get('default_method', constants.DEFAULT_METHOD)
        self.push_notify = kwargs.get('push_notify', model.PushTaskNotification(request))
        self.valid_int = kwargs.get('valid_int', VALID_INT)
        self.valid_methods = kwargs.get('valid_methods', constants.REQUEST_METHODS)
        self.valid_url = kwargs.get('valid_url', VALID_URL)

    def __call__(self):
        """Validate, store the task and return a 201 response."""

        # Unpack.
        request = self.request
        settings = request.registry.settings

        # Validate.
        # - url
        url = request.GET.get('url', None)
        has_valid_url = url and self.valid_url.match(url)
        if not has_valid_url:
            raise self.bad_request(u'You must provide a valid web hook URL.')
        # - timeout
        default_timeout = settings.get('ntorque.default_timeout')
        raw_timeout = request.GET.get('timeout', default_timeout)
        try:
            timeout = int(raw_timeout)
        except ValueError:
            raise self.bad_request(u'You must provide a valid integer timeout.')
        # - method
        method = request.GET.get('method', self.default_method)
        if method not in self.valid_methods:
            methods_str = u', '.join(self.valid_methods)
            msg = u'Request `method` must be one of: {0}.'.format(methods_str)
            raise self.bad_request(msg)

        # Store the task.
        app = request.application
        task = self.create_task(app, url, timeout, method)

        # Notify.
        self.push_notify(task)

        # Return a 201 response with the task url as the Location header.
        response = request.response
        response.status_int = 201
        response.headers['Location'] = request.resource_url(task)[:-1]
        return ''

@view_config(context=model.Task, permission='view', request_method='GET',
        renderer='json')
class TaskStatus(object):
    """``GET /tasks/task:id`` endpoint."""

    def __init__(self, request, **kwargs):
        self.request = request

    def __call__(self):
        """Validate, store the task and return a 201 response."""

        # Unpack.
        request = self.request
        task = request.context

        # Return a 200 response with a JSON repr of the task.
        return task

@view_config(context=model.Task, name='push', permission='view',
        request_method='POST', renderer='json')
class PushTask(object):
    """``POST /tasks/task:id/push`` to push an existing task onto the redis queue."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.push_notify = kwargs.get('push_notify', model.PushTaskNotification(request))

    def __call__(self):
        """Push the task onto the queue."""

        # Unpack.
        request = self.request
        task = request.context

        # Notify.
        self.push_notify(task)

        # Return a 201 response with the task url as the Location header.
        response = request.response
        response.status_int = 201
        response.headers['Location'] = request.resource_url(task)[:-1]
        return ''
