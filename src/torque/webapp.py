#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tornado web application, serving:
  * ``/add_task``
  * ``/concurrent_executer``
  
  Run using::
      
      $ ./bin/torque-serve
  
"""

import logging
import math
import time

try:
    import json
except ImportError:
    import simplejson as json

from tornado import ioloop, httpclient, httpserver, web
from tornado import options as tornado_options
from tornado.options import options

import config
from client import add_task, fetch_tasks
from utils import do_nothing, unicode_urlencode

class AddTask(web.RequestHandler):
    """Add tasks to the queue over an http request, i.e.: from any
      programming language.
      
      To add a task to the queue, post to this handler with two params:
      
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
        return add_task(url, **kwargs)
    


class ConcurrentExecuter(web.RequestHandler):
    """Takes a ``queue_name``, fetches ``limit`` items from
      the queue, and posts them individually via concurrent, 
      non-blocking requests.
      
      If the queue is empty, returns 204 to indicate there's
      no content to process.
      
      If an individual task errors, its ``ts`` is incremented
      according to a backoff algorithm.
    """
    
    def get(self):
        self.post()
    
    @web.asynchronous
    def post(self):
        self.start_time = time.time()
        # queue_name and limit are optional
        kwargs = {}
        queue_name = self.get_argument('queue_name', False)
        if queue_name:
            kwargs['queue_name'] = queue_name
        limit = self.get_argument('limit', False)
        if limit:
            kwargs['limit'] = limit
        tasks = fetch_tasks(**kwargs)
        if len(tasks) == 0:
            self.set_status(204)
            self.finish()
        else:
            self.kwargs = queue_name and {'queue_name': queue_name} or {}
            self.task_ids = []
            http = httpclient.AsyncHTTPClient(max_clients=options.max_tasks)
            for task in tasks:
                http.fetch(
                    task.url,
                    method='POST',
                    body=unicode_urlencode(task.params),
                    callback=self.async_callback(
                        self._handle_response,
                        task = task
                    )
                )
                self.task_ids.append(task.id)
            
        
    
    def _handle_response(self, response, task):
        if not response.error:
            task.remove(**self.kwargs)
        else: 
            error_count = task.get_and_increment_error_count()
            if error_count > options.max_task_errors:
                task.remove(**self.kwargs)
            else: # backoff scheduling it again
                delay = math.pow(1 + options.min_delay, error_count)
                if delay > options.max_task_delay:
                    delay = options.max_task_delay
                task.add(delay=delay, **self.kwargs)
        # if all the requests have returned
        self.task_ids.remove(task.id)
        if len(self.task_ids) == 0:
            self.set_status(200)
            self.finish()
        
    
    


mapping = [(
        r'/add_task', 
        AddTask,
    ), (
        r'/concurrent_executer', 
        ConcurrentExecuter
    )
]

def main():
    # hack around an OSX error
    tornado_options.enable_pretty_logging = do_nothing
    # parse the command line options
    tornado_options.parse_command_line()
    # create the web application
    application = web.Application(mapping, debug=options.debug)
    # start the http server, forking one process per cpu
    http_server = httpserver.HTTPServer(application)
    http_server.bind(options.port)
    http_server.start()
    # start the async ioloop
    ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()

