-- Phase 2 ML tables - Model versioning, predictions, annotations, chunks
-- Run this SQL directly against the RDS database via AWS RDS Query Editor
-- Or use an SSH tunnel/bastion host

-- Add embedding columns to articles table
ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedding DOUBLE PRECISION[];
ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMP WITH TIME ZONE;

-- Create article_annotations table
CREATE TABLE IF NOT EXISTS article_annotations (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    user_id VARCHAR(255),
    annotation_type VARCHAR(50) NOT NULL,
    selected_text TEXT NOT NULL,
    start_position INTEGER,
    end_position INTEGER,
    context_before TEXT,
    context_after TEXT,
    confidence_score DOUBLE PRECISION,
    embedding DOUBLE PRECISION[],
    embedding_model VARCHAR(100),
    embedded_at TIMESTAMP WITH TIME ZONE,
    used_for_training BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_article_annotations_article_id ON article_annotations(article_id);
CREATE INDEX IF NOT EXISTS ix_article_annotations_used_for_training ON article_annotations(used_for_training);

-- Create chunk_analysis_results table
CREATE TABLE IF NOT EXISTS chunk_analysis_results (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    ml_prediction VARCHAR(50) NOT NULL,
    ml_confidence DOUBLE PRECISION NOT NULL,
    hunt_score DOUBLE PRECISION,
    passed_filter BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chunk_analysis_results_article_id ON chunk_analysis_results(article_id);
CREATE INDEX IF NOT EXISTS idx_article_chunk ON chunk_analysis_results(article_id, chunk_index);

-- Create chunk_classification_feedback table
CREATE TABLE IF NOT EXISTS chunk_classification_feedback (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunk_analysis_results(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    model_classification VARCHAR(50) NOT NULL,
    model_confidence DOUBLE PRECISION NOT NULL,
    is_correct BOOLEAN NOT NULL,
    user_classification VARCHAR(50),
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chunk_classification_feedback_article_id ON chunk_classification_feedback(article_id);
CREATE INDEX IF NOT EXISTS ix_chunk_classification_feedback_chunk_id ON chunk_classification_feedback(chunk_id);

-- Create ml_model_versions table
CREATE TABLE IF NOT EXISTS ml_model_versions (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    s3_bucket VARCHAR(255),
    s3_key VARCHAR(500),
    model_hash VARCHAR(64),
    training_samples INTEGER,
    training_config JSONB,
    training_duration_seconds DOUBLE PRECISION,
    trained_at TIMESTAMP WITH TIME ZONE,
    accuracy DOUBLE PRECISION,
    precision DOUBLE PRECISION,
    recall DOUBLE PRECISION,
    f1_score DOUBLE PRECISION,
    confusion_matrix JSONB,
    classification_report JSONB,
    test_accuracy DOUBLE PRECISION,
    test_f1_score DOUBLE PRECISION,
    evaluation_results JSONB,
    evaluated_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    deployed_at TIMESTAMP WITH TIME ZONE,
    deployment_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_model_name_version UNIQUE (model_name, version)
);

CREATE INDEX IF NOT EXISTS ix_ml_model_versions_model_name ON ml_model_versions(model_name);
CREATE INDEX IF NOT EXISTS ix_ml_model_versions_is_active ON ml_model_versions(is_active);
CREATE INDEX IF NOT EXISTS idx_active_model ON ml_model_versions(model_name, is_active);

-- Create ml_prediction_logs table
CREATE TABLE IF NOT EXISTS ml_prediction_logs (
    id SERIAL PRIMARY KEY,
    model_version_id INTEGER REFERENCES ml_model_versions(id) ON DELETE SET NULL,
    article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunk_analysis_results(id) ON DELETE CASCADE,
    input_text TEXT NOT NULL,
    input_hash VARCHAR(64) NOT NULL,
    prediction VARCHAR(50) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    prediction_probabilities JSONB,
    inference_time_ms DOUBLE PRECISION,
    feature_importance JSONB,
    feedback_correct BOOLEAN,
    feedback_label VARCHAR(50),
    feedback_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ml_prediction_logs_model_version_id ON ml_prediction_logs(model_version_id);
CREATE INDEX IF NOT EXISTS ix_ml_prediction_logs_article_id ON ml_prediction_logs(article_id);
CREATE INDEX IF NOT EXISTS ix_ml_prediction_logs_chunk_id ON ml_prediction_logs(chunk_id);
CREATE INDEX IF NOT EXISTS ix_ml_prediction_logs_input_hash ON ml_prediction_logs(input_hash);
CREATE INDEX IF NOT EXISTS idx_prediction_feedback ON ml_prediction_logs(feedback_correct, created_at);

-- Mark migration as complete in alembic_version
INSERT INTO alembic_version (version_num) VALUES ('0002')
ON CONFLICT DO NOTHING;

-- Done!
SELECT 'Phase 2 ML tables created successfully' as status;
