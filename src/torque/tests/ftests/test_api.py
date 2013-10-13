# -*- coding: utf-8 -*-

"""Functional tests for the torque API."""

import logging
logger = logging.getLogger(__name__)

import json
import transaction
import urllib
import unittest

from torque.tests import boilerplate

class TestRootEndpoint(unittest.TestCase):
    """Test the ``POST /`` endpoint to create tasks."""
    
    def setUp(self):
        self.app_factory = boilerplate.TestAppFactory()
    
    def tearDown(self):
        self.app_factory.drop()
    
    def test_unsupported_method(self):
        """GET is not a supported method."""
        
        api = self.app_factory()
        r = api.get('/', status=405)
    
    def test_post(self):
        """Unauthenticated POST should be forbidden by default."""
        
        api = self.app_factory()
        r = api.post('/', status=403)
    
    def test_post_without_authentication(self):
        """POST should not be forbidden if told not to authenticate."""
        
        settings = {'torque.should_authenticate': False}
        api = self.app_factory(**settings)
        r = api.post('/', status=400)
    
    def test_post_authenticated(self):
        """Authenticated POST should not be forbidden."""
        
        from torque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()
        
        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()
        
        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')
        
        # Now the request should make it through auth to fail on validation.
        r = api.post('/', headers={'api_key': api_key}, status=400)
    
    def test_post_task(self):
        """POSTing a valid url should enque a task."""
        
        from torque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()
        get_task = model.GetTask()
        
        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()
        
        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')
        headers={'api_key': api_key}
        
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
        
        from torque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()
        
        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()
        
        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')
        headers={'api_key': api_key}
        
        # Invent an invalid web hook url.
        url = u'not a url'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))
        
        # Enquing the task should fail.
        r = api.post(endpoint, headers=headers, status=400)
    
    def test_post_task_without_authentication(self):
        """POSTing without auth should enque a task with ``app==None``."""
        
        from torque import model
        get_task = model.GetTask()
        
        # Create the wsgi app, which also sets up the db.
        settings = {'torque.should_authenticate': False}
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
        
        from torque import model
        get_task = model.GetTask()
        
        # Create the wsgi app, which also sets up the db.
        settings = {'torque.should_authenticate': False}
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
        
        from torque import model
        get_task = model.GetTask()
        
        # Create the wsgi app, which also sets up the db.
        settings = {'torque.should_authenticate': False}
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
    

class TestGetCreatedTaskLocation(unittest.TestCase):
    """Test that the task location returned by ``POST /`` works."""
    
    def setUp(self):
        self.app_factory = boilerplate.TestAppFactory()
    
    def tearDown(self):
        self.app_factory.drop()
    
    def test_get_created_task_location(self):
        """The location returned after enquing a task should be gettable."""
        
        # Create the wsgi app, which also sets up the db.
        settings = {'torque.should_authenticate': False}
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
        
        from torque import model
        create_app = model.CreateApplication()
        get_key = model.GetActiveKey()
        get_task = model.GetTask()
        
        # Create the wsgi app, which also sets up the db.
        api = self.app_factory()
        
        # Create an application and get its api key.
        with transaction.manager:
            app = create_app(u'example')
            api_key = get_key(app).value.encode('utf-8')
        headers={'api_key': api_key}
        
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
        channel = settings.get('torque.redis_channel')
        redis = self.app_factory.redis_client
        
        # Enquing the task should respond with 201 and the location header.
        self.assertEquals(redis.llen(channel), 0)
    
    def test_notification(self):
        """After creating a task, its id should be on the redis channel."""
        
        # Setup.
        api = self.app_factory(**{'torque.should_authenticate': False})
        settings = self.app_factory.settings
        channel = settings.get('torque.redis_channel')
        redis = self.app_factory.redis_client
        
        # Enque the task.
        url = u'http://example.com/hook'
        endpoint = '/?url=' + urllib.quote_plus(url.encode('utf-8'))
        r = api.post(endpoint, status=201)
        location = r.headers['Location']
        
        # Its id should be in the redis channel list.
        self.assertEquals(redis.llen(channel), 1)
        task_id_str = redis.lpop(channel)
        task_id = int(task_id_str)
        self.assertTrue(task_id > 0)
        self.assertTrue(location.endswith(task_id_str))
    
    def test_notification_order(self):
        """Task notifications should be added to the tail of the channel list."""
        
        # Setup.
        api = self.app_factory(**{'torque.should_authenticate': False})
        settings = self.app_factory.settings
        channel = settings.get('torque.redis_channel')
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
        id1 = redis.lpop(channel)
        id2 = redis.lpop(channel)
        self.assertTrue(location1.endswith(id1))
        self.assertTrue(location2.endswith(id2))
    

