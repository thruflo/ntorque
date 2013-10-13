
# Torque - web hook task queue

Torque is a [task](http://www.celeryproject.org)
[queue](https://github.com/resque/resque) service that uses [web hooks][].
You can use it from any programming language (that speaks HTTP) to queue
up and reliably execute idempotent tasks.

For example, in Python:

```python
import os
import requests

params = {'url': 'http://example.com/myhooks/send_welcome_email'}
data = {'new_user_id': 1234}

endpoint = os.environ.get('torque.URL')
response = requests.post(endpoint, data=data, params=params)
```

Torque is free, open source software [released into the public domain][] with
no license restrictions. It is packaged for deployment as a [Chef cookbook][],
for development [using Vagrant][] and is provided as a hosted service by
[nTorque.com][].

[web hooks]: http://timothyfitz.com/2009/02/09/what-webhooks-are-and-why-you-should-care/
[released into the public domain]: http://unlicense.org/UNLICENSE
[Chef cookbook]: https://github.com/thruflo/torque-cookbook 
[using Vagrant]: https://github.com/thruflo/torque-vagrant
[nTorque.com]: http://www.ntorque.com

## Rationale

Torque is designed to be a good solution when you need more reliability than
fire-and-forget but you don't need an [AMPQ][] / [ESB][] sledgehammer to crack
your "do this later" nut.

Because it uses web hooks, you can:

1. use it from (and to integrate) applications written in any language
1. use DNS / web server load balancing to distribute tasks
1. bootstrap your task execution environment the way you bootstrap a web
   application -- i.e.: once at startup, potentially re-using your web
   application's configuration and middleware stack

[AMPQ]: http://www.rabbitmq.com
[ESB]: http://en.wikipedia.org/wiki/Enterprise_service_bus

## Functionality

Torque provides the following endpoints:

* `POST /` to enqueue a task
* `GET /stats` to view usage statistics
* `GET /tasks/:id` to view task status
* `DELETE /tasks/:id` to delete a task
* `DELETE /` to delete all tasks

And the following features:

* persistent task storage
* non-blocking, concurrent task execution
* HTTPS and redirect support
* linear backoff to retry tasks that fail due to network errors
* exponential backoff for tasks that respond with an HTTP error

## Implementation

Torque is a Python application comprising of a web application and one or more
worker processes. These use a [PostgreSQL][] database to persist tasks and a
[Redis][] database as a notification channel. The whole stack is patched with
[Gevent][] so task storage and execution are non-blocking.

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

When the web hook returns with a 200 response, the task is marked as `completed`.
Completed tasks are periodically deleted after a configurable time period. When
the web hook call fails or returns a non-200 response code (after redirects have
been followed), the task is set to `retry` after a delay (based on the backoff
algorithms [described above](#functionality)). These are picked up by a
background process which polls the database for tasks to be retried.

[PostgreSQL]: http://www.postgresql.org
[Redis]: http://redis.io
[Gevent]: http://www.gevent.org

## Installation

Because Torque has a number of moving parts, it's recommended that you install
it in a VM / container using the [chef cookbook][] provided. For example, using
[librarian-chef][] add the following lines to your `Cheffile`:

```ruby
cookbook "torque",
    :git => "https://github.com/thruflo/torque-cookbook"
```

Then in your `node.json`, add the torque recipe to your `run_list` and override
any configuration attributes:

```javascript
{
  "torque": {
    // override attributes here
  },
  ...
  "run_list": [
      "recipe[torque]"
      ...
    ]
  }
}
```

As a convenience, you can get a development environment up and running using
[Vagrant][] by cloning the [torque-vagrant][] repo and running `vagrant up`
(which provisions the environment using [chef-solo][]):

```shell
git clone https://github.com/thruflo/torque-vagrant.git
cd torque-vagrant
vagrant up
```

[librarian-chef]: https://github.com/applicationsonline/librarian-chef
[chef cookbook]: https://github.com/thruflo/torque-cookbook 
[Vagrant]: http://www.vagrantup.com
[torque-vagrant]: https://github.com/thruflo/torque-vagrant
[Chef-solo]: http://docs.opscode.com/chef_solo.html

## Configuration

XXX todo:

* `torque.SHOULD_AUTHENTICATE`
* `torque.enable_hsts`
* ...

## Usage / API

XXX todo:

* `api_key` header
* document endpoints

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

    Timeout 1800
    ProxyTimeout 1800

Or with [Nginx][]:

    send_timeout 1800;
    proxy_send_timeout 1800;

[Apache]: http://httpd.apache.org
[Nginx]: http://nginx.org

#### Secure Public Hooks

If your web hooks are exposed on a public IP, you are likely to want to secure
them, e.g.: using HTTPS and an authentication credential like an API key.

It's also worth noting that you may need to turn off [CSRF validation][].

[CSRF validation]: http://en.wikipedia.org/wiki/Cross-site_request_forgery#Prevention

## Support

Raise [bugs / issues on GitHub](https://github.com/thruflo/torque/issues).
