"""add_race_unique_identifiers

Revision ID: 3c278b933cdd
Revises: a31753298031
Create Date: 2024-11-07 03:45:47.243458

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c278b933cdd'
down_revision = 'a31753298031'
branch_labels = None
depends_on = None


def upgrade():
    # SQLiteの制約に対応するためbatch_alter_tableを使用
    with op.batch_alter_table('races') as batch_op:
        # 1. venue_idカラムの追加（既存のvenueカラムは残したまま）
        batch_op.add_column(sa.Column('venue_id', sa.Integer(), nullable=True))
        
        # 2. race_numberカラムの追加
        batch_op.add_column(sa.Column('race_number', sa.Integer(), nullable=True))
        
        # 3. 開催年を明示的に保存するカラムを追加
        batch_op.add_column(sa.Column('race_year', sa.Integer(), nullable=True))
        
        # 4. 開催回を保存するカラムを追加
        batch_op.add_column(sa.Column('kai', sa.Integer(), nullable=True))
        
        # 5. 開催日を保存するカラムを追加
        batch_op.add_column(sa.Column('nichi', sa.Integer(), nullable=True))


def downgrade():
    # ロールバック用の処理
    with op.batch_alter_table('races') as batch_op:
        batch_op.drop_column('nichi')
        batch_op.drop_column('kai')
        batch_op.drop_column('race_year')
        batch_op.drop_column('race_number')
        batch_op.drop_column('venue_id')
