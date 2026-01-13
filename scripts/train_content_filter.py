#!/usr/bin/env python3
"""Train Content Filter ML Model

This script trains a content classification model for identifying
threat hunting content vs. non-technical/junk content.

Model Architecture:
- TF-IDF vectorization (character n-grams + word n-grams)
- Random Forest or SVM classifier
- Cross-validation for hyperparameter tuning

Usage:
    # Train from annotated database data
    python scripts/train_content_filter.py --from-db

    # Train from JSON file
    python scripts/train_content_filter.py --from-file training_data.json

    # Train and upload to S3
    python scripts/train_content_filter.py --from-db --upload-s3

    # Evaluate existing model
    python scripts/train_content_filter.py --evaluate-only
"""
import argparse
import hashlib
import json
import logging
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_training_data_from_file(filepath: str) -> Tuple[List[str], List[str]]:
    """
    Load training data from JSON file.

    Expected format:
    [
        {"text": "...", "label": "huntable"},
        {"text": "...", "label": "not_huntable"},
        ...
    ]
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = [item["text"] for item in data]
    labels = [item["label"] for item in data]

    logger.info(f"Loaded {len(texts)} samples from {filepath}")
    return texts, labels


def load_training_data_from_db(database_url: str) -> Tuple[List[str], List[str]]:
    """
    Load training data from database annotations.

    Uses ArticleAnnotation table where users have labeled content.
    """
    from sqlalchemy import create_engine, text

    # Convert async URL to sync
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)

    query = text("""
        SELECT
            aa.selected_text as text,
            aa.annotation_type as label
        FROM article_annotations aa
        WHERE aa.annotation_type IN ('huntable', 'not_huntable')
        AND aa.used_for_training = false
        AND length(aa.selected_text) > 50
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

    if not rows:
        logger.warning("No training data found in database")
        return [], []

    texts = [row[0] for row in rows]
    labels = [row[1] for row in rows]

    logger.info(f"Loaded {len(texts)} samples from database")
    return texts, labels


def create_synthetic_training_data() -> Tuple[List[str], List[str]]:
    """
    Create synthetic training data for bootstrapping.

    Uses HuntScorer to generate labels for sample content.
    This is useful for initial model training before user annotations exist.
    """
    from cti_scraper.services.hunt_scorer import HuntScorer

    # Sample threat hunting content (huntable)
    huntable_samples = [
        "The attacker used rundll32.exe to execute the malicious DLL via the command: rundll32.exe C:\\Windows\\Temp\\payload.dll,DllMain",
        "PowerShell was observed downloading the second stage payload using Invoke-WebRequest and executing it with IEX (Invoke-Expression)",
        "Lateral movement was achieved through PsExec.exe targeting admin$ shares on remote systems within the domain",
        "The threat actor leveraged wmic.exe to query installed antivirus products: wmic /node:target AntiVirusProduct get displayName",
        "Persistence was established via a scheduled task created with schtasks.exe /create /tn 'UpdateCheck' /tr 'powershell.exe -enc ...'",
        "LSASS memory was dumped using comsvcs.dll: rundll32.exe C:\\Windows\\System32\\comsvcs.dll, MiniDump",
        "The Cobalt Strike beacon was configured to communicate via HTTPS on port 443 with a User-Agent string mimicking Chrome",
        "Registry key HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run was modified to establish persistence",
        "The APT group used certutil.exe -decode to decode the base64 encoded payload stored in the alternate data stream",
        "Network discovery commands were executed: net view /domain, nltest /dclist:, ping -n 1 dc01.corp.local",
    ]

    # Sample non-technical content (not_huntable)
    not_huntable_samples = [
        "Welcome to our quarterly security newsletter! Click here to learn more about our latest product updates and features.",
        "What is ransomware? Ransomware is a type of malicious software that encrypts your files and demands payment.",
        "Top 10 cybersecurity best practices for small businesses: 1. Use strong passwords 2. Enable two-factor authentication",
        "Join our upcoming webinar on cloud security fundamentals. Register now to secure your spot!",
        "The global cybersecurity market is expected to reach $300 billion by 2025, according to recent industry reports.",
        "Our team of experts provides 24/7 monitoring and incident response services. Contact us for a free consultation.",
        "Understanding the basics of network security: A beginner's guide to firewalls, VPNs, and intrusion detection systems.",
        "Download our free whitepaper on the state of cybersecurity in 2024. Learn about emerging trends and challenges.",
        "Security awareness training is essential for all employees. Our platform offers interactive courses and phishing simulations.",
        "Meet our leadership team: John Smith, CEO with 20 years of experience in cybersecurity and risk management.",
    ]

    # Score and verify samples
    verified_huntable = []
    verified_not_huntable = []

    for sample in huntable_samples:
        score = HuntScorer.score_article("", sample, "")["threat_hunting_score"]
        if score >= 40:  # Should score high
            verified_huntable.append(sample)
        else:
            logger.warning(f"Huntable sample scored low ({score}): {sample[:50]}...")

    for sample in not_huntable_samples:
        score = HuntScorer.score_article("", sample, "")["threat_hunting_score"]
        if score < 40:  # Should score low
            verified_not_huntable.append(sample)
        else:
            logger.warning(f"Not huntable sample scored high ({score}): {sample[:50]}...")

    texts = verified_huntable + verified_not_huntable
    labels = ["huntable"] * len(verified_huntable) + ["not_huntable"] * len(verified_not_huntable)

    logger.info(f"Created {len(texts)} synthetic training samples")
    return texts, labels


