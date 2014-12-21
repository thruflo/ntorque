#!/bin/bash

if [ "$MODE" = "development" ]; then
    gunicorn --log-level=info -c gunicorn.py ntorque.api:main
else
    newrelic-admin run-program gunicorn --log-level=warn -c gunicorn.py ntorque.api:main
fi
