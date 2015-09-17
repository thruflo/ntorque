# -*- coding: utf-8 -*-

"""Provides business logic to read and write data using the ORM."""

__all__ = [
    'CreateApplication',
    'CreateTask',
    'DeleteOldTasks',
    'GetActiveKey',
    'GetDueTasks',
    'LookupApplication',
    'LookupTask',
    'PushTaskNotification',
    'TaskFactory',
    'TaskManager',
]

import logging
logger = logging.getLogger(__name__)

import json
import transaction

from datetime import datetime

from pyramid.security import ALL_PERMISSIONS
from pyramid.security import Allow, Deny
from pyramid.security import Authenticated, Everyone

from pyramid_weblayer import tx

from . import constants as c
from . import due
from . import orm as model

class CreateApplication(object):
    """Create an application."""

    def __init__(self, **kwargs):
        self.app_cls = kwargs.get('app_cls', model.Application)
        self.key_cls = kwargs.get('key_cls', model.APIKey)
        self.session = kwargs.get('session', model.Session)

    def __call__(self, name):
        """Create a named application with an auto-generated api_key."""

        key = self.key_cls()
        app = self.app_cls(name=name, api_keys=[key])
        self.session.add(app)
        self.session.flush()
        return app


class CreateTask(object):
    """Create a task from a ``request`` and call ``*args``."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.factory_cls = kwargs.get('factory_cls', TaskFactory)
        self.default_charset = kwargs.get('default_charset', c.DEFAULT_CHARSET)
        self.default_enctype = kwargs.get('default_enctype', c.DEFAULT_ENCTYPE)
        self.header_prefix = kwargs.get('header_prefix', c.PROXY_HEADER_PREFIX)

    def __call__(self, application, url, timeout, method):
        """Unpack ``enctype, body and headers`` from the request and then
          pass through as args to the underlying ``CreateTask`` factory.
        """

        # Get the content type and parse the encoding type out of it.
        request = self.request
        content_type = request.headers.get('Content-Type', None)
        if not content_type:
            enctype = self.default_enctype
        else: # Extract just the enctype and decode to unicode.
            enctype = content_type.split(';')[0].decode('utf8')

        # Get the charset.
        charset = request.charset
        charset = charset.decode('utf8') if charset else self.default_charset

        # Use it to decode the body to a unicode string.
        body = request.body.decode(charset)

        # Extract any headers to pass through.
        headers = {}
        for key, value in request.headers.items():
            if key.lower().startswith(self.header_prefix.lower()):
                k = key[len(self.header_prefix):]
                headers[k] = value

        # Use the underlying factory to create the task.
        factory = self.factory_cls(application, url, timeout, method)
        return factory(body=body, charset=charset, enctype=enctype, headers=headers)

class TaskFactory(object):
    """Create and store a task."""

    def __init__(self, app, url, timeout, method, **kwargs):
        self.app = app
        self.url = url
        self.timeout = timeout
        self.method = method
        self.task_cls = kwargs.get('task_cls', model.Task)
        self.session = kwargs.get('session', model.Session)

    def __call__(self, body=u'', headers=None, **kwargs):
        """Create and return a task."""

        # Unpack.
        app = self.app
        url = self.url
        timeout = self.timeout
        method = self.method

        # Jsonify the headers.
        if headers is None:
            headers = {}
        headers_json = json.dumps(headers)

        # Accept either app or app_id.
        if app is not None:
            if getattr(app, 'id', None):
                kwargs['app'] = app
            elif isinstance(app, int):
                kwargs['app_id'] = app

        # Create.
        task = self.task_cls(body=body, headers=headers_json,
                method=method, timeout=timeout, url=url, **kwargs)

        # Save, flush and return.
        self.session.add(task)
        self.session.flush()
        return task

class PushTaskNotification(object):
    """Add a transaction commit hook to push a task onto the redis channel."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.join_tx = kwargs.get('join_tx', tx.join_to_transaction)

    def __call__(self, task):
        """Prepare instruction and add to channel on tx commit."""

        # Unpack.
        request = self.request
        settings = request.registry.settings

        # Prepare instruction.
        instruction = '{0}:{1}'.format(task.id, task.retry_count)

        # Push onto the queue when the current transaction commits.
        channel = settings['ntorque.redis_channel']
        self.join_tx(request.redis.rpush, channel, instruction)


class GetActiveKey(object):
    """Lookup an application's active ``api_key``."""

    def __init__(self, **kwargs):
        self.key_cls = kwargs.get('key_cls', model.APIKey)

    def __call__(self, app):
        """Return the first active key for the ``app`` provided."""

        # Unpack.
        key_cls = self.key_cls

        # Query active keys.
        query = key_cls.query.filter(*key_cls.active_clauses())

        # Belonging to this app.
        query = query.filter(key_cls.app==app)

        # Matching the value provided.
        return query.first()


class GetActiveKeyValues(object):
    """Lookup all the active ``api_key`` values's for an application."""

    def __init__(self, **kwargs):
        self.key_cls = kwargs.get('key_cls', model.APIKey)
        self.session = kwargs.get('session', model.Session)

    def __call__(self, app):
        """Return all the active key values for the ``app`` provided."""

        # Unpack.
        key_cls = self.key_cls

        # Query active key values.
        query = self.session.query(key_cls.value)
        query = query.filter(*key_cls.active_clauses())

        # Belonging to this app.
        query = query.filter(key_cls.app==app)
        return [item[0] for item in query]



