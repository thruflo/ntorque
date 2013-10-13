# -*- coding: utf-8 -*-

"""Expose and implement the Torque API endpoints."""

__all__ = [
    'EnqueTask',
]

import logging
logger = logging.getLogger(__name__)

import re

from pyramid import httpexceptions
from pyramid.view import view_config

from torque import model
from . import tree

# From `colander.url`.
URL_PATTERN = r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))"""

VALID_ID = re.compile(r'^[0-9]+$')
VALID_URL = re.compile(URL_PATTERN) 

@view_config(context=tree.APIRoot, permission='create', request_method='POST',
        renderer='string')
class EnqueTask(object):
    """``POST /`` endpoint."""
    
    def __init__(self, request, **kwargs):
        self.request = request
        self.bad_request = kwargs.get('bad_request', httpexceptions.HTTPBadRequest)
        self.create_task = kwargs.get('create_task', model.CreateTask())
        self.valid_url = kwargs.get('valid_url', VALID_URL)
    
    def __call__(self):
        """Validate, store the task and return a 201 response."""
        
        # Unpack.
        request = self.request
        settings = request.registry.settings
        
        # Validate.
        url = request.GET.get('url', None)
        has_valid_url = url and self.valid_url.match(url)
        if not has_valid_url:
            raise self.bad_request(u'You must provide a valid web hook URL.')
        
        # Store the task.
        task = self.create_task(request.application, url, request)
        
        # Notify.
        channel = settings['torque.redis_channel']
        request.redis.rpush(channel, str(task.id))
        
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
    

