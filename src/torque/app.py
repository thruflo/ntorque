#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Sets up the Tornado web application and provides a ``main`` function
  which starts it up and starts the taskqueue polling.
"""

import logging
import time

from tornado import ioloop, httpserver, web

from config import options
from hooks import AddTask, ConcurrentExecuter
from utils import dispatch_request

application = web.Application([(
            r'/hooks/add', 
            AddTask,
        ), (
            r'/hooks/execute', 
            ConcurrentExecuter
        )
    ], 
    debug=options.debug
)

def loop():
    backoff = options.min_delay
    while True:
        status = dispatch_request(
            url='http://localhost:%s/hooks/execute' % options.port, 
            params={
                'queue_name': options.queue_name,
                'limit': options.max_concurrent_tasks
            }
        )
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
    


def main():
    # set the logging level
    logging.getLogger().setLevel(getattr(logging, options.log_level.upper()))
    # start the http server
    http_server = httpserver.HTTPServer(application)
    http_server.listen(8888)
    # start the async io loop
    ioloop.IOLoop.instance().start()
    # start the queue polling
    loop()


if __name__ == "__main__":
    main()

