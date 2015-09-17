# -*- coding: utf-8 -*-

"""Provides ``Backoff``, a numerical value adapter that provides ``linear()`` and
  ``exponential()`` backoff value calculation::

      >>> b = Backoff(1)
      >>> b.linear()
      2
      >>> b.linear()
      3
      >>> b.exponential()
      6
      >>> b.exponential()
      12

  The default linear increment is the start value::

      >>> b = Backoff(2)
      >>> b.linear()
      4
      >>> b.linear()
      6

  You can override this by passing an ``incr`` kwarg to the constructor::

      >>> b = Backoff(10, incr=2)
      >>> b.linear()
      12

  You can override this by passing an arg to the linear method::

      >>> b.linear(4)
      16

  The default exponential factor is ``2``. You can override this by providing
  a ``factor`` kwarg to the constructor, or an arg to the method::

      >>> b = Backoff(1, factor=3)
      >>> b.exponential()
      3
      >>> b.exponential(1.5)
      4.5

  Both can be limited to a maximum value::

      >>> b = Backoff(1, max_value=2)
      >>> b.linear()
      2
      >>> b.linear()
      2
      >>> b = Backoff(2, max_value=5)
      >>> b.exponential()
      4
      >>> b.exponential()
      5

"""

__all__ = [
    'Backoff',
]

import logging
logger = logging.getLogger(__name__)

class Backoff(object):
    """Adapts a ``start_value`` to provide ``linear()`` and ``exponential()``
      backoff value calculation.
    """

    def __init__(self, start_value, factor=2, incr=None, max_value=None):
        """Store the ``value`` and setup the defaults, using the start value
          as the default increment if not provided.
        """

        if incr is None:
            incr = start_value
        if max_value is None:
            max_value = float('inf')

        self.default_factor = factor
        self.default_incr = incr
        self.max_value = max_value
        self.value = start_value

    def limit(self, value):
        if value > self.max_value:
            return self.max_value
        return value

    def linear(self, incr=None):
        """Add ``incr`` to the current value."""

        if incr is None:
            incr = self.default_incr

        value = self.value + incr
        self.value = self.limit(value)
        return self.value

    def exponential(self, factor=None):
        """Multiple the current value by (fraction * itself)."""

        if factor is None:
            factor = self.default_factor

        value = self.value * factor
        self.value = self.limit(value)
        return self.value


