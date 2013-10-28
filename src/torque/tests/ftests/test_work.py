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
        """Aquiring a task that doesn't exist returns None."""
        
        from torque.work.perform import TaskPerformer
        performer = TaskPerformer()
        
        # performer('1234:0', None)
        raise NotImplementedError
    
    def test_acquire_task_hit(self):
        """XXX Aquiring a task that does exist works."""
        
        from pyramid.request import Request
        from torque.model import CreateTask
        from torque.model import Session
        from torque.work.perform import TaskPerformer
        
        req = Request.blank('/')
        create_task = CreateTask()
        with transaction.manager:
            task = create_task(None, 'http://foo.com', 20, req)
            instruction = '{0}:0'.format(task.id)
        
        performer = TaskPerformer()
        # performer(instruction) # XXX
        raise NotImplementedError
    

