"""Database models for CTI Scraper"""
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base


class Source(Base):
    """Source configuration and health metrics"""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identifier = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    rss_url = Column(Text, nullable=True)
    check_frequency = Column(Integer, nullable=False, default=1800)  # seconds
    active = Column(Boolean, nullable=False, default=True)
    last_check = Column(DateTime(timezone=True), nullable=True)
    last_success = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    total_articles = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    articles = relationship("Article", back_populates="source")
    checks = relationship("SourceCheck", back_populates="source")


class Article(Base):
    """Article content and metadata"""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_url = Column(Text, nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    modified_at = Column(DateTime(timezone=True), nullable=True)
    authors = Column(JSON, nullable=True)  # Array of author names
    tags = Column(JSON, nullable=True)  # Array of tags
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA256
    article_metadata = Column(JSONB, nullable=True)  # Hunt scores, OS detection, etc.
    discovered_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    processing_status = Column(String(50), nullable=False, default="pending", index=True)
    word_count = Column(Integer, nullable=True)

    # Embedding fields
    embedding = Column(Vector(768), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived = Column(Boolean, nullable=False, default=False, index=True)

    # Relationships
    source = relationship("Source", back_populates="articles")
    annotations = relationship("ArticleAnnotation", back_populates="article")
    chunks = relationship("ChunkAnalysisResult", back_populates="article")
    workflow_executions = relationship("AgenticWorkflowExecution", back_populates="article")
    sigma_matches = relationship("ArticleSigmaMatch", back_populates="article")


class SourceCheck(Base):
    """Source check history"""
    __tablename__ = "source_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    check_time = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    success = Column(Boolean, nullable=False)
    method = Column(String(50), nullable=False)  # 'rss' or 'scrape'
    articles_found = Column(Integer, nullable=False, default=0)
    response_time = Column(Float, nullable=True)  # milliseconds
    error_message = Column(Text, nullable=True)
    check_metadata = Column(JSON, nullable=True)

    # Relationships
    source = relationship("Source", back_populates="checks")


class ArticleAnnotation(Base):
    """User annotations for ML training"""
    __tablename__ = "article_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(255), nullable=True)  # For future multi-user support
    annotation_type = Column(String(50), nullable=False)  # 'huntable' or 'not_huntable'
    selected_text = Column(Text, nullable=False)
    start_position = Column(Integer, nullable=True)
    end_position = Column(Integer, nullable=True)
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Embedding fields
    embedding = Column(Vector(768), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)

    used_for_training = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    article = relationship("Article", back_populates="annotations")


class ContentHash(Base):
    """Content hash tracking for deduplication"""
    __tablename__ = "content_hashes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    first_seen = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ChunkAnalysisResult(Base):
    """ML chunk classification results"""
    __tablename__ = "chunk_analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    ml_prediction = Column(String(50), nullable=False)  # 'huntable' or 'not_huntable'
    ml_confidence = Column(Float, nullable=False)
    hunt_score = Column(Float, nullable=True)
    passed_filter = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    article = relationship("Article", back_populates="chunks")
    feedbacks = relationship("ChunkClassificationFeedback", back_populates="chunk")

    __table_args__ = (
        Index("idx_article_chunk", "article_id", "chunk_index"),
    )


class ChunkClassificationFeedback(Base):
    """User feedback on ML predictions"""
    __tablename__ = "chunk_classification_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("chunk_analysis_results.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_text = Column(Text, nullable=False)
    model_classification = Column(String(50), nullable=False)
    model_confidence = Column(Float, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    user_classification = Column(String(50), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    chunk = relationship("ChunkAnalysisResult", back_populates="feedbacks")


class AgenticWorkflowConfig(Base):
    """Workflow configuration"""
    __tablename__ = "agentic_workflow_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    min_hunt_score = Column(Integer, nullable=False, default=70)
    junk_filter_threshold = Column(Float, nullable=False, default=0.7)
    is_active = Column(Boolean, nullable=False, default=True)
    agent_models = Column(JSONB, nullable=True)  # Model configuration per agent
    agent_prompts = Column(JSONB, nullable=True)  # Custom prompts per agent
    qa_enabled = Column(JSONB, nullable=True)  # QA settings per agent
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    executions = relationship("AgenticWorkflowExecution", back_populates="config")


class AgenticWorkflowExecution(Base):
    """Workflow execution tracking"""
    __tablename__ = "agentic_workflow_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    config_id = Column(Integer, ForeignKey("agentic_workflow_config.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    current_step = Column(String(100), nullable=True)

    # Step results
    ranking_score = Column(Float, nullable=True)
    ranking_reasoning = Column(Text, nullable=True)
    os_detection_result = Column(JSONB, nullable=True)
    extraction_result = Column(JSONB, nullable=True)
    sigma_rules = Column(JSONB, nullable=True)
    similarity_results = Column(JSONB, nullable=True)

    termination_reason = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    article = relationship("Article", back_populates="workflow_executions")
    config = relationship("AgenticWorkflowConfig", back_populates="executions")


class SigmaRule(Base):
    """SIGMA detection rules"""
    __tablename__ = "sigma_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(255), nullable=False, unique=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    logsource = Column(JSONB, nullable=False)
    detection = Column(JSONB, nullable=False)
    tags = Column(JSONB, nullable=True)
    level = Column(String(50), nullable=True)
    falsepositives = Column(JSONB, nullable=True)
    author = Column(String(500), nullable=True)
    date = Column(DateTime(timezone=True), nullable=True)
    modified = Column(DateTime(timezone=True), nullable=True)
    references = Column(JSONB, nullable=True)

    # Embedding fields for similarity search
    title_embedding = Column(Vector(768), nullable=True)
    description_embedding = Column(Vector(768), nullable=True)
    tags_embedding = Column(Vector(768), nullable=True)
    signature_embedding = Column(Vector(768), nullable=True)  # Combined embedding
    embedded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    article_matches = relationship("ArticleSigmaMatch", back_populates="sigma_rule")


class ArticleSigmaMatch(Base):
    """Article-to-SIGMA rule matches"""
    __tablename__ = "article_sigma_matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    sigma_rule_id = Column(Integer, ForeignKey("sigma_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=False)
    match_type = Column(String(50), nullable=False)  # 'title', 'description', 'tags', 'signature'
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    article = relationship("Article", back_populates="sigma_matches")
    sigma_rule = relationship("SigmaRule", back_populates="article_matches")

    __table_args__ = (
        Index("idx_article_sigma", "article_id", "sigma_rule_id"),
    )


class SigmaRuleQueue(Base):
    """Queue for human review of generated SIGMA rules"""
    __tablename__ = "sigma_rule_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_execution_id = Column(Integer, ForeignKey("agentic_workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_yaml = Column(Text, nullable=False)
    rule_data = Column(JSONB, nullable=False)
    similarity_max = Column(Float, nullable=True)
    similarity_results = Column(JSONB, nullable=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class MLModelVersion(Base):
    """ML model version tracking for content classification"""
    __tablename__ = "ml_model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(255), nullable=False, index=True)  # e.g., 'content_filter', 'junk_classifier'
    version = Column(String(50), nullable=False)  # e.g., 'v1.0.0', '2024-01-15'
    model_type = Column(String(100), nullable=False)  # e.g., 'sklearn_svm', 'pytorch_transformer'

    # Model storage
    s3_bucket = Column(String(255), nullable=True)
    s3_key = Column(String(500), nullable=True)
    model_hash = Column(String(64), nullable=True)  # SHA256 of model file

    # Training metadata
    training_samples = Column(Integer, nullable=True)
    training_config = Column(JSONB, nullable=True)  # Hyperparameters, feature config
    training_duration_seconds = Column(Float, nullable=True)
    trained_at = Column(DateTime(timezone=True), nullable=True)

    # Performance metrics (on validation set)
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    confusion_matrix = Column(JSONB, nullable=True)
    classification_report = Column(JSONB, nullable=True)

    # Evaluation on test set
    test_accuracy = Column(Float, nullable=True)
    test_f1_score = Column(Float, nullable=True)
    evaluation_results = Column(JSONB, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)

    # Deployment status
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deployment_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('model_name', 'version', name='uq_model_name_version'),
        Index('idx_active_model', 'model_name', 'is_active'),
    )


class MLPredictionLog(Base):
    """Log of ML predictions for monitoring and retraining"""
    __tablename__ = "ml_prediction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_version_id = Column(Integer, ForeignKey("ml_model_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_id = Column(Integer, ForeignKey("chunk_analysis_results.id", ondelete="CASCADE"), nullable=True, index=True)

    input_text = Column(Text, nullable=False)
    input_hash = Column(String(64), nullable=False, index=True)  # For dedup
    prediction = Column(String(50), nullable=False)  # 'huntable', 'not_huntable'
    confidence = Column(Float, nullable=False)
    prediction_probabilities = Column(JSONB, nullable=True)  # All class probabilities

    # Inference metrics
    inference_time_ms = Column(Float, nullable=True)
    feature_importance = Column(JSONB, nullable=True)  # Top features if available

    # Feedback (for active learning)
    feedback_correct = Column(Boolean, nullable=True)
    feedback_label = Column(String(50), nullable=True)
    feedback_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_prediction_feedback', 'feedback_correct', 'created_at'),
    )
