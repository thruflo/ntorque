# -*- coding: utf-8 -*-

"""Provides declarative SQLAlchemy ORM classes."""

__all__ = [
    'APIKey',
    'Application',
    'Base',
    'DEFAULT_CHARSET',
    'DEFAULT_ENCTYPE',
    'Session',
    'Task',
]

import logging
logger = logging.getLogger(__name__)

from datetime import datetime

from zope.sqlalchemy import ZopeTransactionExtension

from sqlalchemy import orm
from sqlalchemy.ext import declarative

from sqlalchemy.schema import Column
from sqlalchemy.schema import Index
from sqlalchemy.schema import ForeignKey

from sqlalchemy.types import Boolean
from sqlalchemy.types import DateTime
from sqlalchemy.types import Enum
from sqlalchemy.types import Integer
from sqlalchemy.types import Unicode
from sqlalchemy.types import UnicodeText

from torque import root
faux_root = lambda **kwargs: root.TraversalRoot(None, **kwargs)

from torque import util
generate_api_key = lambda: util.generate_random_digest(num_bytes=20)

Session = orm.scoped_session(orm.sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative.declarative_base()

TASK_STATUSES = [
    u'pending', 
    u'in_progress', 
    u'retry', 
    u'completed'
]

DEFAULT_CHARSET = u'utf8'
DEFAULT_ENCTYPE = u'application/x-www-form-urlencoded'

class BaseMixin(object):
    """Provides an int ``id`` as primary key, ``version``, ``created`` and
      ``modified`` columns and a scoped ``self.query`` property.
    """
    
    id = Column(Integer, primary_key=True)
    created = Column('c', DateTime, default=datetime.utcnow, nullable=False)
    modified = Column('m', DateTime, default=datetime.utcnow, nullable=False,
            onupdate=datetime.utcnow)
    version = Column('v', Integer, default=1, nullable=False)
    
    query = Session.query_property()

class LifeCycleMixin(object):
    """Provide life cycle flags for `is_active`` and ``is_deleted``."""
    
    # Flags.
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    @classmethod
    def active_clauses(cls):
        return cls.is_active==True, cls.is_deleted==False
    
    
    # Datetimes to record when the actions occured.
    activated = Column(DateTime)
    deactivated = Column(DateTime)
    deleted = Column(DateTime)
    undeleted = Column(DateTime)
    
    def _set_life_cycle_state(self, flag_name, flag_value, dt_name, now=None):
        """Shared logic to set a flag and its datetime record."""
        
        # Compose.
        if now is None:
            now = datetime.utcnow
        
        # Get the flag value.
        stored_value = getattr(self, flag_name)
        
        # Set the flag.
        setattr(self, flag_name, flag_value)
        
        # If it changed, then record when.
        if stored_value != flag_value:
            setattr(self, dt_name, now())
            identifier = getattr(self, 'slug', getattr(self, 'id', None))
            logger.debug(('Lifecycle', dt_name, self, identifier))
    
    
    # API.
    def activate(self):
        self._set_life_cycle_state('is_active', True, 'activated')
    
    def deactivate(self):
        self._set_life_cycle_state('is_active', False, 'deactivated')
    
    def delete(self):
        self._set_life_cycle_state('is_deleted', True, 'deleted')
    
    def undelete(self):
        self._set_life_cycle_state('is_deleted', False, 'undeleted')
    


class Application(Base, BaseMixin, LifeCycleMixin):
    """Encapsulate an application."""
    
    __tablename__ = 'applications'
    
    name = Column(Unicode(96), nullable=False)


class APIKey(Base, BaseMixin, LifeCycleMixin):
    """Encapsulate an api key used to authenticate an application."""
    
    __tablename__ = 'api_keys'
    __table_args__ = (
        Index('ix_api_keys', 'is_active', 'is_deleted', 'value'),
    )
    
    # Belongs to an ``Application``.
    app_id = Column(Integer, ForeignKey('applications.id'), nullable=False)
    app = orm.relationship(Application, backref=orm.backref('api_keys',
            cascade="all, delete-orphan", single_parent=True))
    
    # Has a unique, randomly generated value.
    value = Column(Unicode(40), default=generate_api_key, nullable=False,
            unique=True)

class Task(Base, BaseMixin):
    """Encapsulate a task."""
    
    __tablename__ = 'tasks'
    
    # Implemented during traversal to grant ``self.app`` access.
    __acl__ = NotImplemented
    
    # Faux root allows us to generate urls with request.resource_url, even
    # when tasks aren't looked up using traversal.
    __parent__ = faux_root(key='tasks', parent=faux_root())
    
    @property
    def __name__(self):
        return self.id
    
    
    # Can belong to an ``Application``.
    app_id = Column(Integer, ForeignKey('applications.id'))
    app = orm.relationship(Application, backref=orm.backref('tasks',
            cascade="all, delete-orphan", single_parent=True))
    
    # Has a pre-defined status.
    status = Column(Enum(*TASK_STATUSES, name='task_statuses'),
            default=u'pending', index=True, nullable=False)
    
    # When should the task be executed / retried?
    due = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # The web hook url and POST body with charset and content type. Note that
    # the data is decoded from the charset to unicode.
    url = Column(Unicode(256), nullable=False)
    charset = Column(Unicode(24), default=DEFAULT_CHARSET, nullable=False)
    enctype = Column(Unicode(256), default=DEFAULT_ENCTYPE, nullable=False)
    body = Column(UnicodeText)
    
    def __json__(self, request=None):
        return {
            'id': self.id,
            'status': self.status,
            'url': self.url,
        }
    

