
# nTorque - web hook task queue

[nTorque][] is a [task](http://www.celeryproject.org)
[queue](https://github.com/resque/resque) service that uses [web hooks][].
It is free, open source software [released into the public domain][] that
you can use from any programming language (that speaks HTTP) to queue
up and reliably execute idempotent tasks. For example, in Python:

```python
import os
import requests

params = {'url': 'http://example.com/myhooks/send_email'}
data = {'user_id': 1234}

endpoint = os.environ.get('NTORQUE_URL')
response = requests.post(endpoint, data=data, params=params)
```

[nTorque]: http://ntorque.com
[web hooks]: http://timothyfitz.com/2009/02/09/what-webhooks-are-and-why-you-should-care/
[released into the public domain]: http://unlicense.org/UNLICENSE


## Rationale

nTorque is designed to be a good solution when you need more reliability than
fire-and-forget but you don't need an [AMPQ][] / [ESB][] sledgehammer to crack
your "do this later" nut.

Because it uses web hooks, you can:

1. use it from (and to integrate) applications written in any language
1. use DNS / web server load balancing to distribute tasks
1. bootstrap your task execution environment the way you bootstrap a web
   application -- i.e.: once at startup, re-using your web app's configuration
   and middleware

[AMPQ]: http://www.rabbitmq.com
[ESB]: http://en.wikipedia.org/wiki/Enterprise_service_bus


## Functionality

nTorque provides the following endpoints:

* `POST /` to enqueue a task
* `GET /tasks/:id` to view task status

And the following features:

* persistent task storage
* non-blocking, concurrent task execution
* HTTPS and redirect support
* configurable (linear or exponential) backoff


## Implementation

nTorque is a Python application comprising of a web application and one or more
worker processes. These use a [PostgreSQL][] database to persist tasks and a
[Redis][] database as a notification channel.

<pre><code>+------+  |  +--------+    +--------+    +--------+  |
|POST /|     |Frontend|    |Web app |    |Postgres|
|------|  |  |--------|    |--------|    |--------|  |
|- url |+- ->|- auth  |+-->|- store |+-->|- tasks |
|- data|  |  |- rate  |    |- notify|    |        |  |
|      |     |  limits|    |        |    |        |
+------+  |  +--------+    +--------+    +--------+
                               +           ^    +    |
          |                    |           |   url
                             rpush        get  data  |
          |                    |           |    |
                               v           +    v    |
          |                 +--------+   +--------+     +---------+
                            |Redis   |   |Worker  |  |  |Web hook |
          |                 +--------+   |--------|     |---------|
                               |         |- POST  |+-|->|- perform|
          | nTorque            +-blpop-> |  data  |     |  task   |
                                         +--------+  |  +---------+
</code></pre>

In the event of a response with status code:

* 200 or 201: the task is marked as successfully completed
* 202 - 499: the task is marked as failed and is not retried
* 500 (or network error): the task is retried

[Hack here][] if you'd like a different strategy.

[Hack here]: https://github.com/thruflo/ntorque/blob/master/src/ntorque/work/perform.py#L133

## Algorithm

The real crux of nTorque is a trade-off between request timeout and retry delay.
It's worth understanding this before deploying -- and how to simply mitigate
it by a) specifying an appropriate default timeout and b) overriding this as
necessary on a task by task basis.

Like [RQ][] and [Resque][], nTorque uses Redis as a push messaging channel. A
request comes in, a notification is `rpush`d onto a channel and `blpop`d off.
This means that tasks are executed immediately, with a nice evented / push
notification pattern.

Unlike [RQ][] and [Resque][], nTorque doesn't trust Redis as a persistence layer.
Instead, it relies on good-old-fashioned PostgreSQL: the first thing nTorque does
when a new task arrives is write it to disk. It then notifies a consumer process
using Redis [BLPOP][]. The consumer then reads the data from disk and performs
the task by making an HTTP request to its url.

In most cases, this request will succeed, the task will be marked as completed
and no more needs to be done. However, this won't happen *every time*, e.g.: when
there's a network error or the webhook server is temporarily down. Because there
are edge case failure scenarios where the web hook response is unreliable, nTorque
refuses to rely on it as the source of truth&trade; about a task's status. Instead,
the single source of truth is the PostgreSQL database.

This is achieved by automatically setting a task to retry every time it's read
("acquired") from the database. Specifically, the query that reads the task data
is performed within a transaction that also updates the task's due date and retry
count. This means that in any failure scenario, nTorque can always just be restarted
(potentially on a new server as long as it connects to the same database) and you
can be sure that tasks will be performed at least once no matter where they were
in the pipeline when whatever it was fell over.

