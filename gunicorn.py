# -*- coding: utf-8 -*-

"""Gunicorn configuration."""

import logging
import os
import signal
import sys

from pyramid.settings import asbool

def _post_fork(server, worker):
    import gevent_psycopg2
    gevent_psycopg2.monkey_patch()

def _on_starting(server):
    import gevent.monkey
    gevent.monkey.patch_socket()

def _when_ready(server):
    def monitor():
        modify_times = {}
        while True:
            for module in sys.modules.values():
                path = getattr(module, "__file__", None)
                if not path: continue
                if path.endswith(".pyc") or path.endswith(".pyo"):
                    path = path[:-1]
                try:
                    modified = os.stat(path).st_mtime
                except:
                    continue
                if path not in modify_times:
                    modify_times[path] = modified
                    continue
                if modify_times[path] != modified:
                    logging.info("%s modified; restarting server", path)
                    os.kill(os.getpid(), signal.SIGHUP)
                    modify_times = {}
                    break
            gevent.sleep(0.5)
    
    import gevent
    gevent.spawn(monitor)


backlog = int(os.environ.get('GUNICORN_BACKLOG', 64))
bind = '0.0.0.0:{0}'.format(os.environ.get('PORT', 5100))
daemon = asbool(os.environ.get('GUNICORN_DAEMON', False))
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', 24000))
mode = os.environ.get('MODE', 'development')
preload_app = asbool(os.environ.get('GUNICORN_PRELOAD_APP', False))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 10))
workers = int(os.environ.get('GUNICORN_WORKERS', 2))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'gevent')

if 'gevent' in worker_class.lower():
    post_fork = _post_fork
    if mode == 'development':
        on_starting = _on_starting
        when_ready = _when_ready

