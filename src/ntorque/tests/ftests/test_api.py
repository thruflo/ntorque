# -*- coding: utf-8 -*-

"""Functional tests for the ntorque API."""

import logging
logger = logging.getLogger(__name__)

from datetime import datetime
from datetime import timedelta

import json
import transaction
import urllib
import unittest

from ntorque.model import constants
from ntorque.tests import boilerplate

class TestRootEndpoint(unittest.TestCase):
    """Test the ``POST /`` endpoint to create tasks."""

    def setUp(self):
        self.app_factory = boilerplate.TestAppFactory()

    def tearDown(self):
        self.app_factory.drop()

    def test_get(self):
        """GET returns an installation message."""

        api = self.app_factory()
        r = api.get('/', status=200)
        self.assertTrue(u'installed' in r.body)

    def test_post(self):
        """Unauthenticated POST should be forbidden by default."""

        api = self.app_factory()
        r = api.post('/', status=403)

    def test_post_without_authentication(self):
        """POST should not be forbidden if told not to authenticate."""

        settings = {'ntorque.authenticate': False}
        api = self.app_factory(**settings)
        r = api.post('/', status=400)

    def test_post_authenticated(self):
        """Authenticated POST should not be forbidden."""

        from ntorque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()

        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()

        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')

        # Now the request should make it through auth to fail on validation.
        r = api.post('/', headers={'NTORQUE_API_KEY': api_key}, status=400)

    def test_post_task(self):
        """POSTing a valid url should enque a task."""

        from ntorque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()
        get_task = model.LookupTask()

        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()

        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')
        headers={'NTORQUE_API_KEY': api_key}

        # Invent a web hook url.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))

        # Enquing the task should respond with 201.
        r = api.post(endpoint, headers=headers, status=201)

        # With the url to the task as the Location header.
        task_id = int(r.headers['Location'].split('/')[-1])
        with transaction.manager:
            task = get_task(task_id)
            task_url = task.url
            task_app_name = task.app.name
        self.assertEqual(task_url, url)
        self.assertEqual(task_app_name, u'example')

    def test_post_invalid_url(self):
        """POSTing an invalid url should not."""

        from ntorque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()

        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()

        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')
        headers={'NTORQUE_API_KEY': api_key}

        # Invent an invalid web hook url.
        url = u'not a url'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))

        # Enquing the task should fail.
        r = api.post(endpoint, headers=headers, status=400)

    def test_post_task_without_authentication(self):
        """POSTing without auth should enque a task with ``app==None``."""

        from ntorque import model
        get_task = model.LookupTask()

        # Create the wsgi app, which also sets up the db.
        settings = {'ntorque.authenticate': False}
        api = self.app_factory(**settings)

        # Invent a web hook url.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))

        # Enquing the task should respond with 201.
        r = api.post(endpoint, status=201)

        # With the url to the task as the Location header.
        task_id = int(r.headers['Location'].split('/')[-1])
        with transaction.manager:
            task = get_task(task_id)
            task_app = task.app
        self.assertIsNone(task_app)

    def test_post_task_with_body(self):
        """Enqued tasks should store the charset and encoding and the decoded
          POST body.
        """

        from ntorque import model
        get_task = model.LookupTask()

        # Create the wsgi app, which also sets up the db.
        settings = {'ntorque.authenticate': False}
        api = self.app_factory(**settings)

        # Setup a request with form encoded latin-1.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))
        headers = {'Content-Type': 'application/x-www-form-urlencoded;charset=latin1'}
        params = {'foo': u'bçr'.encode('latin1')}

        # Enquing the task should respond with 201.
        r = api.post(endpoint, headers=headers, params=params, status=201)

        # With the url to the task as the Location header.
        task_id = int(r.headers['Location'].split('/')[-1])
        with transaction.manager:
            task = get_task(task_id)
            task_charset = task.charset
            task_enctype = task.enctype
            task_body = task.body
        self.assertEquals(task_charset, u'latin1')
        self.assertEquals(task_enctype, u'application/x-www-form-urlencoded')
        self.assertTrue(task_body, urllib.urlencode(params).decode('latin1'))

    def test_post_task_with_json_body(self):
        """Test enqueing a task with a JSON body and UTF-8 charset."""

        from ntorque import model
        get_task = model.LookupTask()

        # Create the wsgi app, which also sets up the db.
        settings = {'ntorque.authenticate': False}
        api = self.app_factory(**settings)

        # Setup a request with form encoded latin-1.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))
        params = {u'foo': u'b€r'}

        # Enquing the task should respond with 201.
        r = api.post_json(endpoint, params=params, status=201)

        # With the url to the task as the Location header.
        task_id = int(r.headers['Location'].split('/')[-1])
        with transaction.manager:
            task = get_task(task_id)
            task_charset = task.charset
            task_enctype = task.enctype
            task_body = task.body
        self.assertEquals(task_charset, u'UTF-8')
        self.assertEquals(task_enctype, u'application/json')
        self.assertTrue(json.loads(task_body), params)

    def test_task_with_non_default_request_method(self):
        """Test enqueing a task with the PUT method."""

        from ntorque import model
        get_task = model.LookupTask()

        # Create the wsgi app, which also sets up the db.
        settings = {'ntorque.authenticate': False}
        api = self.app_factory(**settings)

        # Setup a request with PUT method.

        # Enqueue with and without cutsom method.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))
        r1 = api.post_json(endpoint, status=201)
        endpoint += '&method=' + urllib.quote_plus(u'PUT'.encode('utf-8'))
        r2 = api.post_json(endpoint, status=201)

        # The first task has the default method.
        task_id = int(r1.headers['Location'].split('/')[-1])
        with transaction.manager:
            task = get_task(task_id)
            task_method = task.method
        self.assertEquals(task_method, constants.DEFAULT_METHOD)

        # The second task has the PUT method.
        task_id = int(r2.headers['Location'].split('/')[-1])
        with transaction.manager:
            task = get_task(task_id)
            task_method = task.method
        self.assertEquals(task_method, u'PUT')