Incidentally, tasks due to be retried are picked up by a background process that
polls the database every `NTORQUE_REQUEUE_INTERVAL` seconds.

More importantly, and where this description has been heading, is the relation
between the due date of the task as it lies, gloriously in repose, and the
timeout of the web hook call. For there is one thing we don't want to do, and
that is keep retrying tasks before they've had a chance to complete.

In order to prevent this behaviour, we impose a simple constraint:

> **The due date set when the task is transactionally read and incremented must
  be longer than the web hook timeout.**

This means that, in the worst case (when a web hook request does timeout or
fail to respond), you must wait for the full timeout duration before your task
is retried. So whilst you may naturally want to set a relatively high timeout
for long running tasks, you may want to keep it shorter for simper tasks like
sending your new user's welcome or reset password email: so that they're
retried faster.

The good news is that, in addition to the global `NTORQUE_DEFAULT_TIMEOUT`
configuration variable, you can set an appropriate timeout for different tasks
using the [`timeout` query parameter](#usage-api/post).

Simple -- once you know how the system works.

[BLPOP]: http://redis.io/commands/blpop
[Gevent]: http://www.gevent.org
[PostgreSQL]: http://www.postgresql.org
[Redis]: http://redis.io
[Resque]: https://github.com/resque/resque
[RQ]: http://python-rq.org/


## Installation

Clone the repo, install the Python app using:

    bash pip_install.sh

You need Redis and Postgres running. If necessary, create the database:

    createdb -T template0 -E UTF8 ntorque

If you like, install Foreman, to run the multiple processes, using:

    bundle install

Run the migrations:

    foreman run alembic upgrade head

Bootstrap an app (if you'd like to authenticate access with an API key):

    foreman run python alembic/scripts/create_application.py --name YOURAPP

You should then be able to:

    foreman start

Alternatively, skip the Foreman stuff and run the commands listed in `Processes`
manually / using a Docker / Chef / init.d wrapper. Or push to Heroku, run the
migrations and it should just work.


## Configuration

Algorithm / Behaviour:

* `NTORQUE_BACKOFF`: `exponential` (default) or `linear`
* `NTORQUE_CLEANUP_AFTER_DAYS`: how many days to leave tasks in the db for, defaults
  to `7`
* `NTORQUE_DEFAULT_TIMEOUT`: how long, in seconds, to wait before treating a web
  hook request as having failed -- defaults to `60` see the algorithm section
  above for details
* `NTORQUE_MIN_DUE_DELAY`: minimum delay before retrying -- don't set any lower
  than `2`
* `NTORQUE_MAX_DUE_DELAY`: maximum retry delay -- defaults to `7200` but you
  should make sure its longer than `NTORQUE_DEFAULT_TIMEOUT`
* `NTORQUE_MAX_RETRIES`: how many attempts before giving up on a task -- defaults
  to `36`
* `NTORQUE_REQUEUE_INTERVAL`: how often, in seconds, to poll the database for
  tasks to requeue -- defaults to 5
* `NTORQUE_TRANSIENT_REQUEST_ERRORS`: 4xx errors which ntorque should retry -- defaults to '408,423,429,449'

Deployment:

* `NTORQUE_AUTHENTICATE`: whether to require authentication; defaults to `True`
  -- see authentication section in Usage below
* `NTORQUE_ENABLE_HSTS`: set this to `True` if you're using [HSTS][]
* `HSTS_PROTOCOL_HEADER`: set this to, e.g.: `X-Forwarded-Proto` if you're running
  behind an https proxy frontend (see [pyramid_hsts][] for more details)
* `MODE`: if set to `development` this will run [Gunicorn][] in watch mode (so the app
  server restarts when a Python file changes) and will raise HTTP exceptions in the
  API views (rather than returning them). If set to `production` it will run Gunicorn
  behind a [newrelic][] client. If this isn't quite what you want then either don't
  set it or set it to any other string (or hack the `run.sh` and / or `gunicorn.py`
  scripts)

Redis:

* `NTORQUE_REDIS_CHANNEL`: name of your Redis list used as a notification channel;
  defaults to `ntorque`
* `REDIS_URL`, etc.: see [pyramid_redis][] for details on how to configure your
  Redis connection

Database:

* `DATABASE_URL`, defaults to `postgresql:///ntorque`
* `SQLALCHEMY_MAX_OVERFLOW`, `SQLALCHEMY_POOL_CLASS`, `SQLALCHEMY_POOL_SIZE` and
  `SQLALCHEMY_POOL_RECYCLE` -- see the SQLAlchemy docs on [engine configuration][]
  and [pyramid_basemodel][] for more information; if you don't provide these
  then SQLAlchemy will use sensible defaults, also note that if you're using
  [pgbouncer][] you should set `SQLALCHEMY_POOL_CLASS=sqlalchemy.pool.NullPool`

[engine configuration]: http://docs.sqlalchemy.org/en/rel_0_9/core/engines.html
[gunicorn]: http://gunicorn.org
[hsts]: http://en.wikipedia.org/wiki/HTTP_Strict_Transport_Security
[newrelic]: https://addons.heroku.com/newrelic
[pgbouncer]: https://wiki.postgresql.org/wiki/PgBouncer
[pyramid_basemodel]: https://github.com/thruflo/pyramid_basemodel
[pyramid_hsts]: https://github.com/thruflo/pyramid_hsts
[pyramid_redis]: https://github.com/thruflo/pyramid_redis

## Usage / API

### Authentication

If you set `NTORQUE_AUTHENTICATE` to `True` then you need to create at least one
application (e.g.: using the `alembic/scripts/create_application.py` script) and
provide its api key in the `NTORQUE_API_KEY` header when enqueuing a task.

### `POST /`

To enqueue a task, make a POST request to the root path of your nTorque
installation.

**Required**:

* a `url` query parameter; this is the url to your web hook that you want nTorque
  to call to perform your task

**Optional**:

* a `method` query parameter; which http method to use when calling the webhook --
  the default is POST, but you can alternatively specify DELETE, PUT or PATCH.
* a `timeout` query parameter; how long, in seconds, to wait before treating the
  web hook call as having timed out -- see the Algorithm section above for context

**Data**:

This aside, you can pass through any POST data, encoded as any content type you
like. The data, content type and character encoding will be passed on in the POST
(or DELETE, PUT or PATCH) request to your web hook.

**Headers**:

Aside from the content type, length and charset headers, derived from your
request, you can specify headers to pass through to your web hook, by prefixing
the header name with `NTORQUE-PASSTHROUGH-`. So, for example, to pass through
a `FOO: Bar` header, you would provide `NTORQUE-PASSTHROUGH-FOO: Bar` in your
request headers.

**Response**:

You should receive a 201 response with the url to the task in the `Location`
header.

### `GET /task/:id`

Returns a JSON data dict with status information about a task.

#### `POST /task/:id/push`

Pushes a task onto the redis notification channel to be consumed, aquired and
performed. You should *not* normally need to use this. It's exposed as an
optimisation for [hybrid][] integrations.

[hybrid]: https://github.com/thruflo/ntorque/blob/master/src/ntorque/client.py#L141


## Pro-Tips

nTorque is a system for reliably calling web hook task handlers: not for
implementing them. You are responsible for implementing and exposing your own
web hooks. In most languages and frameworks this is simple, e.g.: in Ruby
using [Sinatra][]:

```ruby
post '/hooks/foo' do
    # your code here
end
```

Or in Python using [Flask][]:

```python
@app.route('/hooks/foo', methods=['POST'])
def foo():
    # your code here
```

Key things to bear in mind are:

[Sinatra]: http://www.sinatrarb.com
[Flask]: http://flask.pocoo.org

#### Status Code

After successfully performing their task, your web hooks are expected to return
an HTTP response with a `200` or `201` status code. If not, nTorque will keep
retrying the task.

#### Avoid Timeouts

Your web server must be configured with a high enough timeout to allow tasks
enough time to complete. If not, you may be responding with an error when tasks
are actually being performed successfully.

For example, for a 30 minute timeout with [Apache][] as a proxy:

```text
Timeout 1800
ProxyTimeout 1800
```

Or with [Nginx][]:

```text
send_timeout 1800;
proxy_send_timeout 1800;
```

[Apache]: http://httpd.apache.org
[Nginx]: http://nginx.org

#### Secure Public Hooks

If your web hooks are exposed on a public IP, you are likely to want to secure
them, e.g.: using HTTPS and an authentication credential like an API key.

It's also worth noting that you may need to turn off [CSRF validation][].

[CSRF validation]: http://en.wikipedia.org/wiki/Cross-site_request_forgery#Prevention


## Support

Raise [bugs / issues on GitHub](https://github.com/thruflo/ntorque/issues).
