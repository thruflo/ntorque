"""Initial migration.
  
  Revision ID: 4ae58a31c179
  Revises: None
  Create Date: 2014-01-30 14:33:48.166748
"""

# Revision identifiers, used by Alembic.
revision = '4ae58a31c179'
down_revision = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('ntorque_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('c', sa.DateTime(), nullable=False),
        sa.Column('m', sa.DateTime(), nullable=False),
        sa.Column('v', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('activated', sa.DateTime(), nullable=True),
        sa.Column('deactivated', sa.DateTime(), nullable=True),
        sa.Column('deleted', sa.DateTime(), nullable=True),
        sa.Column('undeleted', sa.DateTime(), nullable=True),
        sa.Column('name', sa.Unicode(length=96), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ntorque_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('c', sa.DateTime(), nullable=False),
        sa.Column('m', sa.DateTime(), nullable=False),
        sa.Column('v', sa.Integer(), nullable=False),
        sa.Column('app_id', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('timeout', sa.Integer(), nullable=False),
        sa.Column('due', sa.DateTime(), nullable=False),
        sa.Column('status', sa.Enum(u'FAILED', u'COMPLETED', u'PENDING',
                name='ntorque_task_statuses'), nullable=False),
        sa.Column('url', sa.Unicode(length=256), nullable=False),
        sa.Column('charset', sa.Unicode(length=24), nullable=False),
        sa.Column('enctype', sa.Unicode(length=256), nullable=False),
        sa.Column('headers', sa.UnicodeText(), nullable=True),
        sa.Column('body', sa.UnicodeText(), nullable=True),
        sa.ForeignKeyConstraint(['app_id'], ['ntorque_applications.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ntorque_api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('c', sa.DateTime(), nullable=False),
        sa.Column('m', sa.DateTime(), nullable=False),
        sa.Column('v', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('activated', sa.DateTime(), nullable=True),
        sa.Column('deactivated', sa.DateTime(), nullable=True),
        sa.Column('deleted', sa.DateTime(), nullable=True),
        sa.Column('undeleted', sa.DateTime(), nullable=True),
        sa.Column('app_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Unicode(length=40), nullable=False),
        sa.ForeignKeyConstraint(['app_id'], ['ntorque_applications.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('value')
    )

def downgrade():
    op.drop_table('ntorque_api_keys')
    op.drop_table('ntorque_tasks')
    op.drop_table('ntorque_applications')

