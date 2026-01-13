"""Lambda handler for ML model training

This Lambda function:
1. Loads annotations from RDS
2. Trains TF-IDF + RandomForest/SVM model
3. Uploads model artifacts to S3
4. Records model version in database
"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add scripts to path for training code reuse
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from train_content_filter import (
    load_training_data_from_db,
    train_model,
    upload_to_s3
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda handler for ML training.

    Event format:
    {
        "model_type": "random_forest",  # or "svm"
        "upload_s3": true,
        "include_feedback": true
    }
    """
    logger.info(f"Starting ML training with event: {json.dumps(event)}")

    # Parse event
    model_type = event.get("model_type", "random_forest")
    upload_s3_flag = event.get("upload_s3", True)
    include_feedback = event.get("include_feedback", True)

    # Get config from environment
    database_url = _get_database_url()
    s3_bucket = os.environ.get("ML_MODEL_BUCKET")
    min_samples = int(os.environ.get("MIN_TRAINING_SAMPLES", "10"))

    try:
        # Load training data
        logger.info("Loading training data from database...")
        texts, labels = load_training_data_from_db(database_url)

        if len(texts) < min_samples:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "success": False,
                    "error": f"Insufficient training data. Found {len(texts)}, need {min_samples}",
                    "samples_found": len(texts),
                    "min_required": min_samples
                })
            }

        # Use /tmp for model output (Lambda ephemeral storage)
        output_dir = "/tmp/models/content_filter"
        os.makedirs(output_dir, exist_ok=True)

        # Train model
        logger.info(f"Training {model_type} model with {len(texts)} samples...")
        metadata = train_model(
            texts=texts,
            labels=labels,
            model_type=model_type,
            output_dir=output_dir
        )

        # Upload to S3
        if upload_s3_flag and s3_bucket:
            logger.info(f"Uploading model to S3 bucket: {s3_bucket}")
            upload_to_s3(output_dir, s3_bucket, "models/content_filter")

            # Also upload versioned copy
            version_prefix = f"models/content_filter/versions/{metadata['version']}"
            upload_to_s3(output_dir, s3_bucket, version_prefix)

        # Record model version in database
        _record_model_version(database_url, metadata)

        logger.info("Training completed successfully")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "model_version": metadata["version"],
                "training_samples": metadata["training_samples"],
                "training_duration_seconds": metadata["training_duration_seconds"],
                "metrics": metadata["metrics"],
                "s3_uploaded": upload_s3_flag and s3_bucket is not None
            })
        }

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }


def _get_database_url():
    """Get database URL from Secrets Manager."""
    import boto3

    secret_id = os.environ.get("DATABASE_SECRET_ID")
    if not secret_id:
        raise ValueError("DATABASE_SECRET_ID not configured")

    secrets_client = boto3.client("secretsmanager")
    response = secrets_client.get_secret_value(SecretId=secret_id)
    secret = json.loads(response["SecretString"])

    # Construct database URL (sync version for training)
    return (
        f"postgresql://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}"
    )


def _record_model_version(database_url, metadata):
    """Record model version in database."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)

    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO ml_model_versions (
                version_number,
                model_name,
                model_type,
                trained_at,
                training_samples,
                training_duration_seconds,
                accuracy,
                precision,
                recall,
                f1_score,
                confusion_matrix,
                model_params,
                model_file_path
            ) VALUES (
                (SELECT COALESCE(MAX(version_number), 0) + 1 FROM ml_model_versions),
                :model_name,
                :model_type,
                :trained_at,
                :training_samples,
                :training_duration_seconds,
                :accuracy,
                :precision,
                :recall,
                :f1_score,
                :confusion_matrix,
                :model_params,
                :model_file_path
            )
        """), {
            "model_name": metadata["model_name"],
            "model_type": metadata["model_type"],
            "trained_at": metadata["trained_at"],
            "training_samples": metadata["training_samples"],
            "training_duration_seconds": metadata["training_duration_seconds"],
            "accuracy": metadata["metrics"]["accuracy"],
            "precision": metadata["metrics"]["precision"],
            "recall": metadata["metrics"]["recall"],
            "f1_score": metadata["metrics"]["f1_score"],
            "confusion_matrix": json.dumps(metadata["metrics"]["confusion_matrix"]),
            "model_params": json.dumps(metadata["best_params"]),
            "model_file_path": f"s3://{os.environ['ML_MODEL_BUCKET']}/models/content_filter/{metadata['version']}/model.pkl"
        })
        conn.commit()

    logger.info("Recorded model version in database")
