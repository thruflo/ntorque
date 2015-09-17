# -*- coding: utf-8 -*-

import gevent.monkey
import gevent_psycopg2

def green_threads():
    gevent.monkey.patch_all()
    gevent_psycopg2.monkey_patch()
