
Overview
--------

Torque is a web hook task queue based on Tornado_ and redis_.  It's designed to
solve two problems in the context of a web application:

#. you want to do something later
#. you want to do a number of things in parallel

There are many ways of approaching these problems.  For example, in python, you 
might look at Twisted_, Celery_ and Stackless_.  

Torque is inspired by Google App Engine's taskqueue_, which models_ tasks as 
webhooks_.  This approach allows you to handle tasks within your normal web 
application environment by writing request handlers, just as you would to handle 
a user initiated request.

To use it, you need to run three processes:

#. a redis_ database
#. ``./bin/torque-serve``, which exposes a Tornado_ application (by default on
   ``http://localhost:8889``)
#. one ``./bin/torque-process`` per queue

You can process queues ad infinitum, or until they are empty.  See
``torque.process.QueueProcessor.__doc__`` for the details.

You can add tasks to the queue in two ways:

#. by posting an HTTP request to the Tornado_ application run by ``./bin/torque-serve``
#. or by using the python client api in ``torque.client``

This first method allows you to use Torque from any programming language.  The second
makes it much simpler if you're using python.

To add a task using an HTTP request, post to ``/add_task`` with two params:

* ``url`` which is the url to the webhook you want the task to request
* ``params`` which is a json encoded dictionary of the params you want
  to post to the webhook you're requesting

An example in python (with the Tornado application available on ``localhost``,
running on port ``8889``) would be::

    import json
    import urllib
    
    mytask = {
        'url': 'http://mywebservice.com/hooks/do/foo',
        'params': json.dumps({'foo', 'somevalue', 'baz': 99})
    }
    target_url = 'http://localhost:8889/hooks/add'
    urllib.urlopen(target_url, urllib.urlencode(mytask))

This queued a POST request to ``http://mywebservice.com/hooks/do/foo`` with
the params ``foo=somevalue`` and ``baz=99`` to be made as soon as possible.

You can do something similar using any programming language that can make url 
requests.  However, if you are using python, it's much simpler to use the client 
api that Torque provides::

    from torque.client import add_task
    t = add_task(url='http://mywebservice.com/hooks/do/foo', params={'a': 1})

Note that this doesn't require json encoding the params.  For all the client api
options, see ``torque.client.Task.__doc__``.

Individual tasks backoff exponentially if they error, upto a maximum backoff delay
that's configurable as ``--max_task_delay``, until they error ``--max_task_errors`` 
times (at which point they get deleted).


Install
-------

Install the redis_ and Tornado_ dependencies.  Then install Torque::

    $ easy_install torque

Or manually from source::

    $ git clone git://github.com/thruflo/torque.git
    $ cd torque
    $ python setup.py install


Run
---

Run redis_::

    $ ./redis-server

Start the `Tornado`_ application::

    $ ./bin/torque-serve

If you want to run the tests, use::

    $ ./bin/nosetests -w ./src/torque --with-doctest
    .......
    ----------------------------------------------------------------------
    Ran 7 tests in 22.627s
    
    OK

Start the default task queue running ad infinitum::

    $ ./bin/torque-process

See ``--help`` against either of the torque console scripts for a list of configuration
options.  For example, to run a second queue called ``foobar``, you might use::

    ./bin/torque-process --queue_name=foobar

Or to process the default queue once until empty you might use::

    ./bin/torque-process --finish_on_empty=true --max_task_errors=3

Or to do exactly the same from python code::
    
    from torque.processor import QueueProcessor
    QueueProcessor(max_task_errors=3).process(finish_on_empty=true)

Read the source code for more information.

.. _webhooks: http://wiki.webhooks.org/
.. _models: http://code.google.com/appengine/docs/python/taskqueue/overview.html#Task_Concepts
.. _taskqueue: http://code.google.com/appengine/docs/python/taskqueue/
.. _redis: http://code.google.com/p/redis/
.. _Tornado: http://www.tornadoweb.org/
.. _Twisted: http://twistedmatrix.com/trac/
.. _Celery: http://ask.github.com/celery/introduction.html
.. _Stackless: http://www.stackless.com/
.. _SortedSet: http://code.google.com/p/redis/wiki/SortedSets
.. _asyncronously: http://www.tornadoweb.org/documentation#non-blocking-asynchronous-requests

