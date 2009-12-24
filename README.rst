
Overview
--------

"""Run the taskqueue::
  
      $ ./bin/run-taskqueue
  
  This will expose a Tornado webserver (by default running on port 8090,
  use ``-p`` to specify another port, e.g.: ``-p 8081``).
  
  To add a task to the queue, post to ``/hooks/add`` with two params:
  
  * ``url`` which is the url to the webhook you want the task to request
  * ``params`` which is a json encoded dictionary of the params you want
  to post to the webhook you're requesting
  
  An example in python might be::
  
      try:
          import json
      except ImportError:
          import simplejson as json
      import urllib
      
      mytask = {
          'url': 'http://mywebservice.com/hooks/do/foo',
          'params': json.dumps({'foo', 'somevalue', 'baz': 99})
      }
      target_url = 'http://localhost:8090/hooks/add'
      urllib.urlopen(target_url, urllib.urlencode(mytask))
  
  This queued a POST request to ``http://mywebservice.com/hooks/do/foo`` with
  the params ``foo=somevalue`` and ``baz=99`` to be made as soon as possible
  and then returned immediately.
  
  You can do something similar using any programming language that can make
  url requests.  However, if you are using python, you can use the client api
  that torque provides::
  
      from torque import client
      
      # create a task
      t = client.Task(url='http://mywebservice.com/hooks/do/foo', params={'a': 1})
      # add it to the queue
      t.add()
      
      # or just use the shortcut function to do
      # both at the same time
      client.add(url='http://mywebservice.com/hooks/do/foo', params={'a': 1})
  
  You can also specify a base url for all task requests using ``--base-task-url``
  e.g. ``--base-task-url 'http://mywebservice.com'`` allows::
  
      t = client.Task(url='/hooks/do/foo', params={'a': 1})
  
  You can specify a delay for the task, so that it's executed *after* (but
  not necessarily *at*) a number of seconds::
  
      t = client.Task(url='/hooks/do/foo', params={'a': 1}, delay=2)
  
  Individual tasks backoff exponentially if they error, until they error 
  either ``MAX_TASK_ERRORS`` or ``--max-task-errors`` times, as which point 
  they get binned.
"""




Install
-------

Install the ``./vendor`` dependencies.  (See ``./etc/redis.tiger.patch`` if, like me, you're still using OSX Tiger.)

Then install the egg::

    $ python setup.py install


Run
---

Run redis::

    $ ...

Start the task queue::

    $ ./bin/run-taskqueue


Use
---

...


