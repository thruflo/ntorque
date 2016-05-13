# -*- coding: utf-8 -*-

"""Functional tests for the nTorque client utilities."""

import logging
logger = logging.getLogger(__name__)

from datetime import datetime
from datetime import timedelta

import json
import requests
import time
import transaction
import urllib
import unittest

from ntorque.model import api as repo
from ntorque.model import constants

from ntorque import client

class WebTestResponseAdapter(object):
    """Adapt a ``webtest.response.TestResponse`` instance to provide a subset of
      the ``requests.Response`` class api.
    """

    def __init__(self, response, **kwargs):
        self.response = response
        self.exc_cls = kwargs.get('exc_cls', requests.exceptions.HTTPError)

    @property
    def headers(self):
        return self.response.headers

    @property
    def status_code(self):
        return self.response.status_int

    @property
    def text(self):
        try:
            return self.response.text
        except AttributeError:
            return u''

    def json(self):
        return self.response.json

    def raise_for_status(self):
        if self.status_code > 399:
            msg = u'{0} error.'.format(self.status_code)
            raise self.exc_cls(msg, response=self)

class WebTestPoster(object):
    """Compose a dispatcher with this to post using a webtest app."""

    def __init__(self, app, **kwargs):
        self.app = app
        self.adapter = kwargs.get('adapter', WebTestResponseAdapter)

    def __call__(self, url, data, headers, method='POST'):
        """Use ``self.app`` to make the request."""

        # Unpack.
        app = self.app
        response_adapter = self.adapter

        # Convert the url to a path with query string so,
        # e.g.: `http://localhost/foo?url=...` becomes `/foo?url=...`.
        path = '/' if 'http://localhost' in url else url
        parts = url.split('http://localhost')
        if len(parts) > 1:
            path += '/'.join(parts[1:])
        path = path.replace('//', '/')

        # Prepare the post.
        kwargs = dict(headers=headers, expect_errors=True)
        if data:
            kwargs['params'] = data

        # Return the adapted response.
        make_request = getattr(app, method.lower())
        return response_adapter(make_request(path, **kwargs))

class TestDispatch(unittest.TestCase):
    """Test the HTTP client with a direct dispatcher."""

    def setUp(self):
        from ntorque.tests import boilerplate
        self.app_factory = boilerplate.TestAppFactory()

    def tearDown(self):
        self.app_factory.drop()

    def makePoster(self):
        app = self.app_factory(**{'ntorque.authenticate': False})
        return WebTestPoster(app)

    def test_direct_http(self):
        """Use the direct dispatcher and HTTP client to enqueue a task."""

        # Instantiate direct HTTP dispatcher.
        dispatcher = client.DirectDispatcher(post=self.makePoster())
        cli = client.HTTPTorqueClient(dispatcher, 'http://localhost')

        # Use it to enqueue a task.
        status, data, headers = cli('http://example.com/hook')

        # Get the task id from the location header.
        location = headers['Location']
        task_id = int(location.split('/')[-1])

        # Assert that the task is in the database.
        lookup = repo.LookupTask()
        with transaction.manager:
            task = lookup(task_id)
            self.assertTrue(task.status == u'PENDING')

        # Assert that the notification is in the redis channel.
        factory = self.app_factory
        channel = factory.settings.get('ntorque.redis_channel')
        redis = factory.redis_client
        task_id, retry_count = map(int, redis.lpop(channel).split(':'))
        self.assertTrue(task_id == task_id)

    def test_dispatch_json(self):
        """Dispatch JSON encoded data."""

        # Instantiate direct HTTP dispatcher.
        dispatcher = client.DirectDispatcher(post=self.makePoster())
        cli = client.HTTPTorqueClient(dispatcher, 'http://localhost')

        # Use it to enqueue a task.
        url = 'http://example.com/hook'
        data = {'foo': u'bar'}
        headers = {'Content-Type': 'application/json; utf-8'}
        status, response_data, response_headers = cli(url, data=json.dumps(data),
                headers=headers)

        # Get the task id from the location header.
        location = response_headers['Location']
        task_id = int(location.split('/')[-1])

        # Assert that the task has the right charset, enctype and data.
        lookup = repo.LookupTask()
        with transaction.manager:
            task = lookup(task_id)
            self.assertTrue(task.charset.lower() == 'utf-8')
            self.assertTrue(task.enctype == 'application/json')

    def test_hybrid_after_commit(self):
        """Use the after commit dispatcher and hybrid client to enqueue a task."""

        # Instantiate.
        dispatcher = client.AfterCommitDispatcher(post=self.makePoster())
        cli = client.HybridTorqueClient(dispatcher, 'http://localhost')

        # Prepare.
        task_id = 1
        lookup = repo.LookupTask()

        # Assert that the task is not in the database.
        with transaction.manager:
            task = lookup(task_id)
            self.assertTrue(task is None)

        # Enqueue.
        with transaction.manager:
            cli('http://example.com/hook')

        # Wait a moment.
        time.sleep(0.1)

        # Assert that the task is in the database.
        with transaction.manager:
            task = lookup(task_id)
            self.assertTrue(task.status == u'PENDING')

        # Wait a moment.
        time.sleep(0.1)

        # Assert that the notification is in the redis channel.
        factory = self.app_factory
        channel = factory.settings.get('ntorque.redis_channel')
        redis = factory.redis_client
        task_id, retry_count = map(int, redis.lpop(channel).split(':'))
        self.assertTrue(task_id == task_id)

