#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Misc helper functions.
"""

import logging
import urllib
import urllib2

import re
starts_with_some_text_a_colon_and_two_fwd_slashes = re.compile(r'^[a-zA-Z]+:\/\/')

from tornado.options import options

def do_nothing():
    return None


def normalise_url(url):
    if starts_with_some_text_a_colon_and_two_fwd_slashes.match(url):
        return url
    return u'%s%s' % (
        options.base_task_url,
        url.startswith('/') and url or unicode(u'/' + url)
    )


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


def dispatch_request(url, params={}):
    url = normalise_url(url)
    postdata = unicode_urlencode(params)
    request = urllib2.Request(url, postdata)
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError, err:
        _log = err.code == 204 and logging.debug or logging.warning
        _log(err)
        return err.code
    except Exception, err:
        logging.warning(err)
        return 500
    return response.code
    

