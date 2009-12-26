
Overview
--------

Torque is a web hook task queue based on tornado and redis.  It's intended to 
provide a similar pattern to Google App Engine's taskqueue_.

To use it, you need to run a redis_ database, a console script that exposes
a Tornado_ web application and one process per task queue.  You can then add 
tasks to one or more queues, either using a python client api provides or via 
an HTTP api (or indeed by adding them directly to the database).

Tasks consist of a ``url`` and some ``params``.  When a task is executed, torque
will post the params to the url.  If the task errors, it backs off steeply until
it errors too many times, at which point it's deleted.

Tasks are stored in a redis SortedSet_.  Tornado is used to execute tasks
asyncronously_, without blocking.


Install
-------

Install the redis_ and Tornado_ dependencies.  (n.b.: see 
``./etc/redis.tiger.patch`` if, like me, you're still using OSX Tiger).  Then 
install the torque egg::

    $ python setup.py install


Run
---

Run `redis`_::

    $ ./redis-server


Start the `Tornado`_ application::

    $ ./bin/torque-serve

Start the task queue::

    $ ./bin/torque-process

See ``--help`` against either of the torque console scripts for a list of configuration
options.  For example, to run a second queue called ``foobar``, you might use::

    ./bin/torque-process --queue_name=foobar


Use
---

To add a task to the queue, post to ``/add_task`` with two params:

* ``url`` which is the url to the webhook you want the task to request
* ``params`` which is a json encoded dictionary of the params you want
  to post to the webhook you're requesting

An example in python (with the Tornado application available on ``localhost``,
running on the default port of ``8889``) would be::

    import json
    import urllib
    
    mytask = {
        'url': 'http://mywebservice.com/hooks/do/foo',
        'params': json.dumps({'foo', 'somevalue', 'baz': 99})
    }
    target_url = 'http://localhost:8090/hooks/add'
    urllib.urlopen(target_url, urllib.urlencode(mytask))

This queued a POST request to ``http://mywebservice.com/hooks/do/foo`` with
the params ``foo=somevalue`` and ``baz=99`` to be made as soon as possible.

You can do something similar using any programming language that can make
url requests.  However, if you are using python, you can use the client api
that torque provides::

    from torque.client import add_task
    
    add_task(url='http://mywebservice.com/hooks/do/foo', params={'a': 1})

Note that this doesn't require json encoding the params.  You can specify a 
delay for the task, so that it's executed *after* (but not necessarily *at*) 
a number of seconds::

    add_task(url='...', params={...}, delay=20) # will execute after 20 seconds

Individual tasks backoff exponentially if they error, upto a maximum backoff delay
that's configurable as ``--max_task_delay``, until they error ``--max_task_errors`` 
times (at which point they get deleted).

See the source code for more info and options, or just run it and use it ;)

.. _taskqueue: http://code.google.com/appengine/docs/python/taskqueue/
.. _redis: http://code.google.com/p/redis/
.. _Tornado: http://www.tornadoweb.org/
.. _SortedSet: http://code.google.com/p/redis/wiki/SortedSets
.. _asyncronously: http://www.tornadoweb.org/documentation#non-blocking-asynchronous-requests

