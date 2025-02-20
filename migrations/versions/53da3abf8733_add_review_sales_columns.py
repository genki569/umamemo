"""add review sales columns

Revision ID: 53da3abf8733
Revises: edd6a0fd5416
Create Date: 2024-11-06 00:50:31.239110

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '53da3abf8733'
down_revision = 'edd6a0fd5416'
branch_labels = None
depends_on = None


def upgrade():
    # review_purchasesテーブルを作成
    op.create_table('review_purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('price_paid', sa.Integer(), nullable=False),
        sa.Column('purchase_date', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='completed'),
        sa.ForeignKeyConstraint(['review_id'], ['race_reviews.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # race_reviewsテーブルに新しいカラムを追加
    with op.batch_alter_table('race_reviews', schema=None) as batch_op:
        batch_op.add_column(sa.Column('price', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('sale_status', sa.String(length=20), nullable=False, server_default='free'))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))


def downgrade():
    # race_reviewsテーブルから追加したカラムを削除
    with op.batch_alter_table('race_reviews', schema=None) as batch_op:
        batch_op.drop_column('description')
        batch_op.drop_column('sale_status')
        batch_op.drop_column('price')

    # review_purchasesテーブルを削除
    op.drop_table('review_purchases')
