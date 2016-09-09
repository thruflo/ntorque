# -*- coding: utf-8 -*-

"""Utility functions."""

__all__ = [
    'call_in_process',
    'generate_random_digest',
]

import logging
logger = logging.getLogger(__name__)

import Queue
import binascii
import multiprocessing
import os

def call_in_process(f, *args, **kwargs):
    """Calls a function or method with the args and kwargs provided
      in a new process. We use this to make sure we don't get a memory
      leak from the db queries -- given that this thing runs forever.
    """

    # Configure.
    timeout = kwargs.get('process_timeout', 10) # seconds

    # Prepare a wrapper function and cross-process queue to get the
    # return value from.
    q = multiprocessing.Queue()
    def doit():
        r = f(*args, **kwargs)
        q.put(r)

    # Run the function in a new process and put the result on the queue.
    p = multiprocessing.Process(target=doit)
    p.start()

    # Block until the function is called or the timeout is reached.
    # If the latter, terminate the process.
    p.join(timeout=timeout)
    if p.is_alive():
        p.terminate()

    # Now, if there's a value on the queue, return it.
    return_value = None
    try:
        return_value = q.get(False)
    except Queue.Empty:
        pass
    return return_value

def generate_random_digest(num_bytes=20):
    """Generates a random hash and returns the hex digest as a unicode string.

      Defaults to sha1::

          >>> import hashlib
          >>> h = hashlib.sha1()
          >>> digest = generate_random_digest()
          >>> len(h.hexdigest()) == len(digest)
          True

      Pass in ``num_bytes`` to specify a different length hash::

          >>> h = hashlib.sha512()
          >>> digest = generate_random_digest(num_bytes=64)
          >>> len(h.hexdigest()) == len(digest)
          True

      Returns unicode::

          >>> type(digest) == type(u'')
          True

    """

    r = os.urandom(num_bytes)
    return unicode(binascii.hexlify(r))
