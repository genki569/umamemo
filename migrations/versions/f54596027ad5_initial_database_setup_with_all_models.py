"""initial database setup with all models

Revision ID: f54596027ad5
Revises: 
Create Date: 2024-11-05 03:19:22.577037

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f54596027ad5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('horses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('sex', sa.String(length=10), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('jockeys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('races',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('date', sa.String(length=10), nullable=True),
    sa.Column('start_time', sa.String(length=10), nullable=True),
    sa.Column('track_type', sa.String(length=20), nullable=True),
    sa.Column('distance', sa.Integer(), nullable=True),
    sa.Column('direction', sa.String(length=20), nullable=True),
    sa.Column('weather', sa.String(length=20), nullable=True),
    sa.Column('track_condition', sa.String(length=20), nullable=True),
    sa.Column('venue', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.Column('is_premium', sa.Boolean(), nullable=True),
    sa.Column('trial_start', sa.DateTime(), nullable=True),
    sa.Column('trial_end', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('race_id', sa.Integer(), nullable=False),
    sa.Column('horse_id', sa.Integer(), nullable=False),
    sa.Column('jockey_id', sa.Integer(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('frame_number', sa.Integer(), nullable=True),
    sa.Column('horse_number', sa.Integer(), nullable=True),
    sa.Column('weight', sa.Float(), nullable=True),
    sa.Column('odds', sa.Float(), nullable=True),
    sa.Column('popularity', sa.Integer(), nullable=True),
    sa.Column('time', sa.String(length=10), nullable=True),
    sa.Column('margin', sa.String(length=20), nullable=True),
    sa.Column('passing', sa.String(length=20), nullable=True),
    sa.Column('last_3f', sa.Float(), nullable=True),
    sa.Column('horse_weight', sa.Integer(), nullable=True),
    sa.Column('weight_change', sa.Integer(), nullable=True),
    sa.Column('prize', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['horse_id'], ['horses.id'], ),
    sa.ForeignKeyConstraint(['jockey_id'], ['jockeys.id'], ),
    sa.ForeignKeyConstraint(['race_id'], ['races.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('favorites',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('horse_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['horse_id'], ['horses.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('race_reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('race_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('pace_analysis', sa.Text(), nullable=True),
    sa.Column('track_condition_note', sa.Text(), nullable=True),
    sa.Column('race_flow', sa.Text(), nullable=True),
    sa.Column('overall_impression', sa.Text(), nullable=True),
    sa.Column('winner_analysis', sa.Text(), nullable=True),
    sa.Column('placed_horses_analysis', sa.Text(), nullable=True),
    sa.Column('notable_performances', sa.Text(), nullable=True),
    sa.Column('future_prospects', sa.Text(), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=True),
    sa.Column('is_premium', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['race_id'], ['races.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('race_reviews')
    op.drop_table('favorites')
    op.drop_table('entries')
    op.drop_table('users')
    op.drop_table('races')
    op.drop_table('jockeys')
    op.drop_table('horses')
    # ### end Alembic commands ###
