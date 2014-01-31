
# Torque - web hook task queue

[Torque][] is a [task](http://www.celeryproject.org)
[queue](https://github.com/resque/resque) service that uses [web hooks][].
It is free, open source software [released into the public domain][] that
you can use from any programming language (that speaks HTTP) to queue
up and reliably execute idempotent tasks. For example, in Python:

```python
import os
import requests

params = {'url': 'http://example.com/myhooks/send_email'}
data = {'user_id': 1234}

endpoint = os.environ.get('TORQUE_URL')
response = requests.post(endpoint, data=data, params=params)
```

[Torque]: http://documentup.com/thruflo/torque
[web hooks]: http://timothyfitz.com/2009/02/09/what-webhooks-are-and-why-you-should-care/
[released into the public domain]: http://unlicense.org/UNLICENSE


## Rationale

Torque is designed to be a good solution when you need more reliability than
fire-and-forget but you don't need an [AMPQ][] / [ESB][] sledgehammer to crack
your "do this later" nut.

Because it uses web hooks, you can:

1. use it from (and to integrate) applications written in any language
1. use DNS / web server load balancing to distribute tasks
1. bootstrap your task execution environment the way you bootstrap a web
   application -- i.e.: once at startup, potentially re-using your web
   application's configuration and middleware

[AMPQ]: http://www.rabbitmq.com
[ESB]: http://en.wikipedia.org/wiki/Enterprise_service_bus


## Functionality

Torque provides the following endpoints:

* `POST /` to enqueue a task
* `GET /tasks/:id` to view task status

And the following features:

* persistent task storage
* non-blocking, concurrent task execution
* HTTPS and redirect support
* configurable (linear or exponential) backoff to retry tasks that fail due
  to network, connection or internal server errors


## Implementation

Torque is a Python application comprising of a web application and one or more
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
          | Torque             +-blpop-> |  data  |     |  task   |
                                         +--------+  |  +---------+
</code></pre>

In the event of a response with status code:

* 200 or 201: the task is marked as successfully completed
* 202 - 499: the task is marked as failed and is not retried
* 500 (or network error): the task is retried

Note that it's eminently possible to fork / provide a patch that makes this
behaviour more configurable, e.g.: to provide an alternative strategy to
retry failed tasks. Also that completed tasks are periodically deleted after
a configurable time period.


## Algorithm

The real crux of Torque is a trade-off between request timeout and retry delay.
It's worth understanding this before deploying -- and how to simply mitigate
it by a) specifying an appropriate default timeout and b) overriding this as
necessary on a task by task basis.

Like [RQ][] and [Resque][], Torque uses Redis as a push messaging channel. A
request comes in, a notification is `rpush`d onto a channel and `blpop`d off.
This means that tasks are executed immediately, with a nice evented / push
notification pattern.

Unlike [RQ][] and [Resque][], Torque doesn't trust Redis as a persistence layer.
Instead, it relies on good-old-fashioned PostgreSQL: the first thing Torque does
when a new task arrives is write it to disk (with a due date and a retry count).

Now, when the consumer receives the push notification from Redis, it reads the
data from disk and performs the task by making a POST request to the
task's webhook url. In most cases, this request will succeed, the task will
be marked as completed and no more needs to be done. However, this won't happen
*every time* as the process is highly vulnerable to network errors.

The Torque process can fall over. Redis can fall over. The webhook request can
encounter any number of transient errors. The longer the web hook request takes
to return, the more chance there is something will go wrong.

Because of these risks, Torque explicitly refuses to rely on either the Redis
notification channel or the web hook response as the source of truth&trade;
about a task's status -- whether it has been performed successfully or not.
Instead, the single source of truth is, predictably enough, the PostgreSQL
database.

The way this is achieved is through an algorithm that automatically sets a
task to retry every time it's read from the database. Explicitly, the query
that reads the task data is performed within a transaction that also updates
the task's due date and retry count. This means that, if nothing happens
(the system falls over, the network hangs) after reading the task, it will
remain stored in a state that indicates that and when it needs to be retried.

If the task is completed successfully, it is marked as completed before its
retry date is due. If the web hook call fails, the task's status is updated
as soon as the information becomes available, e.g.: bringing the retry date
forward or making it as failed. However, fundamentally, if nothing happens,
the task remains untouched, ready to retried when due.

Incidentally, tasks due to be retried are straightforwardly picked up by a
background process that polls the database relatively infrequently (e.g.:
every few seconds).

More importantly, and where this description has been heading, is the relation
between the due date of the task as it lies, gloriously in repose, and the
timeout of the web hook call. For there is one thing we don't want to do, and
that is keep retrying tasks before they've had a chance to complete.

In order to prevent this behaviour -- which would hammer the web hook server
with unnecessary requests -- we impose a simple constraint. The due date set
when the task is transactionally read and incremented must be longer than the
web hook timeout. (Plus a small margin to cover the time it takes to prepare
and handle the web hook request).

