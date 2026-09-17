"""create click_events table

Revision ID: 28a92f01bc44
Revises: 14ced21d31f6
Create Date: 2026-09-17 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28a92f01bc44'
down_revision: Union[str, Sequence[str], None] = '14ced21d31f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'click_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('url_id', sa.Integer(), nullable=False),
        sa.Column('clicked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('referrer', sa.String(length=512), nullable=True),
        sa.Column('user_agent_family', sa.String(length=128), nullable=True),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['url_id'], ['urls.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_click_events_url_id', 'click_events', ['url_id'], unique=False)
    op.create_index('ix_click_events_clicked_at', 'click_events', ['clicked_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_click_events_clicked_at', table_name='click_events')
    op.drop_index('ix_click_events_url_id', table_name='click_events')
    op.drop_table('click_events')
