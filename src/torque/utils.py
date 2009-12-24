#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Misc helper functions.
"""

import re
starts_with_some_text_a_colon_and_two_fwd_slashes = re.compile(r'^[a-zA-Z]+:\/\/')

import urllib, urllib2

from config import options

def normalise_url(url):
    if starts_with_some_text_a_colon_and_two_fwd_slashes.match(url):
        return url
    return u'%s%s' % (
        options.base_task_url,
        url.startswith('/') and url or unicode(u'/' + url)
    )


def unicode_urlencode(params):
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
    except Exception, err:
        logging.warning('error dispatching request')
        logging.warning(request)
        logging.warning(err)
        return 500
    else:
        return response.status
    