class TestGetCreatedTaskLocation(unittest.TestCase):
    """Test that the task location returned by ``POST /`` works."""

    def setUp(self):
        self.app_factory = boilerplate.TestAppFactory()

    def tearDown(self):
        self.app_factory.drop()

    def test_get_created_task_location(self):
        """The location returned after enquing a task should be gettable."""

        # Create the wsgi app, which also sets up the db.
        settings = {'ntorque.authenticate': False}
        api = self.app_factory(**settings)

        # Invent a web hook url.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))

        # Enquing the task should respond with 201 and the location header.
        r = api.post(endpoint, status=201)
        location = r.headers['Location']

        # Getting that location should return JSON and a 200.
        r = api.get_json(location, status=200)

    def test_get_created_task_access_control(self):
        """When using authentication, the task is only accessible to the app
          that created it.
        """

        from ntorque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()
        get_task = model.LookupTask()

        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()

        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')
        headers={'NTORQUE_API_KEY': api_key}

        # Invent a web hook url.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))

        # Enquing the task should respond with 201.
        r = api.post(endpoint, headers=headers, status=201)
        location = r.headers['Location']

        # Getting that location should be forbidden unless authenticated.
        r = api.get_json(location, status=403)
        r = api.get_json(location, headers=headers, status=200)


class TestCreatedTaskNotification(unittest.TestCase):
    """Test new task notifications."""

    def setUp(self):
        self.app_factory = boilerplate.TestAppFactory()

    def tearDown(self):
        self.app_factory.drop()

    def test_notification_channel_is_empty(self):
        """Before creating a task, the redis channel should be empty."""

        api = self.app_factory()
        settings = self.app_factory.settings
        channel = settings.get('ntorque.redis_channel')
        redis = self.app_factory.redis_client

        # Enquing the task should respond with 201 and the location header.
        self.assertEquals(redis.llen(channel), 0)

    def test_notification(self):
        """After creating a task, its `id:retry_count` should be in redis."""

        # Setup.
        api = self.app_factory(**{'ntorque.authenticate': False})
        settings = self.app_factory.settings
        channel = settings.get('ntorque.redis_channel')
        redis = self.app_factory.redis_client

        # Enque the task.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))
        r = api.post(endpoint, status=201)
        location = r.headers['Location']

        # Its id should be in the redis channel list.
        self.assertEquals(redis.llen(channel), 1)
        task_id, retry_count = map(int, redis.lpop(channel).split(':'))
        self.assertTrue(task_id > 0)
        self.assertTrue(retry_count is 0)
        self.assertTrue(location.endswith(str(task_id)))

    def test_notification_order(self):
        """Task notifications should be added to the tail of the channel list."""

        # Setup.
        api = self.app_factory(**{'ntorque.authenticate': False})
        settings = self.app_factory.settings
        channel = settings.get('ntorque.redis_channel')
        redis = self.app_factory.redis_client

        # Enque two tasks.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))
        r1 = api.post(endpoint, status=201)
        r2 = api.post(endpoint, status=201)
        location1 = r1.headers['Location']
        location2 = r2.headers['Location']

        # Pop them in order from the head of the list -- the first task should
        # come first.
        id1, _ = map(int, redis.lpop(channel).split(':'))
        id2, _ = map(int, redis.lpop(channel).split(':'))
        self.assertTrue(location1.endswith(str(id1)))
        self.assertTrue(location2.endswith(str(id2)))

    def test_manual_push_notification(self):
        """Test creating a task manually and then pushing a notification."""

        from ntorque.model.api import TaskFactory
        from ntorque.model.api import LookupTask

        # Setup.
        api = self.app_factory(**{'ntorque.authenticate': False})
        settings = self.app_factory.settings
        channel = settings.get('ntorque.redis_channel')
        redis = self.app_factory.redis_client

        # Manually create the task.
        timeout = 30
        factory = TaskFactory(None, u'http://example.com/hook', timeout, u'POST')
        with transaction.manager:
            task = factory()
            task_id = task.id

        # As a sanity check, let'd make sure that, when created, the task's
        # due date is in the future -- which means we have a window of opportunity
        # to push a notification onto the queue.
        lookup = LookupTask()
        task = lookup(task_id)
        self.assertTrue(task.status == u'PENDING')
        self.assertTrue(task.due > task.created + timedelta(seconds=timeout))

        # Push a notification onto the queue.
        path = '/tasks/{0}/push'.format(task_id)
        r = api.post(path, status=201)
        location = r.headers['Location']

        # Its id should be in the redis channel list.
        self.assertEquals(redis.llen(channel), 1)
        task_id, retry_count = map(int, redis.lpop(channel).split(':'))
        self.assertTrue(task_id == task.id)
        self.assertTrue(retry_count is 0)
        self.assertTrue(location.endswith(str(task_id)))

