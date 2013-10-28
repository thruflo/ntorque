# -*- coding: utf-8 -*-

"""Shared constant values."""

__all__ = [
    'DEFAULT_CHARSET',
    'DEFAULT_ENCTYPE',
    'TASK_STATUSES',
]

DEFAULT_CHARSET = u'utf8'
DEFAULT_ENCTYPE = u'application/x-www-form-urlencoded'

TASK_STATUSES = {
    'pending': u'pending', 
    'completed': u'completed',
}
