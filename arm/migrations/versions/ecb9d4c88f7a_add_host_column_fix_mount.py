"""add host column, fix mount

Revision ID: ecb9d4c88f7a
Revises: e688fe04d305
Create Date: 2022-02-28 11:42:51.650003

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ecb9d4c88f7a'
down_revision = 'c54d68996895'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job', sa.Column('host', sa.String(length=256), nullable=True))
    op.alter_column('job','mountpoint', type_=sa.String(length=256))

def downgrade():
    op.drop_column('job', 'host')
    op.alter_column('job', 'mountpoint', type_=sa.String(length=20))
