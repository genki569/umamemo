"""Add user_id to RaceMemo

Revision ID: a31753298031
Revises: a957190551ed
Create Date: 2024-11-07 ...

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a31753298031'
down_revision = 'a957190551ed'
branch_labels = None
depends_on = None

def upgrade():
    # 既存のテーブルにuser_idカラムを追加
    with op.batch_alter_table('race_memos') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))  # 既存データがあるのでnullable=True
        batch_op.create_foreign_key(
            'fk_race_memos_user_id',
            'users',
            ['user_id'], ['id']
        )

def downgrade():
    # 追加したカラムと制約を削除
    with op.batch_alter_table('race_memos') as batch_op:
        batch_op.drop_constraint('fk_race_memos_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')
