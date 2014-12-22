"""Add request ``method`` to ``ntorque_tasks``.

  Revision ID: 32ee88d6d6d
  Revises: 4ae58a31c179
  Created: 2014-12-22 10:36:23.871146
"""

# Revision identifiers, used by Alembic.
revision = '32ee88d6d6d'
down_revision = '4ae58a31c179'

from alembic import op
import sqlalchemy as sa

from sqlalchemy.sql import table, column

from ntorque.model.orm import Task

def upgrade():
    bind = op.get_bind()
    typ = Task.__table__.c.method.type
    impl = typ.dialect_impl(bind.dialect)
    impl.create(bind, checkfirst=True)
    # Add with ``nullable=True``.
    op.add_column(
        'ntorque_tasks', 
        sa.Column(
            'method', 
            sa.Enum(
                u'DELETE', u'PATCH', u'POST', u'PUT',
                name='ntorque_request_methods'
            ),
            nullable=True
        )
    )
    # Set the default value.
    tasks = table('ntorque_tasks', column('method'))
    op.execute(tasks.update().values(method=u'POST'))
    # Now we can set ``nullable=False``.
    op.alter_column('ntorque_tasks', 'method', nullable=False)

def downgrade():
    op.drop_column('ntorque_tasks', 'method')
