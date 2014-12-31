#!/bin/bash

if [ "$MODE" = "production" ]; then
    newrelic-admin run-program gunicorn --log-level=warn -c gunicorn.py ntorque.api:main
else
    gunicorn --log-level=info -c gunicorn.py ntorque.api:main
fi
