"""add updated_at to horses

Revision ID: edd6a0fd5416
Revises: 96241dce02eb
Create Date: 2024-11-05 15:11:39.807
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'edd6a0fd5416'
down_revision = '96241dce02eb'
branch_labels = None
depends_on = None


def upgrade():
    # 一時テーブルが存在する場合は削除
    op.execute('DROP TABLE IF EXISTS _alembic_tmp_users')
    
    # horsesテーブルの更新（こちらを先に実行）
    with op.batch_alter_table('horses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), 
                          server_default=sa.text('CURRENT_TIMESTAMP'),
                          nullable=True))
        op.execute('UPDATE horses SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL')

    # usersテーブルの更新
    op.execute('UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL')
    op.execute('UPDATE users SET is_premium = 0 WHERE is_premium IS NULL')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('created_at',
                            existing_type=sa.DateTime(),
                            server_default=sa.text('CURRENT_TIMESTAMP'),
                            nullable=False)
        batch_op.alter_column('is_premium',
                            existing_type=sa.BOOLEAN(),
                            server_default=sa.text('0'),
                            nullable=False)


def downgrade():
    with op.batch_alter_table('horses', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('created_at',
                            existing_type=sa.DateTime(),
                            nullable=True,
                            server_default=None)
        batch_op.alter_column('is_premium',
                            existing_type=sa.BOOLEAN(),
                            nullable=True,
                            server_default=None)
