#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Runs the webapp and the process in seperate threads of
  a single process.
"""

import logging

from tornado import options as tornado_options

from processor import QueueProcessor
from webapp import serve
from utils import do_nothing

def main():
    # hack around an OSX error
    tornado_options.enable_pretty_logging = do_nothing
    # parse the command line options
    tornado_options.parse_command_line()
    # start the queue processor
    qp = QueueProcessor()
    qp.start(async=True)
    try: # serve the webapp
        serve()
    except KeyboardInterrupt, err:
        qp.stop()
        raise err
    

