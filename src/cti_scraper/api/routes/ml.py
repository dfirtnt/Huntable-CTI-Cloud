"""ML API Routes - Annotation, Classification, and Model Management"""
import hashlib
import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.base import get_async_session
from ...db.models import (
    Article,
    ArticleAnnotation,
    ChunkAnalysisResult,
    ChunkClassificationFeedback,
    MLModelVersion,
    MLPredictionLog,
)


from ...services.content_chunker import ContentChunker
from ...services.hunt_scorer import HuntScorer
from ...services.ml_classifier import ContentClassifier, get_classifier


# Dependency for FastAPI
async def get_db_session():
    """Dependency for getting async database session"""
    async with get_async_session() as session:
        yield session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ML"])


# ============== Pydantic Models ==============

class AnnotationCreate(BaseModel):
    """Request to create an annotation"""
    article_id: int
    selected_text: str = Field(..., min_length=10)
    annotation_type: str = Field(..., pattern="^(huntable|not_huntable)$")
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None


class AnnotationResponse(BaseModel):
    """Annotation response"""
    id: int
    article_id: int
    selected_text: str
    annotation_type: str
    confidence_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkResponse(BaseModel):
    """Chunk response for annotation interface"""
    index: int
    text: str
    start_position: int
    end_position: int
    word_count: int
    contains_code: bool
    contains_command: bool
    contains_ioc: bool
    hunt_score: Optional[float] = None
    ml_prediction: Optional[str] = None
    ml_confidence: Optional[float] = None


class ClassificationRequest(BaseModel):
    """Request to classify text"""
    text: str = Field(..., min_length=10)
    title: Optional[str] = None


class ClassificationResponse(BaseModel):
    """Classification response"""
    prediction: str
    confidence: float
    probabilities: dict
    model_version: str
    inference_time_ms: float
    hunt_score: Optional[float] = None
    features_used: Optional[List[str]] = None


class FeedbackCreate(BaseModel):
    """Feedback on ML prediction"""
    chunk_id: Optional[int] = None
    article_id: Optional[int] = None
    chunk_text: str
    model_classification: str
    model_confidence: float
    is_correct: bool
    user_classification: Optional[str] = None
    comment: Optional[str] = None


class ModelVersionResponse(BaseModel):
    """Model version info"""
    id: int
    model_name: str
    version: str
    model_type: str
    is_active: bool
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    training_samples: Optional[int] = None
    trained_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnnotationStatsResponse(BaseModel):
    """Annotation statistics"""
    total_annotations: int
    huntable_count: int
    not_huntable_count: int
    used_for_training: int
    pending_training: int
    articles_with_annotations: int


# ============== Annotation Endpoints ==============