def train_model(
    texts: List[str],
    labels: List[str],
    model_type: str = "random_forest",
    output_dir: str = "models/content_filter"
) -> Dict[str, Any]:
    """
    Train the content classification model.

    Args:
        texts: Training texts
        labels: Training labels ('huntable' or 'not_huntable')
        model_type: 'random_forest' or 'svm'
        output_dir: Directory to save model files

    Returns:
        Dictionary with model metadata and metrics
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )
    from sklearn.model_selection import GridSearchCV, train_test_split
    from sklearn.svm import SVC

    logger.info(f"Training {model_type} model with {len(texts)} samples")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    logger.info(f"Train set: {len(X_train)}, Test set: {len(X_test)}")

    # Create TF-IDF vectorizer with character and word n-grams
    vectorizer = TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 3),  # Word unigrams, bigrams, trigrams
        analyzer="word",
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
        strip_accents="unicode",
        lowercase=True
    )

    # Fit vectorizer on training data
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    logger.info(f"Vocabulary size: {len(vectorizer.vocabulary_)}")

    # Train model with hyperparameter tuning
    start_time = datetime.now()

    if model_type == "random_forest":
        param_grid = {
            "n_estimators": [100, 200],
            "max_depth": [10, 20, None],
            "min_samples_split": [2, 5],
            "class_weight": ["balanced"]
        }
        base_model = RandomForestClassifier(random_state=42, n_jobs=-1)

    elif model_type == "svm":
        param_grid = {
            "C": [0.1, 1.0, 10.0],
            "kernel": ["linear", "rbf"],
            "class_weight": ["balanced"]
        }
        base_model = SVC(random_state=42, probability=True)

    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Grid search with cross-validation
    grid_search = GridSearchCV(
        base_model,
        param_grid,
        cv=5,
        scoring="f1_weighted",
        n_jobs=-1,
        verbose=1
    )

    grid_search.fit(X_train_vec, y_train)
    model = grid_search.best_estimator_

    training_duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Training completed in {training_duration:.1f}s")
    logger.info(f"Best parameters: {grid_search.best_params_}")

    # Evaluate on test set
    y_pred = model.predict(X_test_vec)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, pos_label="huntable")
    recall = recall_score(y_test, y_pred, pos_label="huntable")
    f1 = f1_score(y_test, y_pred, pos_label="huntable")
    conf_matrix = confusion_matrix(y_test, y_pred).tolist()
    class_report = classification_report(y_test, y_pred, output_dict=True)

    logger.info(f"Test Accuracy: {accuracy:.4f}")
    logger.info(f"Test F1 Score: {f1:.4f}")
    logger.info(f"Test Precision: {precision:.4f}")
    logger.info(f"Test Recall: {recall:.4f}")

    # Save model and vectorizer
    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, "model.pkl")
    vectorizer_path = os.path.join(output_dir, "vectorizer.pkl")

    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    logger.info(f"Saved model to {model_path}")

    with open(vectorizer_path, "wb") as f:
        pickle.dump(vectorizer, f)
    logger.info(f"Saved vectorizer to {vectorizer_path}")

    # Calculate model hash
    with open(model_path, "rb") as f:
        model_hash = hashlib.sha256(f.read()).hexdigest()

    # Build metadata
    metadata = {
        "model_name": "content_filter",
        "model_type": model_type,
        "version": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "training_samples": len(texts),
        "training_duration_seconds": training_duration,
        "best_params": grid_search.best_params_,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "model_hash": model_hash,
        "metrics": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "confusion_matrix": conf_matrix,
            "classification_report": class_report
        },
        "trained_at": datetime.now().isoformat()
    }

    # Save metadata
    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.info(f"Saved metadata to {metadata_path}")

    return metadata


def upload_to_s3(
    local_dir: str,
    s3_bucket: str,
    s3_prefix: str = "models/content_filter"
) -> None:
    """Upload model files to S3."""
    import boto3

    s3_client = boto3.client("s3")

    for filename in ["model.pkl", "vectorizer.pkl", "metadata.json"]:
        local_path = os.path.join(local_dir, filename)
        if os.path.exists(local_path):
            s3_key = f"{s3_prefix}/{filename}"
            logger.info(f"Uploading {local_path} to s3://{s3_bucket}/{s3_key}")
            s3_client.upload_file(local_path, s3_bucket, s3_key)


def main():
    parser = argparse.ArgumentParser(description="Train content filter ML model")
    parser.add_argument("--from-db", action="store_true", help="Load training data from database")
    parser.add_argument("--from-file", type=str, help="Load training data from JSON file")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic training data")
    parser.add_argument("--model-type", type=str, default="random_forest", choices=["random_forest", "svm"])
    parser.add_argument("--output-dir", type=str, default="models/content_filter")
    parser.add_argument("--upload-s3", action="store_true", help="Upload model to S3")
    parser.add_argument("--s3-bucket", type=str, help="S3 bucket for upload")
    parser.add_argument("--evaluate-only", action="store_true", help="Only evaluate existing model")

    args = parser.parse_args()

    # Load training data
    if args.from_file:
        texts, labels = load_training_data_from_file(args.from_file)
    elif args.from_db:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            sys.exit(1)
        texts, labels = load_training_data_from_db(database_url)
    elif args.synthetic:
        texts, labels = create_synthetic_training_data()
    else:
        logger.error("Must specify --from-db, --from-file, or --synthetic")
        sys.exit(1)

    if not texts:
        logger.error("No training data available")
        sys.exit(1)

    # Check class balance
    from collections import Counter
    label_counts = Counter(labels)
    logger.info(f"Label distribution: {dict(label_counts)}")

    if len(label_counts) < 2:
        logger.error("Need at least 2 classes for training")
        sys.exit(1)

    # Train model
    metadata = train_model(
        texts=texts,
        labels=labels,
        model_type=args.model_type,
        output_dir=args.output_dir
    )

    # Upload to S3 if requested
    if args.upload_s3:
        s3_bucket = args.s3_bucket or os.environ.get("ML_MODEL_BUCKET")
        if not s3_bucket:
            logger.error("Must specify --s3-bucket or ML_MODEL_BUCKET env var")
            sys.exit(1)
        upload_to_s3(args.output_dir, s3_bucket)

    logger.info("Training complete!")
    print(json.dumps(metadata, indent=2, default=str))


if __name__ == "__main__":
    main()
