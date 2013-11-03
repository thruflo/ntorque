# -*- coding: utf-8 -*-

"""Functional tests for the ``torque.work`` package."""

import logging
logger = logging.getLogger(__name__)

import json
import transaction
import urllib
import unittest

from torque.tests import boilerplate

class TestChannelConsumer(unittest.TestCase):
    """Test consuming instructions from the redis channel."""
    
    def setUp(self):
        self.reg_factory = boilerplate.TestRegFactory()
        self.registry = self.reg_factory()
    
    def tearDown(self):
        self.reg_factory.drop()
    
    #def test_foo(self):
    #    """XXX"""
    #    
    #    self.assertTrue('foo' == 'foo')
    

class TestTaskPerformer(unittest.TestCase):
    """Test performing tasks."""
    
    def setUp(self):
        self.reg_factory = boilerplate.TestRegFactory()
        self.registry = self.reg_factory()
    
    def tearDown(self):
        self.reg_factory.drop()
    
    def test_performing_task_miss(self):
        """Performing a task that doesn't exist returns None."""
        
        from torque.work.perform import TaskPerformer
        performer = TaskPerformer()
        
        status = performer('1234:0', None)
        self.assertIsNone(status)
    
    def test_performing_task(self):
        """Performing a task successfully marks it as completed."""
        
        from mock import Mock
        from pyramid.request import Request
        from threading import Event
        flag = Event()
        flag.set()
        
        from torque.model import TASK_STATUSES
        from torque.model import CreateTask
        from torque.model import Session
        from torque.work.perform import TaskPerformer
        
        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask()
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, req)
            instruction = '{0}:0'.format(task.id)
        
        # Instantiate a performer with the requests.post method mocked
        # to return 200 without making a request.
        mock_post = Mock()
        mock_post.return_value.status_code = 200
        performer = TaskPerformer(post=mock_post)
        
        # When performed, the task should be marked as completed.
        status = performer(instruction, flag)
        self.assertTrue(status is TASK_STATUSES[u'completed'])
    
    def test_performing_task_connection_error(self):
        """Tasks are retried when arbitrary connection errors occur."""
        
        from mock import Mock
        from pyramid.request import Request
        from requests.exceptions import RequestException
        from threading import Event
        flag = Event()
        flag.set()
        
        from torque.model import TASK_STATUSES
        from torque.model import CreateTask
        from torque.model import Session
        from torque.work.perform import TaskPerformer
        
        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask()
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, req)
            instruction = '{0}:0'.format(task.id)
        
        # Instantiate a performer with the requests.post method mocked
        # to raise a connection error.
        mock_post = Mock()
        mock_post.side_effect = RequestException()
        performer = TaskPerformer(post=mock_post)
        
        # The task should be pending a retry.
        status = performer(instruction, flag)
        self.assertTrue(status is TASK_STATUSES[u'pending'])
    
    def test_performing_task_server_error(self):
        """Tasks are retried when internal server errors occur."""
        
        from mock import Mock
        from pyramid.request import Request
        from threading import Event
        flag = Event()
        flag.set()
        
        from torque.model import TASK_STATUSES
        from torque.model import CreateTask
        from torque.model import Session
        from torque.work.perform import TaskPerformer
        
        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask()
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, req)
            instruction = '{0}:0'.format(task.id)
        
        # Instantiate a performer with the requests.post method mocked
        # to raise a connection error.
        mock_post = Mock()
        mock_post.return_value.status_code = 500
        performer = TaskPerformer(post=mock_post)
        
        # The task should be pending a retry.
        status = performer(instruction, flag)
        self.assertTrue(status is TASK_STATUSES[u'pending'])
    
    def test_performing_task_bad_request(self):
        """Tasks are failed when invalid."""
        
        from mock import Mock
        from pyramid.request import Request
        from threading import Event
        flag = Event()
        flag.set()
        
        from torque.model import TASK_STATUSES
        from torque.model import CreateTask
        from torque.model import Session
        from torque.work.perform import TaskPerformer
        
        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask()
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, req)
            instruction = '{0}:0'.format(task.id)
        
        # Instantiate a performer with the requests.post method mocked
        # to raise a connection error.
        mock_post = Mock()
        mock_post.return_value.status_code = 400
        performer = TaskPerformer(post=mock_post)
        
        # The task should be pending a retry.
        status = performer(instruction, flag)
        self.assertTrue(status is TASK_STATUSES[u'failed'])
    
    def test_performing_task_waits(self):
        """Performing a task exponentially backs off polling the greenlet
          to see whether it has completed.
        """
        
        from gevent import sleep
        from mock import Mock
        from pyramid.request import Request
        from threading import Event
        flag = Event()
        flag.set()
        
        from torque.model import TASK_STATUSES
        from torque.model import CreateTask
        from torque.model import Session
        from torque.work.perform import TaskPerformer
        
        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask()
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, req)
            instruction = '{0}:0'.format(task.id)
        
        # Instantiate a performer with the requests.post method mocked
        # to take 0.6 seconds to return 200.
        def mock_post(*args, **kwargs):
            sleep(0.4)
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response
        
        # And the sleep method mocked so we can check its calls.
        counter = Mock()
        def mock_sleep(delay):
            counter(delay)
            sleep(delay)
        
        performer = TaskPerformer(post=mock_post, sleep=mock_sleep)
        status = performer(instruction, flag)
        self.assertTrue(status is TASK_STATUSES[u'completed'])
        
        # And gevent.sleep was called with exponential backoff.
        self.assertTrue(0.1499 < counter.call_args_list[1][0][0] < 0.1501)
        self.assertTrue(0.2249 < counter.call_args_list[2][0][0] < 0.2251)
    

