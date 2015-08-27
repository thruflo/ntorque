# -*- coding: utf-8 -*-

"""Support Pyramid traversal to ``/tasks/:task_id``."""

__all__ = [
    'APIRoot',
    'TaskRoot',
]

import logging
logger = logging.getLogger(__name__)

import re
VALID_INT = re.compile(r'^[0-9]+$')

from ntorque import model
from ntorque import root

class APIRoot(root.TraversalRoot):
    """Support ``tasks`` traversal."""

    def __init__(self, *args, **kwargs):
        super(APIRoot, self).__init__(*args, **kwargs)
        self.tasks_root = kwargs.get('tasks_root', TaskRoot)

    def __getitem__(self, key):
        if key == 'tasks':
            return self.tasks_root(self.request, key=key, parent=self)
        raise KeyError(key)


class TaskRoot(root.TraversalRoot):
    """Lookup tasks by ID."""

    def __init__(self, *args, **kwargs):
        super(TaskRoot, self).__init__(*args, **kwargs)
        self.get_task = kwargs.get('get_task', model.LookupTask())
        self.valid_id = kwargs.get('valid_id', VALID_INT)

    def __getitem__(self, key):
        """Lookup task by ID and, if found, make sure the task is locatable."""

        if self.valid_id.match(key):
            int_id = int(key)
            context = self.get_task(int_id)
            if context:
                return self.locatable(context, key)
        raise KeyError(key)


