# -*- coding: utf-8 -*-

"""Use this script from the command line to drive a batch of tasks through your
  nTorque system.

  In one terminal, fire up ntorque using::

      foreman start

  Edit at least the ``WEBHOOK_URL`` below, then in another terminal window::

      python drive.py

"""

import gevent
import gevent.monkey
gevent.monkey.patch_all()

import time

from requests import post

# How many concurrent tasks do you want to dispatch?
NUM_JOBS = 500

# Where's your nTorque instance running?
ENDPOINT = 'http://localhost:5000'

# Edit this to your web hook url, e.g.: a http://requestb.in
WEBHOOK_URL = NotImplemented

def dispatch(endpoint, params, n):
    """Concurrently dispatch ``n`` tasks to the nTorque endpoint."""

    jobs = []
    for i in range(n):
        data = {'i': i}
        jobs.append(gevent.spawn(post, endpoint, data=data, params=params))
    gevent.joinall(jobs)

def main():
    t1 = time.time()
    dispatch(ENDPOINT, {'url': WEBHOOK_URL}, NUM_JOBS)
    t2 = time.time()
    print '{0} jobs dispatched in {1} seconds'.format(NUM_JOBS, t2 - t1)

if __name__ == '__main__':
    main()
