# -*- coding: utf-8 -*-

"""Boilerplate to run ``alembic`` in online mode, using the ``DATABASE_URL``
  environment variable to connect to the right database.
"""

import os

from alembic import context
from sqlalchemy import create_engine
from ntorque.model import Base

# Get a database connection.
engine = create_engine(os.environ['DATABASE_URL'])
connection = engine.connect()

# Configure the alembic environment context.
context.configure(connection=connection, target_metadata=Base.metadata)

# Run the migrations.
try:
    with context.begin_transaction():
        context.run_migrations()
finally:
    connection.close()

