#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Parse command line options into config.*
"""

import logging

from optparse import OptionParser

# setup the option parser
parser = OptionParser()
parser.add_option(
    '--logging', dest='log_level', default='INFO',
    help='logging level'
)
parser.add_option(
    '--debug', dest='debug', default=False,
    help='debug mode'
)
parser.add_option(
    '--port', dest='port', default=8090,
    help='which port to run on'
)
parser.add_option(
    '--queue-name', dest='queue_name', default='default_taskqueue',
    help='name of the queue - useful if you want to run more than one'
)
parser.add_option(
    '--base-task-url', dest='base_task_url', default='http://localhost:8080',
    help='base url to use if and when expanding relative task urls'
)
parser.add_option(
    '--max-concurrent-tasks', dest='max_concurrent_tasks', default=5,
    help='how many tasks can be processed concurrently?'
)
parser.add_option(
    '--max-task-errors', dest='max_task_errors', default=8,
    help='how many times can a task error?'
)
parser.add_option(
    '--min-delay', dest='min_delay', default=0.2,
    help='how long to wait between polling when there are tasks pending'
)
parser.add_option(
    '--max-empty-delay', dest='max_empty_delay', default=1.6,
    help='how long to wait between polling when there are no tasks pending'
)
parser.add_option(
    '--max-error-delay', dest='max_error_delay', default=240,
    help='how long to wait between polling when the concurrent executer is erroring'
)
parser.add_option(
    '--empty-multiplier', dest='empty_multiplier', default=2.0,
    help='what to multiply the delay by when empty'
)
parser.add_option(
    '--error-multiplier', dest='error_multiplier', default=4.0,
    help='what to multiply the delay by when erroring'
)
(options, args) = parser.parse_args()
