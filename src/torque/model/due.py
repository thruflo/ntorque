# -*- coding: utf-8 -*-

"""Provides core logic to auto-generate task status and due date based on the
  task's retry count.
"""

__all__ = [
    'DueFactory',
    'StatusFactory',
]

import logging
logger = logging.getLogger(__name__)

import datetime
import os
import transaction

from torque import backoff
from . import constants

DEFAULT_SETTINGS = {
    'min_delay': os.environ.get('TORQUE_MIN_DUE_DELAY', 1),
    'max_delay': os.environ.get('TORQUE_MAX_DUE_DELAY', 7200),
    'max_retries': os.environ.get('TORQUE_MAX_RETRIES', 36),
}

class DueFactory(object):
    """Simple callable that uses the current datetime and a task's timeout,
      and retry count to generate a future datetime when the task should
      be retried.
    """
    
    def __init__(self, **kwargs):
        self.backoff_cls = kwargs.get('backoff', backoff.Backoff)
        self.datetime = kwargs.get('datetime', datetime.datetime)
        self.timedelta = kwargs.get('timedelta', datetime.timedelta)
        self.settings = kwargs.get('settings', DEFAULT_SETTINGS)
    
    def __call__(self, timeout, retry_count):
        """Return a datetime instance ``timeout + 1`` seconds in the future,
          plus, if there's a retry count, generate additional seconds into
          the future using an exponential backoff algorithm.
        """
        
        # Unpack.
        min_delay = self.settings.get('min_delay')
        max_delay = self.settings.get('max_delay')
        
        # Use the ``retry_count`` to exponentially backoff from the ``min_delay``.
        backoff = self.backoff_cls(min_delay)
        for i in range(retry_count):
            backoff.exponential(2) # 1, 2, 4, 8, 16, 32, 64, 128 seconds ...
        
        # Add the timeout and limit at the ``max_delay``.
        delay = backoff.value + timeout
        if delay > max_delay:
            delay = max_delay
        
        # Generate a datetime ``delay`` seconds in the future.
        return self.datetime.utcnow() + self.timedelta(seconds=delay)
    

class StatusFactory(object):
    """Simple callable that uses a retry count to choose a task status."""
    
    def __init__(self, **kwargs):
        self.settings = kwargs.get('defaults', DEFAULT_SETTINGS)
        self.statuses = kwargs.get('statuses', constants.TASK_STATUSES)
    
    def __call__(self, retry_count):
        """Return a datetime instance ``timeout + 1`` seconds in the future,
          plus, if there's a retry count, generate additional seconds into
          the future using an exponential backoff algorithm.
        """
        
        key = 'pending'
        if retry_count > self.settings.get('max_retries'):
            key = 'completed'
        return self.statuses[key]
    

