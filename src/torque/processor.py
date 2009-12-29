#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Process that scrapes a specified queue.  You can run 
  as many of these as you want, as long as they process 
  different queues.
"""

import logging
import math
import time
import urllib2

from tornado import options as tornado_options
from tornado.options import define, options
from tornado.escape import json_decode, json_encode

from client import get_task
from utils import do_nothing, unicode_urlencode

# external config you may want to provide unless you're processing
# the default queue on the default address
define(
    'server_address', default='http://localhost:8889', 
    help='where is the concurrent executer running?'
)

# are we processing a queue ad infinitum, or just once until empty?
define(
    'finish_on_empty', default=False, type=bool,
    help='should ``QueueProcessor.process`` finish once the queue is empty?'
)

# config specifying how to deal with erroring tasks (these defaults 
# are designed for quite a forgiving, long running queue)
define(
    'max_task_errors', default=100, type=int,
    help='how many times can a task error?'
)
define(
    'max_task_delay', default=1111, type=int,
    help='maximum time an erroring task can be delayed for'
)

# internal config relating to the polling delay / backoff algorithms
# (all times are in seconds)
define(
    'min_delay', default=0.2, type=float,
    help='how long to wait between polling when tasks pending'
)
define(
    'max_empty_delay', default=1.6, type=float,
    help='maximum wait when there are no tasks pending'
)
define(
    'max_error_delay', default=240, type=int,
    help='maximum wait when the concurrent executer is erroring'
)
define(
    'empty_multiplier', default=1.5, type=float,
    help='exponentially multiply the delay by when no tasks are pending'
)
define( 
    'error_multiplier', default=4.0, type=float,
    help='exponentially multiply the delay by when something is erroring' 
)

class QueueProcessor(object):
    """Takes a range if config and processes a queue.
      
      You can use it in two ways.  You can process a queue ad infinitum
      using ``QueueProcessor().process(finish_on_empty=False)``.  Or you 
      can process a queue until it's empty::
      
          >>> from client import add_task, clear_queue, count_tasks
          >>> n = clear_queue()
          >>> url = 'http://www.friendfeed.com'
          >>> for item in 'abcdefghijklmnopqrstuvwxyz':
          ...     t = add_task(url, {'char': item})
          ...
          >>> count_tasks()
          26
          >>> qp = QueueProcessor()
          >>> qp.process(finish_on_empty=True)
          True
          >>> count_tasks()
          0
      
      If you specify ``finish_on_empty=True`` then the method returns
      ``True`` if the queue was cleared successfully.  Or it will
      return ``False`` if it errored.
      
      Note that a task erroring won't error the queue processing.
      Instead, the task will be rescheduled ``max_task_errors`` times,
      backing off exponentially upto ``max_task_delay`` seconds::
      
          >>> non_existant_url = 'http://friendfeed.com/fjfsdghfdshfsfgfjsgfhjsdsd'
          >>> t = add_task(non_existant_url) # will error when executed
          >>> count_tasks()
          1
          >>> qp = QueueProcessor()
          >>> qp.process(finish_on_empty=True)
          True
          >>> count_tasks()
          0
      
      It's worth noting that if you have an erroring task, and relatively 
      high values for ``max_task_errors`` and ``max_task_delay``, it may
      take a while to finish!  In this case, you probably want to lower
      the values for task errors and task delay.
    """
    
    def __init__(
            self, server_address=None, queue_name=None, limit=None,
            max_task_errors=None, max_task_delay=None, min_delay=None,
            error_multiplier=None, empty_multiplier=None,
            max_empty_delay=None, max_error_delay=None
        ):
        self.server_address = server_address and server_address or options.server_address
        self.queue_name = queue_name and queue_name or options.queue_name
        self.limit = limit and limit or options.limit
        self.max_task_errors = max_task_errors and max_task_errors \
                               or options.max_task_errors
        self.max_task_delay = max_task_delay and max_task_delay or options.max_task_delay
        self.min_delay = min_delay and min_delay or options.min_delay
        self.error_multiplier = error_multiplier and error_multiplier \
                                or options.error_multiplier
        self.empty_multiplier = empty_multiplier and empty_multiplier \
                                or options.empty_multiplier
        self.max_empty_delay = max_empty_delay and max_empty_delay \
                                or options.max_empty_delay
        self.max_error_delay = max_error_delay and max_error_delay \
                                or options.max_error_delay
        
    
    
    def _dispatch(self, url, params={}, decode=True):
        """Internal method that dispatches a request and handles the
          response to always return a (response, status_code) tuple
          where the response may be None but the status code is always
          an appropriate number.
          
          If ``decode`` is ``True`` and the ``status`` is in the 200s
          then it decodes the response body from a json string into
          a python object.
        """
        
        request = urllib2.Request(url, unicode_urlencode(params))
        response = None
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, err:
            _log = 204 <= err.code <= 205 and logging.debug or logging.warning
            _log(err)
            status = err.code
        except Exception, err:
            logging.warning(err)
            status = 500
        else:
            status = response.code
            response = decode and json_decode(response.read()) or response.read()
        return response, status
    
    
    def process(self, finish_on_empty=None):
        finish_on_empty = finish_on_empty and finish_on_empty or options.finish_on_empty
        backoff = self.min_delay
        url = u'%s/concurrent_executer' % self.server_address
        params = {
            'queue_name': self.queue_name, 
            'limit': self.limit,
            'check_pending': finish_on_empty
        }
        while True:
            logging.info('.')
            response, status = self._dispatch(url=url, params=params)
            # first process the tasks
            # then deal with the backoff
            logging.debug('_dispatch status: %s' % status)
            if status == 200:
                for task_id, status_code in response.iteritems():
                    logging.debug('task_id status: %s' % status_code)
                    t = get_task(task_id, queue_name=self.queue_name)
                    logging.debug(t)
                    if 200 <= status_code < 300:
                        t.remove()
                    else: 
                        error_count = t.get_and_increment_error_count()
                        if error_count > self.max_task_errors:
                            t.remove()
                        else: 
                            delay = math.pow(1 + self.min_delay, error_count)
                            if delay > self.max_task_delay:
                                delay = self.max_task_delay
                            t.add(delay=delay)
                if backoff > self.min_delay:
                    backoff = backoff / self.error_multiplier
                    if backoff < self.min_delay:
                        backoff = self.min_delay
            elif status == 204 or status == 205:
                if status == 205 and finish_on_empty:
                    return True
                backoff = backoff * self.empty_multiplier
                if backoff > self.max_empty_delay:
                    backoff = self.max_empty_delay
            else: # there was an unexpected error
                if finish_on_empty:
                    return False
                backoff = backoff * self.error_multiplier
                if backoff > self.max_error_delay:
                    backoff = self.max_error_delay
            time.sleep(backoff)
        
    
    


def main():
    # hack around an OSX error
    tornado_options.enable_pretty_logging = do_nothing
    # parse the command line options
    tornado_options.parse_command_line()
    # process the queue
    success = QueueProcessor().process()
    # if there is one, report the result
    logging.info(success and 'processed successfully' or 'processing failed')
    


def setup():
    options.queue_name = 'doctests'
    options.max_task_errors = 3


def teardown():
    from client import clear_queue
    clear_queue()


if __name__ == "__main__":
    main()

