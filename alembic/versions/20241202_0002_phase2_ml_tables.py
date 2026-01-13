"""Phase 2 ML tables - Model versioning, predictions, annotations, chunks

Revision ID: 0002
Revises: 0001
Create Date: 2024-12-02

This migration creates the ML infrastructure tables for Phase 2:
- article_annotations: User annotations for ML training
- chunk_analysis_results: ML chunk classification results
- chunk_classification_feedback: User feedback on predictions
- ml_model_versions: Model version tracking
- ml_prediction_logs: Prediction logging for monitoring

Also adds embedding columns to articles table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add embedding columns to articles table
    op.add_column('articles', sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True))
    op.add_column('articles', sa.Column('embedding_model', sa.String(100), nullable=True))
    op.add_column('articles', sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True))

    # Create article_annotations table
    op.create_table(
        'article_annotations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=True),
        sa.Column('annotation_type', sa.String(50), nullable=False),
        sa.Column('selected_text', sa.Text(), nullable=False),
        sa.Column('start_position', sa.Integer(), nullable=True),
        sa.Column('end_position', sa.Integer(), nullable=True),
        sa.Column('context_before', sa.Text(), nullable=True),
        sa.Column('context_after', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('embedding_model', sa.String(100), nullable=True),
        sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_for_training', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_article_annotations_article_id', 'article_annotations', ['article_id'])
    op.create_index('ix_article_annotations_used_for_training', 'article_annotations', ['used_for_training'])

    # Create chunk_analysis_results table
    op.create_table(
        'chunk_analysis_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('ml_prediction', sa.String(50), nullable=False),
        sa.Column('ml_confidence', sa.Float(), nullable=False),
        sa.Column('hunt_score', sa.Float(), nullable=True),
        sa.Column('passed_filter', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chunk_analysis_results_article_id', 'chunk_analysis_results', ['article_id'])
    op.create_index('idx_article_chunk', 'chunk_analysis_results', ['article_id', 'chunk_index'])

    # Create chunk_classification_feedback table
    op.create_table(
        'chunk_classification_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('chunk_id', sa.Integer(), nullable=True),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('model_classification', sa.String(50), nullable=False),
        sa.Column('model_confidence', sa.Float(), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('user_classification', sa.String(50), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chunk_id'], ['chunk_analysis_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chunk_classification_feedback_article_id', 'chunk_classification_feedback', ['article_id'])
    op.create_index('ix_chunk_classification_feedback_chunk_id', 'chunk_classification_feedback', ['chunk_id'])

    # Create ml_model_versions table
    op.create_table(
        'ml_model_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_name', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('model_type', sa.String(100), nullable=False),
        sa.Column('s3_bucket', sa.String(255), nullable=True),
        sa.Column('s3_key', sa.String(500), nullable=True),
        sa.Column('model_hash', sa.String(64), nullable=True),
        sa.Column('training_samples', sa.Integer(), nullable=True),
        sa.Column('training_config', postgresql.JSONB(), nullable=True),
        sa.Column('training_duration_seconds', sa.Float(), nullable=True),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('precision', sa.Float(), nullable=True),
        sa.Column('recall', sa.Float(), nullable=True),
        sa.Column('f1_score', sa.Float(), nullable=True),
        sa.Column('confusion_matrix', postgresql.JSONB(), nullable=True),
        sa.Column('classification_report', postgresql.JSONB(), nullable=True),
        sa.Column('test_accuracy', sa.Float(), nullable=True),
        sa.Column('test_f1_score', sa.Float(), nullable=True),
        sa.Column('evaluation_results', postgresql.JSONB(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deployment_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_name', 'version', name='uq_model_name_version')
    )
    op.create_index('ix_ml_model_versions_model_name', 'ml_model_versions', ['model_name'])
    op.create_index('ix_ml_model_versions_is_active', 'ml_model_versions', ['is_active'])
    op.create_index('idx_active_model', 'ml_model_versions', ['model_name', 'is_active'])

    # Create ml_prediction_logs table
    op.create_table(
        'ml_prediction_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_version_id', sa.Integer(), nullable=True),
        sa.Column('article_id', sa.Integer(), nullable=True),
        sa.Column('chunk_id', sa.Integer(), nullable=True),
        sa.Column('input_text', sa.Text(), nullable=False),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('prediction', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('prediction_probabilities', postgresql.JSONB(), nullable=True),
        sa.Column('inference_time_ms', sa.Float(), nullable=True),
        sa.Column('feature_importance', postgresql.JSONB(), nullable=True),
        sa.Column('feedback_correct', sa.Boolean(), nullable=True),
        sa.Column('feedback_label', sa.String(50), nullable=True),
        sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['model_version_id'], ['ml_model_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chunk_id'], ['chunk_analysis_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ml_prediction_logs_model_version_id', 'ml_prediction_logs', ['model_version_id'])
    op.create_index('ix_ml_prediction_logs_article_id', 'ml_prediction_logs', ['article_id'])
    op.create_index('ix_ml_prediction_logs_chunk_id', 'ml_prediction_logs', ['chunk_id'])
    op.create_index('ix_ml_prediction_logs_input_hash', 'ml_prediction_logs', ['input_hash'])
    op.create_index('idx_prediction_feedback', 'ml_prediction_logs', ['feedback_correct', 'created_at'])


def downgrade() -> None:
    op.drop_table('ml_prediction_logs')
    op.drop_table('ml_model_versions')
    op.drop_table('chunk_classification_feedback')
    op.drop_table('chunk_analysis_results')
    op.drop_table('article_annotations')
    op.drop_column('articles', 'embedded_at')
    op.drop_column('articles', 'embedding_model')
    op.drop_column('articles', 'embedding')
