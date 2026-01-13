"""Initial Phase 1 schema - Sources, Articles, SourceChecks

Revision ID: 0001
Revises:
Create Date: 2024-12-01

This migration creates the core tables needed for Phase 1:
- sources: Threat intelligence source configuration
- articles: Scraped article content
- source_checks: Source check history
- content_hashes: Deduplication tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pgvector extension (required for embeddings in later phases)
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('identifier', sa.String(255), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('rss_url', sa.Text(), nullable=True),
        sa.Column('check_frequency', sa.Integer(), nullable=False, server_default='1800'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_articles', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('identifier')
    )
    op.create_index('ix_sources_identifier', 'sources', ['identifier'])

    # Create articles table
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('canonical_url', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('authors', postgresql.JSON(), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('article_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('processing_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('canonical_url'),
        sa.UniqueConstraint('content_hash')
    )
    op.create_index('ix_articles_source_id', 'articles', ['source_id'])
    op.create_index('ix_articles_canonical_url', 'articles', ['canonical_url'])
    op.create_index('ix_articles_content_hash', 'articles', ['content_hash'])
    op.create_index('ix_articles_published_at', 'articles', ['published_at'])
    op.create_index('ix_articles_processing_status', 'articles', ['processing_status'])
    op.create_index('ix_articles_archived', 'articles', ['archived'])

    # Create source_checks table
    op.create_table(
        'source_checks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('check_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('method', sa.String(50), nullable=False),
        sa.Column('articles_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('check_metadata', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_source_checks_source_id', 'source_checks', ['source_id'])
    op.create_index('ix_source_checks_check_time', 'source_checks', ['check_time'])

    # Create content_hashes table
    op.create_table(
        'content_hashes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('content_hash')
    )
    op.create_index('ix_content_hashes_content_hash', 'content_hashes', ['content_hash'])
    op.create_index('ix_content_hashes_article_id', 'content_hashes', ['article_id'])


def downgrade() -> None:
    op.drop_table('content_hashes')
    op.drop_table('source_checks')
    op.drop_table('articles')
    op.drop_table('sources')
    op.execute('DROP EXTENSION IF EXISTS vector')
