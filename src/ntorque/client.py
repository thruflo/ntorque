# -*- coding: utf-8 -*-

"""Provides composable dispatcher and client implementations that can be used
  from Python applications to enqueue tasks.

  The most straightforward and generic are the ``DirectDispatcher`` and
  ``HTTPTorqueClient`` which can be used together to dispatch tasks over HTTP.

  For example, instantiate a client::

      dispatcher = DirectDispatcher()
      client = HTTPTorqueClient(dispatcher, 'https://example.com/torque')

  Call it to dispatch a task::

      url = 'https://example.com/hook'
      status, response_data, response_headers = client(url)

  Note that you must encode your data manually before passing to the client.
  For example, to post JSON::

      data = {'foo': u'bar'}
      headers = {'Content-Type': u'application/json; utf-8'}
      client(url, data=json.dumps(data), headers=headers)

"""

__all__ = [
    'NoopDispatcher',
    'DirectDispatcher',
    'AfterCommitDispatcher',
    'HTTPTorqueClient',
    'HybridTorqueClient',
]

import logging
logger = logging.getLogger(__name__)

import requests
import os

from os.path import join as join_path
from urllib import urlencode

from pyramid_weblayer import tx

from ntorque import model
from ntorque.model import constants as c

SUCCESS = u'DISPATCHED'
FAILED = u'FAILED ({0})'

class NoopDispatcher(object):
    """A dispatcher that doesn't do anything."""

    def __call__(self, url, post_data, headers):
        return SUCCESS, None, None

class DirectDispatcher(object):
    """Dispatch an HTTP request and then wait for and handle the response."""

    def __init__(self, **kwargs):
        self.post = kwargs.get('post', requests.post)

    def __call__(self, url, post_data, headers):
        """Make the request and handle the response."""

        # Make the request -- this will raise an error on edge case
        # connection issues.
        r = self.post(url, data=post_data, headers=headers)

        # Handle the response.
        return self.handle(r)

    def handle(self, response):
        """Unpack  the ``response`` into ``data, status``."""

        # Get the response status.
        status = SUCCESS
        try:
            response.raise_for_status()
        except requests.exceptions.RequestException:
            status = FAILED.format(response.status_code)

        # Get the response data.
        try:
            data = response.json()
        except (AttributeError, TypeError, ValueError):
            data = response.text

        # And the headers.
        headers = response.headers

        # Return.
        return status, data, headers

class AfterCommitDispatcher(object):
    """Hang HTTP dispatch off a ``pyramid_weblayer.tx`` commit hook."""

    def __init__(self, **kwargs):
        self.post = kwargs.get('post', requests.post)
        self.after_commit = kwargs.get('after_commit', tx.call_in_background)

    def __call__(self, url, post_data, headers):
        """Dispatch the request in a background thread after the current
          transaction commits -- which means we can't wait for the response.
        """

        # Dispatch the request in a background thread.
        dispatch = lambda: self.post(url, data=post_data, headers=headers)
        self.after_commit(dispatch)

        # Don't wait around for the response.
        return SUCCESS, None, None

class HTTPTorqueClient(object):
    """Enqueue nTorque tasks using the HTTP `POST /` api."""

    def __init__(self, dispatcher, torque_url, api_key=None, **kwargs):
        self.dispatcher = dispatcher
        self.torque_url = torque_url
        self.api_key = api_key

    def __call__(self, url, data=None, headers=None, method=None, timeout=None):
        """Patch the api key into a POST request to the url."""

        # Unpack.
        dispatch = self.dispatcher
        torque_url = self.torque_url
        api_key = self.api_key

        # Validate the POST data.
        if data is not None and not isinstance(data, basestring):
            raise ValueError('Encode your post data as a string')

        # Prepare and augment the headers.
        if headers is None:
            headers = {}
        if api_key:
            headers['TORQUE_API_KEY'] = api_key
            headers['NTORQUE_API_KEY'] = api_key

        # Build a dict of query params.
        query = {'url': url}
        if method is not None:
            query['method'] = method
        if timeout is not None:
            query['timeout'] = timeout

        # Append the query params to the torque_url.
        divider = '&' if '?' in torque_url else '?'
        url = '{0}{1}{2}'.format(torque_url, divider, urlencode(query))

        # Dispatch and return `response_data, status`.
        return dispatch(url, data, headers)

class HybridTorqueClient(object):
    """A specific client for applications that use the same database as their
      nTorque instance.

      For these applications, tasks can be stored directly in the database and
      pushed onto the notification queue with a POST to `/tasks/:task_id/push`.

      When used in tandem with the ``AfterCommitDispatcher`` within a Pyramid
      application using the zope ``transaction`` machinery, this provides a
      guarantee that application state will always be rebuildable from the db
      and that tasks will never be lost due to nTorque being down or restarting.
    """

    def __init__(self, dispatcher, torque_url, api_key=None, app_id=None, **kwargs):
        self.dispatcher = dispatcher
        self.torque_url = torque_url
        self.api_key = api_key
        self.app_id = app_id
        self.factory_cls = kwargs.get('factory_cls', model.TaskFactory)
        self.lookup = kwargs.get('lookup', model.LookupApplication())
        self.header_prefix = kwargs.get('header_prefix', c.PROXY_HEADER_PREFIX)
        self.join_path = kwargs.get('join_path', join_path)

    def __call__(self, url, data=None, headers=None, method=None, timeout=None, due=None):
        """Patch the api key into a POST request to the url."""

        # Compose.
        if headers is None:
            headers = {}

        # Unpack.
        api_key = self.api_key
        app_id = self.app_id
        header_prefix = self.header_prefix

        # Validate the POST data.
        if data is not None and not isinstance(data, basestring):
            raise ValueError('Encode your post data as a string')

        # Prepare and extract any pass through headers.
        passthrough_headers = {}
        for key in headers.keys():
            if key.lower().startswith(header_prefix.lower()):
                k = key[len(header_prefix):]
                passthrough_headers[k] = headers.pop(key)

        # Figure out the enctype from the headers -- this means that to use
        # JSON, the caller must have already encoded the data as a JSON string
        # and set a "Content-Type" header to e.g.: "application/json".
        properties = {}
        content_type = headers.get('Content-Type', None)
        if content_type: # Extract just the enctype.
            properties['enctype'] = content_type.split(';')[0]

        # Either use the app_id or the api_key to get an application. Note that
        # the task factory works with `None`, an id or an instance. Using an
        # app_id is more efficient as it skips a db query.
        application = None
        if app_id:
            application = app_id
        elif api_key:
            application = self.lookup(api_key)

        # Instantiate a task factory.
        factory = self.factory_cls(application, url, timeout, method)

        # Create and store the task.
        task = factory(body=data, headers=passthrough_headers, **properties)

        # Dispatch a push notification.
        return self.notify(task, headers)

    def notify(self, task, headers):
        """Use the normal dispatcher to send a push notification."""

        # Unpack.
        dispatch = self.dispatcher
        torque_url = self.torque_url
        api_key = self.api_key

        # Authenticate if necessary.
        if api_key:
            headers['TORQUE_API_KEY'] = api_key
            headers['NTORQUE_API_KEY'] = api_key

        # Build the url.
        url = self.join_path(torque_url, 'tasks', str(task.id), 'push')

        # Dispatch the notification.
        return dispatch(url, None, headers)
