"""initial_schema

Revision ID: 000
Revises: 
Create Date: 2025-07-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create initial database schema with all required tables"""
    
    # Create user_thread_table for OpenAI thread management
    op.create_table('user_thread_table',
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False, server_default='line'),
        sa.Column('thread_id', sa.String(255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('user_id', 'platform')
    )
    
    # Create simple_conversation_history for non-OpenAI models
    op.create_table('simple_conversation_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False, server_default='line'),
        sa.Column('model_provider', sa.String(50), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better query performance
    
    # Indexes for user_thread_table
    op.create_index('idx_thread_user_platform', 'user_thread_table', ['user_id', 'platform'])
    op.create_index('idx_thread_created_at', 'user_thread_table', ['created_at'])
    
    # Indexes for simple_conversation_history
    op.create_index('idx_conversation_user_platform', 'simple_conversation_history', ['user_id', 'platform'])
    op.create_index('idx_conversation_user_platform_provider', 'simple_conversation_history', ['user_id', 'platform', 'model_provider'])
    op.create_index('idx_conversation_created_at', 'simple_conversation_history', ['created_at'])
    op.create_index('idx_user_model_recent', 'simple_conversation_history', ['user_id', 'model_provider', 'created_at'])


def downgrade():
    """Drop all tables and indexes"""
    
    # Drop indexes first
    op.drop_index('idx_user_model_recent', 'simple_conversation_history')
    op.drop_index('idx_conversation_created_at', 'simple_conversation_history')
    op.drop_index('idx_conversation_user_platform_provider', 'simple_conversation_history')
    op.drop_index('idx_conversation_user_platform', 'simple_conversation_history')
    op.drop_index('idx_thread_created_at', 'user_thread_table')
    op.drop_index('idx_thread_user_platform', 'user_thread_table')
    
    # Drop tables
    op.drop_table('simple_conversation_history')
    op.drop_table('user_thread_table')