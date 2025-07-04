"""add_platform_support

Revision ID: 001
Revises: 
Create Date: 2025-07-03 07:53:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = '000'
branch_labels = None
depends_on = None


def upgrade():
    """Add platform support to both user_thread_table and simple_conversation_history"""
    
    # Add platform column to user_thread_table with default value
    op.add_column('user_thread_table', sa.Column('platform', sa.String(50), nullable=False, server_default='line'))
    
    # Drop existing primary key and create new composite primary key
    op.drop_constraint('user_thread_table_pkey', 'user_thread_table', type_='primary')
    op.create_primary_key('user_thread_table_pkey', 'user_thread_table', ['user_id', 'platform'])
    
    # Add platform column to simple_conversation_history with default value
    op.add_column('simple_conversation_history', sa.Column('platform', sa.String(50), nullable=False, server_default='line'))
    
    # Create indexes for better query performance
    op.create_index('idx_conversation_user_platform', 'simple_conversation_history', ['user_id', 'platform'])
    op.create_index('idx_conversation_user_platform_provider', 'simple_conversation_history', ['user_id', 'platform', 'model_provider'])


def downgrade():
    """Remove platform support"""
    
    # Drop indexes
    op.drop_index('idx_conversation_user_platform_provider', 'simple_conversation_history')
    op.drop_index('idx_conversation_user_platform', 'simple_conversation_history')
    
    # Remove platform column from simple_conversation_history
    op.drop_column('simple_conversation_history', 'platform')
    
    # Restore original primary key for user_thread_table
    op.drop_constraint('user_thread_table_pkey', 'user_thread_table', type_='primary')
    op.create_primary_key('user_thread_table_pkey', 'user_thread_table', ['user_id'])
    
    # Remove platform column from user_thread_table
    op.drop_column('user_thread_table', 'platform')