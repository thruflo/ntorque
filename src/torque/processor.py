#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Process that scrapes a specified queue.  You can run 
  as many of these as you want, as long as they process 
  different queues.
"""

import logging
import time

from tornado import options as tornado_options
from tornado.options import options

import config
from utils import dispatch_request, do_nothing

def main():
    # hack around an OSX error
    tornado_options.enable_pretty_logging = do_nothing
    # parse the command line options
    tornado_options.parse_command_line()
    # init
    backoff = options.min_delay
    url = u'%s:%s/concurrent_executer' % (
        options.address,
        options.port
    )
    params = {
        'queue_name': options.queue_name,
        'limit': options.max_tasks
    }
    # loop
    while True:
        logging.info('.')
        status = dispatch_request(url=url, params=params)
        if status == 200:
            if backoff > options.min_delay:
                backoff = backoff / options.error_multiplier
                if backoff < options.min_delay:
                    backoff = options.min_delay
        elif status == 204: # there were no tasks to execute
            backoff = backoff * options.empty_multiplier
            if backoff > options.max_empty_delay:
                backoff = options.max_empty_delay
        else: # there was an unexpected error
            backoff = backoff * options.error_multiplier
            if backoff > options.max_error_delay:
                backoff = options.max_error_delay
        time.sleep(backoff)
    


if __name__ == "__main__":
    main()

