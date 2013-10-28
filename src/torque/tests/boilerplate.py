# -*- coding: utf-8 -*-

"""Provide a consistent factory to make the WSGI app to be tested."""

__all__ = [
    'TestAppFactory',
    'TestRegFactory',
]

try:
    import webtest
except ImportError: #pragma: no cover
    pass

from torque import api
from torque import model
from torque.work import main as work

from pyramid_redis import hooks as redis_hooks

TEST_SETTINGS = {
    'redis.db': 5,
    'redis.url': 'redis://localhost:6379',
    'sqlalchemy.url': u'postgresql:///torque_test',
    'torque.mode': 'testing',
    'torque.redis_channel': 'torque:testing',
}

class TestAppFactory(object):
    """Callable utility that returns a testable WSGI app and manages db state."""
    
    def __init__(self, **kwargs):
        self.app_factory = kwargs.get('app_factory', api.wsgi_app_factory)
        self.base = kwargs.get('base', model.Base)
        self.json_method = kwargs.get('get_json', webtest.utils.json_method)
        self.redis_factory = kwargs.get('redis_factory', redis_hooks.RedisFactory())
        self.session = kwargs.get('session', model.Session)
        self.test_app = kwargs.get('test_app', webtest.TestApp)
        self.test_settings = kwargs.get('test_settings', TEST_SETTINGS)
        self.has_created = False
    
    def __call__(self, **kwargs):
        """Create the WSGI app and wrap it with a patched webtest.TestApp."""
        
        # Patch TestApp.
        self.test_app.get_json = self.json_method('GET')
        
        # Instantiate.
        self.settings = self.test_settings.copy()
        self.settings.update(kwargs)
        app = self.app_factory(settings=self.settings)
        
        # Create the db.
        self.create()
        
        # Wrap and return.
        return self.test_app(app)
    
    def create(self):
        engine = self.session.get_bind()
        self.base.metadata.create_all(engine)
        self.redis_client = self.redis_factory(self.settings)
        self.has_created = True
        self.session.remove()
    
    def drop(self):
        if self.has_created:
            engine = self.session.get_bind()
            self.base.metadata.drop_all(engine)
            self.redis_client.flushdb()
        self.session.remove()
        
    

class TestRegFactory(TestAppFactory):
    """Callable utility that returns a bootstrapped registry."""
    
    def __init__(self, **kwargs):
        self.get_registry = kwargs.get('get_registry', work.BootstrapRegistry())
        self.base = kwargs.get('base', model.Base)
        self.json_method = kwargs.get('get_json', webtest.utils.json_method)
        self.redis_factory = kwargs.get('redis_factory', redis_hooks.RedisFactory())
        self.session = kwargs.get('session', model.Session)
        self.test_settings = kwargs.get('test_settings', TEST_SETTINGS)
        self.has_created = False
    
    def __call__(self, **kwargs):
        """Bootstrap and return the registry."""
        
        # Instantiate.
        self.settings = self.test_settings.copy()
        self.settings.update(kwargs)
        self.registry = self.get_registry(settings=self.settings)
        
        # Create the db.
        self.create()
        
        # Return the registry
        return self.registry
    

