#!/bin/bash

if [ "$MODE" = "production" ]; then
    newrelic-admin run-program gunicorn --log-level=warn -c gunicorn_config.py ntorque.api:main
else
    gunicorn --log-level=info -c gunicorn_config.py ntorque.api:main
fi
