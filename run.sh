#!/bin/bash

if [ "$MODE" = "production" ]; then
    newrelic-admin run-program gunicorn --log-config logging.prod.ini -c gunicorn_config.py ntorque.api:main
else
    gunicorn --log-config logging.dev.ini -c gunicorn_config.py ntorque.api:main
fi
