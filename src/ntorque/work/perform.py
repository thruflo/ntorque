# -*- coding: utf-8 -*-

"""Provides ``TaskPerformer``, a utility that aquires a task from the db,
  and performs it by making a POST request to the task's web hook url.
"""

__all__ = [
    'TaskPerformer',
]

from . import patch
patch.green_threads()

import logging
logger = logging.getLogger(__name__)

import gevent
import requests
import socket
import os

from requests.exceptions import RequestException
from sqlalchemy.exc import SQLAlchemyError

from ntorque import backoff
from ntorque import model

# Configurable transient request errors.
TRANSIENT_REQUEST_ERRORS = os.environ.get('NTORQUE_TRANSIENT_REQUEST_ERRORS',
                                                '408,423,429,449')

class MakeRequest(object):
    """Wrap ``requests.request`` with some instrumentation."""

    def __init__(self, **kwargs):
        self.log = kwargs.get('log', logger)
        self.make_request = kwargs.get('make_request', requests.request)
        self.request_exc = kwargs.get('request_exc', RequestException)
        self.sock_timeout = kwargs.get('sock_timeout', socket.timeout)

    def __call__(self, *args, **kwargs):
        """Make the request and log at the appropriate level for the response."""

        # Prepare
        error = None
        response = None

        # Try and make the request.
        try:
            response = self.make_request(*args, **kwargs)
        except (self.request_exc, self.sock_timeout) as err:
            error = err
        else:
            try:
                response.raise_for_status()
            except self.request_exc as err:
                error = err

        # Log appropriately.
        key = u'torque.work.perform.request'
        if error:
            self.log.warn((key, args, kwargs))
            self.log.warn(error)
            if response:
                self.log.warn(response.status_code)
                self.log.info(response.text)
        else:
            self.log.debug((key, args, kwargs, response.status_code))

        return response

class TaskPerformer(object):
    """Utility that acquires and performs a task by making an HTTP request."""

    def __init__(self, **kwargs):
        self.log = kwargs.get('log', logger)
        self.task_manager_cls = kwargs.get('task_manager_cls', model.TaskManager)
        self.backoff_cls = kwargs.get('backoff', backoff.Backoff)
        self.make_request = kwargs.get('make_request', MakeRequest())
        self.session = kwargs.get('session', model.Session)
        self.sleep = kwargs.get('sleep', gevent.sleep)
        self.spawn = kwargs.get('spawn', gevent.spawn)
        self.transient_errors = kwargs.get('transient_errors',TRANSIENT_REQUEST_ERRORS)

    def __call__(self, instruction, control_flag):
        """Perform a task and close any db connections."""

        try:
            return self.perform(instruction, control_flag)
        finally:
            self.session.remove()

    def perform(self, instruction, control_flag):
        """Acquire a task, perform it and update its status accordingly."""

        # Unpack http codes and transform into an int list.
        http_transient_request_errors = map(int, self.transient_errors.split(','))

        # Parse the instruction to transactionally
        # get-the-task-and-incr-its-retry-count. This ensures that even if the
        # next instruction off the queue is for the same task, or if a parallel
        # worker has the same instruction, the task will only be acquired once.
        task_data = None
        task_manager = self.task_manager_cls()
        task_id, retry_count = map(int, instruction.split(':'))
        try:
            task_data = task_manager.acquire(task_id, retry_count)
        except SQLAlchemyError as err:
            logger.warn(err)
        if not task_data:
            return

        # Unpack the task data.
        url = task_data['url']
        body = task_data['body']
        timeout = task_data['timeout']
        headers = task_data['headers']
        headers['content-type'] = '{0}; charset={1}'.format(
                task_data['enctype'], task_data['charset'])
        headers['ntorque-task-id'] = task_id
        headers['ntorque-task-retry-count'] = retry_count
        max_retries = task_manager.due_factory.settings['max_retries']
        headers['ntorque-task-retry-limit'] = max_retries
        method = task_data['method']

        # Spawn a POST to the web hook in a greenlet -- so we can monitor
        # the control flag in case we want to exit whilst waiting.
        kwargs = dict(data=body, headers=headers, timeout=timeout)
        greenlet = self.spawn(self.make_request, method, url, **kwargs)

        # Wait for the request to complete, checking the greenlet's progress
        # with an expoential backoff.
        response = None
        delay = 0.1 # secs
        max_delay = 2 # secs - XXX really this should be the configurable
                      # min delay in the due logic's `timeout + min delay`.
                      # The issue being that we could end up checking the
                      # ready max delay after the timout, which means that
                      # the task is likely to be re-queued already.
        backoff = self.backoff_cls(delay, max_value=max_delay)
        while control_flag.is_set():
            self.sleep(delay)
            if greenlet.ready():
                response = greenlet.value
                break
            delay = backoff.exponential(1.5) # 0.15, 0.225, 0.3375, ... 2

        # If we didn't get a response, or if the response was not successful,
        # reschedule it. Note that rescheduling *accelerates* the due date --
        # doing nothing here would leave the task to be retried anyway, as its
        # due date was set when the task was aquired.
        if response is None:
            code = 500
        else:
            code = response.status_code
        if code < 202:
            status = task_manager.complete()
        elif code > 499 or code in http_transient_request_errors:
            # XXX what we could also do here are:
            # - set a more informative status flag (even if only descriptive)
            # - noop if the greenlet request timed out
            status = task_manager.reschedule()
        else:
            status = task_manager.fail()

        # Logging to be possible to follow events in production.
        self.log.warn(
            ('NTORQUE Task info',
                'status', status,
                'url', url,
                'code', code,
                'headers', headers,
                'body', body,
            ))
        return status