@router.post("/annotations", response_model=AnnotationResponse)
async def create_annotation(
    annotation: AnnotationCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new annotation for ML training."""
    # Verify article exists
    article = await session.get(Article, annotation.article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Calculate hunt score for the selected text
    score_result = HuntScorer.score_article("", annotation.selected_text, "")
    confidence_score = score_result["threat_hunting_score"] / 100.0

    # Create annotation
    db_annotation = ArticleAnnotation(
        article_id=annotation.article_id,
        selected_text=annotation.selected_text,
        annotation_type=annotation.annotation_type,
        start_position=annotation.start_position,
        end_position=annotation.end_position,
        context_before=annotation.context_before,
        context_after=annotation.context_after,
        confidence_score=confidence_score,
        used_for_training=False
    )

    session.add(db_annotation)
    await session.commit()
    await session.refresh(db_annotation)

    logger.info(f"Created annotation {db_annotation.id} for article {annotation.article_id}")
    return db_annotation


@router.get("/annotations", response_model=List[AnnotationResponse])
async def list_annotations(
    article_id: Optional[int] = None,
    annotation_type: Optional[str] = None,
    used_for_training: Optional[bool] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session)
):
    """List annotations with optional filters."""
    query = select(ArticleAnnotation)

    if article_id:
        query = query.where(ArticleAnnotation.article_id == article_id)
    if annotation_type:
        query = query.where(ArticleAnnotation.annotation_type == annotation_type)
    if used_for_training is not None:
        query = query.where(ArticleAnnotation.used_for_training == used_for_training)

    query = query.order_by(ArticleAnnotation.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/annotations/stats", response_model=AnnotationStatsResponse)
async def get_annotation_stats(session: AsyncSession = Depends(get_db_session)):
    """Get annotation statistics."""
    # Total counts
    total_query = select(func.count(ArticleAnnotation.id))
    total = (await session.execute(total_query)).scalar() or 0

    # By type
    huntable_query = select(func.count(ArticleAnnotation.id)).where(
        ArticleAnnotation.annotation_type == "huntable"
    )
    huntable = (await session.execute(huntable_query)).scalar() or 0

    not_huntable_query = select(func.count(ArticleAnnotation.id)).where(
        ArticleAnnotation.annotation_type == "not_huntable"
    )
    not_huntable = (await session.execute(not_huntable_query)).scalar() or 0

    # Training status
    used_query = select(func.count(ArticleAnnotation.id)).where(
        ArticleAnnotation.used_for_training == True
    )
    used = (await session.execute(used_query)).scalar() or 0

    # Unique articles
    articles_query = select(func.count(func.distinct(ArticleAnnotation.article_id)))
    articles = (await session.execute(articles_query)).scalar() or 0

    return AnnotationStatsResponse(
        total_annotations=total,
        huntable_count=huntable,
        not_huntable_count=not_huntable,
        used_for_training=used,
        pending_training=total - used,
        articles_with_annotations=articles
    )


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Delete an annotation."""
    annotation = await session.get(ArticleAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    await session.delete(annotation)
    await session.commit()

    return {"status": "deleted", "id": annotation_id}


# ============== Chunking Endpoints ==============

@router.get("/articles/{article_id}/chunks", response_model=List[ChunkResponse])
async def get_article_chunks(
    article_id: int,
    include_predictions: bool = True,
    session: AsyncSession = Depends(get_db_session)
):
    """Get article content split into chunks for annotation."""
    article = await session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Chunk the content
    chunker = ContentChunker()
    chunks = chunker.chunk_article(article.content, article.title)

    # Get existing predictions if requested
    existing_predictions = {}
    if include_predictions:
        query = select(ChunkAnalysisResult).where(
            ChunkAnalysisResult.article_id == article_id
        )
        result = await session.execute(query)
        for pred in result.scalars().all():
            existing_predictions[pred.chunk_index] = pred

    # Build response
    response = []
    for chunk in chunks:
        # Calculate hunt score
        score_result = HuntScorer.score_article("", chunk.text, "")

        chunk_response = ChunkResponse(
            index=chunk.index,
            text=chunk.text,
            start_position=chunk.start_position,
            end_position=chunk.end_position,
            word_count=chunk.word_count,
            contains_code=chunk.contains_code,
            contains_command=chunk.contains_command,
            contains_ioc=chunk.contains_ioc,
            hunt_score=score_result["threat_hunting_score"]
        )

        # Add existing prediction if available
        if chunk.index in existing_predictions:
            pred = existing_predictions[chunk.index]
            chunk_response.ml_prediction = pred.ml_prediction
            chunk_response.ml_confidence = pred.ml_confidence

        response.append(chunk_response)

    return response


# ============== Classification Endpoints ==============

@router.post("/classify", response_model=ClassificationResponse)
async def classify_text(request: ClassificationRequest):
    """Classify text as huntable or not huntable."""
    # Get classifier (will use fallback if no model available)
    classifier = get_classifier()

    # Classify
    result = classifier.classify(request.text, request.title or "")

    # Also get hunt score
    score_result = HuntScorer.score_article(
        request.title or "",
        request.text,
        ""
    )

    return ClassificationResponse(
        prediction=result.prediction,
        confidence=result.confidence,
        probabilities=result.probabilities,
        model_version=result.model_version,
        inference_time_ms=result.inference_time_ms,
        hunt_score=score_result["threat_hunting_score"],
        features_used=result.features_used
    )


@router.post("/classify/article/{article_id}")
async def classify_article(
    article_id: int,
    save_results: bool = True,
    session: AsyncSession = Depends(get_db_session)
):
    """Classify all chunks in an article."""
    article = await session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Chunk the content
    chunker = ContentChunker()
    chunks = chunker.chunk_article(article.content, article.title)

    if not chunks:
        return {"article_id": article_id, "chunks_processed": 0, "results": []}

    # Get classifier
    classifier = get_classifier()

    # Classify all chunks
    texts = [chunk.text for chunk in chunks]
    results = classifier.classify_batch(texts)

    # Build response and optionally save
    response_results = []
    for chunk, result in zip(chunks, results):
        # Calculate hunt score
        score_result = HuntScorer.score_article("", chunk.text, "")

        chunk_result = {
            "chunk_index": chunk.index,
            "prediction": result.prediction,
            "confidence": result.confidence,
            "hunt_score": score_result["threat_hunting_score"],
            "passed_filter": result.prediction == "huntable" and result.confidence >= 0.5
        }
        response_results.append(chunk_result)

        # Save to database if requested
        if save_results:
            db_chunk = ChunkAnalysisResult(
                article_id=article_id,
                chunk_index=chunk.index,
                chunk_text=chunk.text,
                ml_prediction=result.prediction,
                ml_confidence=result.confidence,
                hunt_score=score_result["threat_hunting_score"],
                passed_filter=chunk_result["passed_filter"]
            )
            session.add(db_chunk)

    if save_results:
        await session.commit()

    return {
        "article_id": article_id,
        "chunks_processed": len(chunks),
        "model_version": results[0].model_version if results else None,
        "results": response_results
    }


# ============== Feedback Endpoints ==============

@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """Submit feedback on ML prediction for active learning."""
    db_feedback = ChunkClassificationFeedback(
        article_id=feedback.article_id,
        chunk_id=feedback.chunk_id,
        chunk_text=feedback.chunk_text,
        model_classification=feedback.model_classification,
        model_confidence=feedback.model_confidence,
        is_correct=feedback.is_correct,
        user_classification=feedback.user_classification,
        comment=feedback.comment
    )

    session.add(db_feedback)
    await session.commit()
    await session.refresh(db_feedback)

    return {"status": "submitted", "feedback_id": db_feedback.id}


@router.get("/feedback/stats")
async def get_feedback_stats(session: AsyncSession = Depends(get_db_session)):
    """Get feedback statistics for model monitoring."""
    # Total feedback
    total_query = select(func.count(ChunkClassificationFeedback.id))
    total = (await session.execute(total_query)).scalar() or 0

    # Correct predictions
    correct_query = select(func.count(ChunkClassificationFeedback.id)).where(
        ChunkClassificationFeedback.is_correct == True
    )
    correct = (await session.execute(correct_query)).scalar() or 0

    # Incorrect predictions
    incorrect = total - correct

    accuracy = correct / total if total > 0 else 0.0

    return {
        "total_feedback": total,
        "correct_predictions": correct,
        "incorrect_predictions": incorrect,
        "accuracy": accuracy
    }


# ============== Model Management Endpoints ==============

@router.get("/models", response_model=List[ModelVersionResponse])
async def list_models(
    model_name: Optional[str] = None,
    active_only: bool = False,
    session: AsyncSession = Depends(get_db_session)
):
    """List ML model versions."""
    query = select(MLModelVersion)

    if model_name:
        query = query.where(MLModelVersion.model_name == model_name)
    if active_only:
        query = query.where(MLModelVersion.is_active == True)

    query = query.order_by(MLModelVersion.created_at.desc())

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/models/active/{model_name}", response_model=ModelVersionResponse)
async def get_active_model(
    model_name: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Get the active model version for a model name."""
    query = select(MLModelVersion).where(
        MLModelVersion.model_name == model_name,
        MLModelVersion.is_active == True
    )

    result = await session.execute(query)
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail=f"No active model found for {model_name}")

    return model


@router.post("/models/{model_id}/activate")
async def activate_model(
    model_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """Activate a model version (deactivates other versions of same model)."""
    model = await session.get(MLModelVersion, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Deactivate other versions of same model
    deactivate_query = (
        update(MLModelVersion)
        .where(MLModelVersion.model_name == model.model_name)
        .where(MLModelVersion.id != model_id)
        .values(is_active=False)
    )
    await session.execute(deactivate_query)

    # Activate this version
    model.is_active = True
    model.deployed_at = datetime.utcnow()

    await session.commit()

    return {"status": "activated", "model_id": model_id, "model_name": model.model_name}


# ============== Training Endpoints ==============

class TrainingRequest(BaseModel):
    """Request to trigger ML training"""
    model_type: str = Field(default="random_forest", pattern="^(random_forest|svm)$")
    upload_s3: bool = True
    include_feedback: bool = True


@router.post("/train")
async def trigger_training(
    request: TrainingRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Trigger ML model training via Lambda invocation.

    This endpoint invokes the ML trainer Lambda function asynchronously.
    Training results will be logged to CloudWatch and model version recorded in database.
    """
    import boto3
    import os

    # Check if we have enough annotations
    stats_query = select(func.count(ArticleAnnotation.id)).where(
        ArticleAnnotation.used_for_training == False
    )
    annotation_count = (await session.execute(stats_query)).scalar() or 0

    if annotation_count < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient training data. Found {annotation_count} annotations, need at least 10."
        )

    # Invoke training Lambda
    lambda_client = boto3.client("lambda")
    function_name = os.environ.get("ML_TRAINER_FUNCTION_NAME")

    if not function_name:
        raise HTTPException(
            status_code=500,
            detail="ML_TRAINER_FUNCTION_NAME not configured"
        )

    try:
        # Invoke asynchronously (Event invocation type)
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",  # Async
            Payload=json.dumps({
                "model_type": request.model_type,
                "upload_s3": request.upload_s3,
                "include_feedback": request.include_feedback
            })
        )

        request_id = response.get("ResponseMetadata", {}).get("RequestId")

        logger.info(f"Training Lambda invoked: {request_id}")

        return {
            "success": True,
            "request_id": request_id,
            "message": "Training started. Check CloudWatch logs for progress.",
            "log_group": f"/aws/lambda/{function_name}",
            "annotation_count": annotation_count
        }

    except Exception as e:
        logger.error(f"Failed to invoke training Lambda: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Backfill Endpoints ==============

class BackfillRequest(BaseModel):
    """Request to backfill ML classification on existing articles"""
    min_hunt_score: float = Field(default=50.0, ge=0.0, le=100.0)
    limit: Optional[int] = Field(default=100, le=1000)
    force: bool = False  # Reprocess articles that already have classifications


@router.post("/backfill")
async def backfill_chunk_analysis(
    request: BackfillRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Run ML chunk classification on existing articles with hunt_score > threshold.

    This endpoint classifies articles that meet the hunt score threshold but don't
    have ML classifications yet. Useful for processing existing articles after
    training a new model.
    """
    # Get articles that need classification
    query = select(Article).where(
        Article.threat_hunting_score >= request.min_hunt_score,
        Article.content.isnot(None)
    ).order_by(Article.threat_hunting_score.desc())

    if request.limit:
        query = query.limit(request.limit)

    result = await session.execute(query)
    articles = result.scalars().all()

    if not articles:
        return {
            "success": True,
            "message": "No articles found matching criteria",
            "processed": 0
        }

    # Load ML classifier
    classifier = get_classifier()
    chunker = ContentChunker()

    processed = 0
    skipped = 0

    for article in articles:
        # Check if already classified (unless force=True)
        if not request.force:
            existing_query = select(ChunkAnalysisResult).where(
                ChunkAnalysisResult.article_id == article.id
            ).limit(1)
            existing_result = await session.execute(existing_query)

            if existing_result.scalar_one_or_none():
                skipped += 1
                continue
        else:
            # Delete existing classifications if force=True
            delete_query = select(ChunkAnalysisResult).where(
                ChunkAnalysisResult.article_id == article.id
            )
            delete_result = await session.execute(delete_query)
            for existing_chunk in delete_result.scalars().all():
                await session.delete(existing_chunk)

        # Chunk and classify
        chunks = chunker.chunk_article(article.content, article.title)

        if not chunks:
            continue

        # Batch classify all chunks
        texts = [chunk.text for chunk in chunks]
        results = classifier.classify_batch(texts)

        # Save results
        for chunk, result in zip(chunks, results):
            score_result = HuntScorer.score_article("", chunk.text, "")

            chunk_result = ChunkAnalysisResult(
                article_id=article.id,
                chunk_index=chunk.index,
                chunk_text=chunk.text,
                ml_prediction=result.prediction,
                ml_confidence=result.confidence,
                model_version=result.model_version,
                hunt_score=score_result["threat_hunting_score"],
                passed_filter=(result.prediction == "huntable" and result.confidence > 0.7)
            )
            session.add(chunk_result)

        processed += 1

    await session.commit()

    logger.info(f"Backfill complete: processed {processed}, skipped {skipped}")

    return {
        "success": True,
        "processed": processed,
        "skipped": skipped,
        "total_articles": len(articles),
        "model_version": results[0].model_version if processed > 0 and results else None
    }
