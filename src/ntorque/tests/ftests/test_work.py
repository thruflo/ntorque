# -*- coding: utf-8 -*-

"""Functional tests for the ``ntorque.work`` package."""

import logging
logger = logging.getLogger(__name__)

import json
import transaction
import urllib
import unittest

from ntorque.tests import boilerplate

class TestChannelConsumer(unittest.TestCase):
    """Test consuming instructions from the redis channel."""

    def setUp(self):
        self.config_factory = boilerplate.TestConfigFactory()
        self.registry = self.config_factory().registry

    def tearDown(self):
        self.config_factory.drop()

    #def test_foo(self):
    #    """XXX"""
    #
    #    self.assertTrue('foo' == 'foo')


class TestTaskPerformer(unittest.TestCase):
    """Test performing tasks."""

    def setUp(self):
        self.config_factory = boilerplate.TestConfigFactory()
        self.registry = self.config_factory().registry

    def tearDown(self):
        self.config_factory.drop()

    def test_performing_task_miss(self):
        """Performing a task that doesn't exist returns None."""

        from ntorque.work.perform import TaskPerformer
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

        from ntorque.model import TASK_STATUSES
        from ntorque.model import CreateTask
        from ntorque.model import Session
        from ntorque.work.perform import TaskPerformer

        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'POST')
            instruction = '{0}:0'.format(task.id)

        # Instantiate a performer with the requests.post method mocked
        # to return 200 without making a request.
        mock_make_request = Mock()
        mock_make_request.return_value.status_code = 200
        performer = TaskPerformer(make_request=mock_make_request)

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

        from ntorque.model import TASK_STATUSES
        from ntorque.model import CreateTask
        from ntorque.model import Session
        from ntorque.work.perform import TaskPerformer

        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'POST')
            instruction = '{0}:0'.format(task.id)

        # Instantiate a performer with the requests.post method mocked
        # to raise a connection error.
        mock_make_request = Mock()
        mock_make_request.side_effect = RequestException()
        performer = TaskPerformer(make_request=mock_make_request)

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

        from ntorque.model import TASK_STATUSES
        from ntorque.model import CreateTask
        from ntorque.model import Session
        from ntorque.work.perform import TaskPerformer

        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'POST')
            instruction = '{0}:0'.format(task.id)

        # Instantiate a performer with the requests.post method mocked
        # to raise a connection error.
        mock_make_request = Mock()
        mock_make_request.return_value.status_code = 500
        performer = TaskPerformer(make_request=mock_make_request)

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

        from ntorque.model import TASK_STATUSES
        from ntorque.model import CreateTask
        from ntorque.model import Session
        from ntorque.work.perform import TaskPerformer

        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'POST')
            instruction = '{0}:0'.format(task.id)

        # Instantiate a performer with the requests.post method mocked
        # to raise a connection error.
        mock_make_request = Mock()
        mock_make_request.return_value.status_code = 400
        performer = TaskPerformer(make_request=mock_make_request)

        # The task should have failed status.
        status = performer(instruction, flag)
        self.assertTrue(status is TASK_STATUSES[u'failed'])

    def test_performing_tasks_different_http_status_codes(self):
        """Tasks should behave according to status codes in transient_errors."""

        from mock import Mock
        from pyramid.request import Request
        from threading import Event
        flag = Event()
        flag.set()

        from ntorque.model import TASK_STATUSES
        from ntorque.model import CreateTask
        from ntorque.model import Session
        from ntorque.work.perform import TaskPerformer

        # Create two tasks.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task_one = create_task(None, 'http://example.com', 20, u'POST')
            instruction_one = '{0}:0'.format(task_one.id)
            task_two = create_task(None, 'http://example.com', 20, u'POST')
            instruction_two = '{0}:0'.format(task_two.id)

        # Instantiate a performer with the requests.post method mocked
        # to raise a connection error.
        mock_make_request = Mock()
        mock_make_request.return_value.status_code = 400
        performer = TaskPerformer(make_request=mock_make_request)

        # The task should have failed status.
        status = performer(instruction_one, flag)
        self.assertTrue(status is TASK_STATUSES[u'failed'])

        # Now let's instantiate a performer with 400 as a transient code.
        performer = TaskPerformer(make_request=mock_make_request,
                                  transient_errors='400')

        # Now the task should be pending a retry.
        status = performer(instruction_two, flag)
        self.assertTrue(status is TASK_STATUSES[u'pending'])

    def test_performing_task_with_method(self):
        """Tasks are performed using the stored method."""

        from mock import Mock
        from pyramid.request import Request
        from threading import Event
        flag = Event()
        flag.set()

        from ntorque.model import CreateTask
        from ntorque.work.perform import TaskPerformer

        # Create a POST task.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'POST')
            instruction = '{0}:0'.format(task.id)
        # Perform it.
        mock_make_request = Mock()
        performer = TaskPerformer(make_request=mock_make_request)
        performer(instruction, flag)
        # Assert that make_request was called with 'POST'
        self.assertTrue(mock_make_request.call_args_list[0][0][0] == u'POST')

        # Now provide a non-default method.
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'PUT')
            instruction = '{0}:0'.format(task.id)
        mock_make_request = Mock()
        performer = TaskPerformer(make_request=mock_make_request)
        performer(instruction, flag)
        self.assertTrue(mock_make_request.call_args_list[0][0][0] == u'PUT')

    def test_performing_task_adds_ntorque_task_headers(self):
        """Task requests have ntorque-task-* headers."""

        from mock import Mock
        from pyramid.request import Request
        from threading import Event
        flag = Event()
        flag.set()

        from ntorque.model import CreateTask
        from ntorque.work.perform import TaskPerformer

        # Create a POST task.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'POST')
            instruction = '{0}:0'.format(task.id)

        # Perform it.
        mock_make_request = Mock()
        performer = TaskPerformer(make_request=mock_make_request)
        performer(instruction, flag)

        # Assert that make_request was called with the ntorque-task-* headers.
        keys = (
            u'ntorque-task-id',
            u'ntorque-task-retry-count',
            u'ntorque-task-retry-limit',
        )
        headers = mock_make_request.call_args_list[0][1].get('headers', {})
        for item in keys:
            self.assertTrue(headers.has_key(item))

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

        from ntorque.model import TASK_STATUSES
        from ntorque.model import CreateTask
        from ntorque.model import Session
        from ntorque.work.perform import TaskPerformer

        # Create a task.
        req = Request.blank('/')
        create_task = CreateTask(req)
        with transaction.manager:
            task = create_task(None, 'http://example.com', 20, u'POST')
            instruction = '{0}:0'.format(task.id)

        # Instantiate a performer with the requests.post method mocked
        # to take 0.4 seconds to return 200.
        def mock_make_request(*args, **kwargs):
            sleep(0.4)
            mock_response = Mock()
            mock_response.status_code = 200
            return mock_response

        # And the sleep method mocked so we can check its calls.
        counter = Mock()
        def mock_sleep(delay):
            counter(delay)
            sleep(delay)

        performer = TaskPerformer(make_request=mock_make_request, sleep=mock_sleep)
        status = performer(instruction, flag)
        self.assertTrue(status is TASK_STATUSES[u'completed'])

        # And gevent.sleep was called with exponential backoff.
        self.assertTrue(0.1499 < counter.call_args_list[1][0][0] < 0.1501)
        self.assertTrue(0.2249 < counter.call_args_list[2][0][0] < 0.2251)
