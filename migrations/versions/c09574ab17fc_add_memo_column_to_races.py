"""add memo column to races

Revision ID: c09574ab17fc
Revises: ad9aa95aa1f3
Create Date: 2024-11-05 05:11:10.410696

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c09574ab17fc'
down_revision = 'ad9aa95aa1f3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('races', schema=None) as batch_op:
        batch_op.add_column(sa.Column('memo', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('races', schema=None) as batch_op:
        batch_op.drop_column('memo')

    # ### end Alembic commands ###
