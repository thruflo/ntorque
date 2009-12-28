#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Misc helper functions.
"""

import urllib

def do_nothing():
    return None


def unicode_urlencode(params):
    if not params:
        return u''
    if isinstance(params, dict):
        params = params.items()
    return urllib.urlencode([(
                k, 
                isinstance(v, unicode) and v.encode('utf-8') or v
            ) for k, v in params
        ]
    )