class GetDueTasks(object):
    """Get tasks that are due and pending."""

    def __init__(self, **kwargs):
        self.utcnow = kwargs.get('utcnow', datetime.utcnow)
        self.statuses = kwargs.get('statuses', c.TASK_STATUSES)
        self.task_cls = kwargs.get('task_cls', model.Task)

    def __call__(self, limit=99, offset=0):
        """Get the tasks."""

        # Unpack.
        model_cls = self.task_cls
        now = self.utcnow()
        status = self.statuses['pending']

        # Build the query.
        query = model_cls.query.filter(model_cls.status==status)
        query = query.filter(model_cls.due<self.utcnow())

        # Batch.
        query = query.offset(offset).limit(limit)

        # Return the results.
        return query.all()


class DeleteOldTasks(object):
    """Delete tasks last modified more than a time delta ago."""

    def __init__(self, **kwargs):
        self.utcnow = kwargs.get('utcnow', datetime.utcnow)
        self.task_cls = kwargs.get('task_cls', model.Task)

    def __call__(self, delta):
        """Build a query and call a bulk delete."""

        # Unpack.
        model_cls = self.task_cls
        delta_ago = self.utcnow() - delta

        # Build the query.
        query = model_cls.query.filter(model_cls.modified<delta_ago)
        with transaction.manager:
            num_deleted = query.delete()
        return num_deleted



class LookupApplication(object):
    """Lookup an application by ``api_key``."""

    def __init__(self, **kwargs):
        self.app_cls = kwargs.get('app_cls', model.Application)
        self.key_cls = kwargs.get('key_cls', model.APIKey)

    def __call__(self, api_key):
        """Query active applications which have an active api key matching the
          value provided.
        """

        # Unpack.
        app_cls = self.app_cls
        key_cls = self.key_cls

        # Query active applications.
        query = app_cls.query.filter(*app_cls.active_clauses())

        # With an active api key.
        query = query.join(key_cls, key_cls.app_id==app_cls.id)
        query = query.filter(*key_cls.active_clauses())

        # Matching the value provided.
        query = query.filter(key_cls.value==api_key)
        return query.first()


class LookupTask(object):
    """Lookup a task by ``id``."""

    def __init__(self, **kwargs):
        self.patch_acl = kwargs.get('patch_acl', PatchTaskACL())
        self.task_cls = kwargs.get('task_cls', model.Task)

    def __call__(self, id_):
        """Get the task. If it exists, patch its ACL."""

        task = self.task_cls.query.get(id_)
        if task:
            self.patch_acl(task)
        return task


class PatchTaskACL(object):
    def __init__(self, **kwargs):
        self.get_keys = kwargs.get('get_keys', GetActiveKeyValues())

    def __call__(self, task):
        """If the ACL is NotImplemented, implement it."""

        # Exit if already patched.
        if task.__acl__ is not NotImplemented:
            return

        # Start off denying access.
        rules = [(Deny, Everyone, ALL_PERMISSIONS),]

        # And then grant access to ``task.app``.
        if task.app:
            for api_key in self.get_keys(task.app):
                rule = (Allow, api_key, ALL_PERMISSIONS)
                rules.insert(0, rule)

        # Set the ACL to the rules list.
        task.__acl__ = rules



class TaskManager(object):
    """Provide methods to ``acquire`` a task and then ``reschedule``,
      ``complete`` or ``fail`` it.

      Encapsulates the ``task_data`` returned from ``__json__()``ing the
      instance returned from the ``acquire`` query and uses this data to
      update the right task with the right values when setting the status.
    """

    def __init__(self, **kwargs):
        self.due_factory = kwargs.get('due_factory', due.DueFactory())
        self.session = kwargs.get('session', model.Session)
        self.statuses = kwargs.get('statuses', c.TASK_STATUSES)
        self.task_cls = kwargs.get('task_cls', model.Task)
        self.tx_manager = kwargs.get('tx_manager', transaction.manager)

    def _update(self, **values):
        """Consistent logic to update the task. Note that it includes
          the retry_count and timeout as these are used by the onupdate
          functions and thus need to be in the sqlalchemy execution
          context's current params.
        """

        # Unpack.
        retry_count = self.task_data['retry_count']
        timeout = self.task_data['timeout']

        # Merge the values with a consistent values dict.
        values_dict = {
            'retry_count': retry_count,
            'timeout': timeout,
        }
        values_dict.update(values)
        query = self.task_cls.query.filter_by(id=self.task_id,
                retry_count=retry_count)
        with self.tx_manager:
            query.update(values_dict)

    def acquire(self, id_, retry_count):
        """Get a task by ``id`` and ``retry_count``, transactionally setting the
          status to ``in_progress`` and incrementing the ``retry_count``.
        """

        self.task_id = id_
        self.task_data = None
        query = self.task_cls.query
        query = query.filter_by(id=id_, retry_count=retry_count)
        with self.tx_manager:
            task = query.first()
            if task:
                task.retry_count = retry_count + 1
                self.session.add(task)
                self.task_data = task.__json__(include_request_data=True)
        return self.task_data

    def reschedule(self):
        """Reschedule a task by setting the due date -- does the same as the
          default / onupdate machinery but with a timeout of 0.
        """

        retry_count = self.task_data['retry_count']
        self._update(due=self.due_factory(0, retry_count))
        return self.statuses['pending']

    def complete(self):
        """Flag a task as completed."""

        status = self.statuses['completed']
        self._update(status=status)
        return status

    def fail(self):
        """Flag a task as failed."""

        status = self.statuses['failed']
        self._update(status=status)
        return status