This means that, in the worst case (when a web hook request does timeout or
the system falls over when performing a task), you must wait for the full
timeout duration before your task is retried. Normally, this is a relatively
minor problem. However, it is amplified by the nature of web hooks: that you
may naturally want to set a relatively high timeout on request handlers that
are designed to execute long running tasks.

For most web applications, web hooks might only need a maximum of a minute or
two to perform a task like sending an email or re-calculating a score. For
more complex tasks, like re-generating a whole site, or performing some kind
of data analysis, you may want to configure a much higher timeout. However,
this is unlikely to be an unacceptable period to wait before retrying sending
your new user's welcome or reset password email.

Left as a one-size fits all configuration option, the choice is stark.
Short retry times may result in long-running tasks hammering your server.
Higher timeouts may delay simpler tasks being performed.

The good news, of course, is that you don't have to rely on a one-size fits all
configuration value: `TORQUE_DEFAULT_TIMEOUT`. You can also override the web
hook request timeout on a task by task basis, via the `timeout` query parameter.
So, after all this, the solution is to set an appropriate timeout for
different length of tasks. Simple -- once you know how the system works.

[RQ]: http://python-rq.org/
[Resque]: https://github.com/resque/resque
[PostgreSQL]: http://www.postgresql.org
[Redis]: http://redis.io
[Gevent]: http://www.gevent.org


## Installation

Clone the repo, install the Python app using:

    pip install setuptools_git
    pip install -r requirements.txt
    pip install .

You need Redis and Postgres running. If necessary, create the database:

    createdb -T template0 -E UTF8 torque

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

* `TORQUE_BACKOFF`: `exponential` (default) or `linear`
* `TORQUE_CLEANUP_AFTER_DAYS`: how many days to leave tasks in the db for, defaults
  to `7`
* `TORQUE_DEFAULT_TIMEOUT`: how long, in seconds, to wait before treating a web
  hook request as having failed -- defaults to `60` see the algorithm section
  above for details
* `TORQUE_MIN_DUE_DELAY`: minimum delay before retrying -- don't set any lower
  than `2`
* `TORQUE_MAX_DUE_DELAY`: maximum retry delay -- defaults to `7200` but you
  should make sure its longer than `TORQUE_DEFAULT_TIMEOUT`
* `TORQUE_MAX_RETRIES`: how many attempts before giving up on a task -- defaults
  to `36`

Deployment:

* `TORQUE_AUTHENTICATE`: whether to require authentication; defaults to `False`
  -- see authentication section in Usage below
* `TORQUE_ENABLE_HSTS`: set this to `True` if you're using https
* `HSTS_PROTOCOL_HEADER`: set this to, e.g.: `X-Forwarded-Proto` if you're running
  behind an https proxy frontend
* `MODE`: defaults to `development`, set to `production` when you deploy for real

Redis:

* `TORQUE_REDIS_CHANNEL`: name of your Redis list used as a notification channel;
  defaults to `torque`
* `REDIS_URL`, etc.: see [pyramid_redis][] for details on how to configure your
  Redis connection

Database:

* `DATABASE_URL` etc.: your SQLAlchemy engine configuration string, defaults to
  `postgresql:///torque`
* other db config options are `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_SIZE` and
  `DATABASE_POOL_RECYCLE`


## Usage / API

### Authentication

If you set `TORQUE_AUTHENTICATE` to `True` then you need to create at least one
application (e.g.: using the `alembic/scripts/create_application.py` script) and
provide its api key in the `TORQUE_API_KEY` header when enqueuing a task.

### `POST /`

To enqueue a task, make a POST request to the root path of your Torque
installation.

**Required**:

* a `url` query parameter; this is the url to your web hook that you want Torque
  to call to perform your task

**Optional**:

* a `timeout` query parameter; how long, in seconds, to wait before treating the
  web hook call as having timed out -- see the Algorithm section above for context

**Data**:

This aside, you can pass through any POST data, encoded as any content type you
like. The data, content type and character encoding will be passed on in the POST
request to your web hook.

**Headers**:

Aside from the content type, length and charset headers, derived from your
request, you can specify headers to pass through to your web hook, by prefixing
the header name with `TORQUE-PASSTHROUGH-`. So, for example, to pass through
a `FOO: Bar` header, you would provide `TORQUE-PASSTHROUGH-FOO: Bar` in your
request headers.

**Response**:

You should receive a 201 response with the url to the task in the `Location`
header.

### `GET /task:id`

Returns a JSON data dict with status information about a task.


## Pro-Tips

Torque is a system for reliably calling web hook task handlers: not for
implementing them. You are responsible for implementing and exposing your own
web hooks. In most languages and frameworks this is very simple, e.g.: in Ruby
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

#### Return 200 OK

After successfully performing their task, your web hooks are expected to return
an HTTP response with a `200` status code. If not, Torque will keep retrying
the task.

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

Raise [bugs / issues on GitHub](https://github.com/thruflo/torque/issues).
