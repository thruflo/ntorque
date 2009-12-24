#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import time

try:
    import json
except ImportError:
    import simplejson as json

from tornado import httpclient, web

from client import add, update, remove, fetch
from config import options
from utils import unicode_urlencode

class ConcurrentExecuter(web.RequestHandler):
    """Takes a ``queue_name``, fetches ``limit`` items from
      the queue, and posts them individually via concurrent, 
      non-blocking requests.
      
      If the queue is empty, returns 204 to indicate there's
      no content to process.
      
      If an individual task errors, its ``ts`` is incremented
      according to a backoff algorithm
    """
    
    def get(self):
        self.post()
    
    @web.asynchronous
    def post(self):
        logging.info('ConcurrentExecuter.post')
        # queue_name and limit are optional
        kwargs = {}
        queue_name = self.get_argument('queue_name', False)
        if queue_name:
            kwargs['queue_name'] = queue_name
        limit = self.get_argument('limit', False)
        if limit:
            kwargs['limit'] = limit
        tasks = fetch(**kwargs, decode=False)
        if len(tasks) == 0:
            logging.info('no tasks left')
            self.set_status(204)
            self.finish()
        else:
            logging.info('picked up %s tasks' % len(tasks))
            self.kwargs = queue_name and {'queue_name': queue_name} or {}
            self.task_strings = []
            http = httpclient.AsyncHTTPClient()
            for task_string in tasks:
                task = json.loads(task_string)
                url = task['url']
                params = task['params']
                logging.info('httpclient.AsyncHTTPClient.fetch %s' % task)
                http.fetch(
                    url,
                    method='POST',
                    body=unicode_urlencode(params),
                    callback=self.async_callback(
                        self._handle_response,
                        task_string = task_string
                    )
                )
                self.task_strings.append(task_string)
            
        
    
    def _handle_response(self, response, task_string):
        logging.info('ConcurrentExecuter._handle_response for %s' % task_string)
        
        if not response.error:
            # delete the task from the queue
            remove(task_string, **self.kwargs)
            logging.info('deleted %s' % task_string)
        else:
            logging.info(response.error)
            # if it's less than MAX_ERRORS
            error_count = get_and_increment_error_count(task_string)
            if error_count < MAX_TASK_ERRORS:
                # backoff scheduling it again
                delay = options.min_delay
                while error_count > 0:
                    delay = delay * options.error_multiplier
                    error_count -= 1
                update(task_string, delay=delay, **self.kwargs)
                logging.info('backed %s off for %s secs' % (task_string, delay))
            else: # delete it
                remove(task_string, **self.kwargs)
                logging.info('deleted %s' % task_string)
        # if all the requests have returned
        logging.info('removing %s from...' % task_string)
        logging.info(self.task_strings)
        self.task_strings.remove(task_string)
        logging.info(self.task_strings)
        if len(self.task_strings) == 0:
            # finish the request, returning a status of 200
            self.set_status(200)
            self.finish()
            logging.info('finished')
        
    


class AddTask(web.RequestHandler):
    """Webhook available on ``/hooks/add`` that allows tasks to
      be added to the queue over an http request, i.e.: from any
      programming language.
      
      To add a task to the queue, post to ``/hooks/add`` with two params:
      
      * ``url`` which is the url to the webhook you want the task to request
      * ``params`` which is a json encoded dictionary of the params you want
      to post to the webhook you're requesting
      
      You can also provide a ``delay`` and a ``queue_name``.
    """
    
    def get(self):
        self.post()
    
    @web.asynchronous
    def post(self):
        # url is required
        url = self.get_argument('url')
        # params are passed in empty if not provided
        kwargs = {
            'params': json.loads(self.get_argument('params', '{}')),
        }
        # queue_name and delay are optional
        queue_name = self.get_argument('queue_name', False)
        if queue_name:
            kwargs['queue_name'] = queue_name
        delay = self.get_argument('delay', False)
        if delay:
            kwargs['delay'] = delay
        return add(url, **kwargs)
    

