# -*- coding: utf-8 -*-

"""Base traversal root."""

__all__ = [
    'TraversalRoot',
]

import logging
logger = logging.getLogger(__name__)

from zope.interface import alsoProvides
from zope.interface import implementer

from pyramid.interfaces import ILocation

from pyramid.security import ALL_PERMISSIONS
from pyramid.security import Allow, Deny
from pyramid.security import Authenticated, Everyone

@implementer(ILocation)
class TraversalRoot(object):
    """Traversal boilerplate and a base access control policy."""

    __acl__ = [
        (Allow, Authenticated, ALL_PERMISSIONS),
        (Deny, Everyone, ALL_PERMISSIONS),
    ]
    __name__ = ''
    __parent__ = None

    def __init__(self, request, key='', parent=None, **kwargs):
        self.request = request
        self.__name__ = key
        self.__parent__ = parent
        self.alsoProvides = kwargs.get('alsoProvides', alsoProvides)

    def locatable(self, context, key):
        """Make a context object locatable and return it."""

        if not hasattr(context, '__name__'):
            context.__name__ = key
        context.__parent__ = self
        context.request = self.request
        if not ILocation.providedBy(context):
            self.alsoProvides(context, ILocation)
        return context


