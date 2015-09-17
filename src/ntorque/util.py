# -*- coding: utf-8 -*-

"""Utility functions."""

__all__ = [
    'generate_random_digest',
]

import logging
logger = logging.getLogger(__name__)

import os
from binascii import hexlify

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
    return unicode(hexlify(r))

