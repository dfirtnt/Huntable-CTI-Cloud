"""ML Content Classifier Service

Lightweight ML classifier designed to run in AWS Lambda.
Uses scikit-learn models loaded from S3 for content classification.

Features:
- Lazy model loading (only loads when first prediction is made)
- Model caching in Lambda /tmp directory
- TF-IDF + SVM/RandomForest classification
- Fallback to rule-based scoring if model unavailable
"""
import hashlib
import json
import logging
import os
import pickle
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from .hunt_scorer import HuntScorer

logger = logging.getLogger(__name__)

# Lambda /tmp cache directory
LAMBDA_TMP = "/tmp"
MODEL_CACHE_DIR = os.path.join(LAMBDA_TMP, "ml_models")


@dataclass
class ClassificationResult:
    """Result of ML classification"""
    prediction: str  # 'huntable' or 'not_huntable'
    confidence: float  # 0.0 to 1.0
    probabilities: Dict[str, float]  # {'huntable': 0.8, 'not_huntable': 0.2}
    model_version: str
    inference_time_ms: float
    features_used: Optional[List[str]] = None  # Top features if available


class ContentClassifier:
    """ML-based content classifier for threat hunting articles.

    This classifier is designed to run efficiently in AWS Lambda:
    - Models are loaded from S3 on first use
    - Models are cached in /tmp to avoid repeated downloads
    - Falls back to rule-based HuntScorer if model unavailable
    """

    def __init__(
        self,
        s3_bucket: Optional[str] = None,
        model_s3_key: Optional[str] = None,
        vectorizer_s3_key: Optional[str] = None,
        model_version: str = "unknown",
        hunt_score_threshold: float = 50.0,
        use_fallback: bool = True
    ):
        """
        Initialize the classifier.

        Args:
            s3_bucket: S3 bucket containing model files
            model_s3_key: S3 key for the model pickle file
            vectorizer_s3_key: S3 key for the TF-IDF vectorizer pickle file
            model_version: Version string for tracking
            hunt_score_threshold: Threshold for fallback rule-based classification
            use_fallback: Whether to use HuntScorer as fallback
        """
        self.s3_bucket = s3_bucket or os.environ.get("ML_MODEL_BUCKET")
        self.model_s3_key = model_s3_key or os.environ.get("ML_MODEL_KEY", "models/content_filter/model.pkl")
        self.vectorizer_s3_key = vectorizer_s3_key or os.environ.get("ML_VECTORIZER_KEY", "models/content_filter/vectorizer.pkl")
        self.model_version = model_version
        self.hunt_score_threshold = hunt_score_threshold
        self.use_fallback = use_fallback

        # Lazy-loaded model components
        self._model = None
        self._vectorizer = None
        self._model_loaded = False
        self._load_attempted = False

        # S3 client (lazy initialized)
        self._s3_client = None

        # Ensure cache directory exists
        os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

    @property
    def s3_client(self):
        """Lazy S3 client initialization."""
        if self._s3_client is None:
            self._s3_client = boto3.client("s3")
        return self._s3_client

    def _get_cache_path(self, s3_key: str) -> str:
        """Get local cache path for an S3 key."""
        # Use hash of key to avoid path issues
        key_hash = hashlib.md5(s3_key.encode()).hexdigest()[:12]
        filename = os.path.basename(s3_key)
        return os.path.join(MODEL_CACHE_DIR, f"{key_hash}_{filename}")

    def _download_from_s3(self, s3_key: str, local_path: str) -> bool:
        """Download file from S3 to local path."""
        if not self.s3_bucket:
            logger.warning("No S3 bucket configured for model download")
            return False

        try:
            logger.info(f"Downloading {s3_key} from s3://{self.s3_bucket}")
            self.s3_client.download_file(self.s3_bucket, s3_key, local_path)
            logger.info(f"Downloaded to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to download {s3_key}: {e}")
            return False

    def _load_model(self) -> bool:
        """Load model and vectorizer from S3/cache."""
        if self._load_attempted:
            return self._model_loaded

        self._load_attempted = True

        # Check cache first
        model_cache_path = self._get_cache_path(self.model_s3_key)
        vectorizer_cache_path = self._get_cache_path(self.vectorizer_s3_key)

        # Download if not cached
        if not os.path.exists(model_cache_path):
            if not self._download_from_s3(self.model_s3_key, model_cache_path):
                return False

        if not os.path.exists(vectorizer_cache_path):
            if not self._download_from_s3(self.vectorizer_s3_key, vectorizer_cache_path):
                return False

        # Load from cache
        try:
            with open(model_cache_path, "rb") as f:
                self._model = pickle.load(f)
            logger.info(f"Loaded model from {model_cache_path}")

            with open(vectorizer_cache_path, "rb") as f:
                self._vectorizer = pickle.load(f)
            logger.info(f"Loaded vectorizer from {vectorizer_cache_path}")

            self._model_loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def classify(self, text: str, title: str = "") -> ClassificationResult:
        """
        Classify text as huntable or not huntable.

        Args:
            text: Content to classify
            title: Optional title (prepended to text)

        Returns:
            ClassificationResult with prediction and confidence
        """
        start_time = time.time()

        # Combine title and text
        full_text = f"{title}\n\n{text}" if title else text

        # Try ML model first
        if self._load_model():
            result = self._ml_classify(full_text)
        elif self.use_fallback:
            result = self._fallback_classify(title, text)
        else:
            # No model and no fallback - return uncertain
            result = ClassificationResult(
                prediction="unknown",
                confidence=0.0,
                probabilities={"huntable": 0.5, "not_huntable": 0.5},
                model_version="none",
                inference_time_ms=0.0
            )

        # Update inference time
        result.inference_time_ms = (time.time() - start_time) * 1000

        return result

    def _ml_classify(self, text: str) -> ClassificationResult:
        """Classify using loaded ML model."""
        try:
            # Vectorize text
            text_vector = self._vectorizer.transform([text])

            # Get prediction
            prediction = self._model.predict(text_vector)[0]

            # Get probabilities if available
            if hasattr(self._model, "predict_proba"):
                probas = self._model.predict_proba(text_vector)[0]
                classes = self._model.classes_
                probabilities = {str(c): float(p) for c, p in zip(classes, probas)}
                confidence = max(probas)
            else:
                # For models without predict_proba (like some SVMs)
                confidence = 0.8  # Default confidence
                probabilities = {
                    "huntable": 0.8 if prediction == "huntable" else 0.2,
                    "not_huntable": 0.2 if prediction == "huntable" else 0.8
                }

            # Get feature importance if available
            features_used = None
            if hasattr(self._model, "feature_importances_") and hasattr(self._vectorizer, "get_feature_names_out"):
                feature_names = self._vectorizer.get_feature_names_out()
                importances = self._model.feature_importances_
                # Get top 10 features
                top_indices = importances.argsort()[-10:][::-1]
                features_used = [feature_names[i] for i in top_indices]

            return ClassificationResult(
                prediction=str(prediction),
                confidence=float(confidence),
                probabilities=probabilities,
                model_version=self.model_version,
                inference_time_ms=0.0,  # Updated by caller
                features_used=features_used
            )

        except Exception as e:
            logger.error(f"ML classification failed: {e}")
            if self.use_fallback:
                return self._fallback_classify("", text)
            raise

    def _fallback_classify(self, title: str, text: str) -> ClassificationResult:
        """Fallback to rule-based HuntScorer classification."""
        logger.info("Using fallback HuntScorer for classification")

        # Use HuntScorer
        score_result = HuntScorer.score_article(title, "", text)
        hunt_score = score_result["threat_hunting_score"]

        # Convert score to classification
        if hunt_score >= self.hunt_score_threshold:
            prediction = "huntable"
            # Scale confidence based on how much above threshold
            confidence = min(0.95, 0.5 + (hunt_score - self.hunt_score_threshold) / 100)
        else:
            prediction = "not_huntable"
            # Scale confidence based on how much below threshold
            confidence = min(0.95, 0.5 + (self.hunt_score_threshold - hunt_score) / 100)

        return ClassificationResult(
            prediction=prediction,
            confidence=confidence,
            probabilities={
                "huntable": confidence if prediction == "huntable" else 1 - confidence,
                "not_huntable": 1 - confidence if prediction == "huntable" else confidence
            },
            model_version="hunt_scorer_fallback",
            inference_time_ms=0.0,
            features_used=score_result.get("perfect_keyword_matches", [])[:10]
        )

    def classify_batch(self, texts: List[str], titles: Optional[List[str]] = None) -> List[ClassificationResult]:
        """
        Classify multiple texts efficiently.

        Args:
            texts: List of content to classify
            titles: Optional list of titles (same length as texts)

        Returns:
            List of ClassificationResult objects
        """
        if titles is None:
            titles = [""] * len(texts)

        if len(titles) != len(texts):
            raise ValueError("titles must have same length as texts")

        start_time = time.time()
        results = []

        # Try batch ML classification
        if self._load_model():
            try:
                full_texts = [
                    f"{title}\n\n{text}" if title else text
                    for title, text in zip(titles, texts)
                ]

                # Vectorize all texts
                text_vectors = self._vectorizer.transform(full_texts)

                # Get predictions
                predictions = self._model.predict(text_vectors)

                # Get probabilities if available
                if hasattr(self._model, "predict_proba"):
                    all_probas = self._model.predict_proba(text_vectors)
                    classes = self._model.classes_

                    for i, (pred, probas) in enumerate(zip(predictions, all_probas)):
                        probabilities = {str(c): float(p) for c, p in zip(classes, probas)}
                        results.append(ClassificationResult(
                            prediction=str(pred),
                            confidence=float(max(probas)),
                            probabilities=probabilities,
                            model_version=self.model_version,
                            inference_time_ms=0.0
                        ))
                else:
                    for pred in predictions:
                        results.append(ClassificationResult(
                            prediction=str(pred),
                            confidence=0.8,
                            probabilities={
                                "huntable": 0.8 if pred == "huntable" else 0.2,
                                "not_huntable": 0.2 if pred == "huntable" else 0.8
                            },
                            model_version=self.model_version,
                            inference_time_ms=0.0
                        ))

                # Update inference time (average per item)
                total_time_ms = (time.time() - start_time) * 1000
                for result in results:
                    result.inference_time_ms = total_time_ms / len(results)

                return results

            except Exception as e:
                logger.error(f"Batch ML classification failed: {e}")

        # Fallback to individual classification
        for title, text in zip(titles, texts):
            results.append(self.classify(text, title))

        return results


def get_classifier(
    s3_bucket: Optional[str] = None,
    model_name: str = "content_filter"
) -> ContentClassifier:
    """
    Factory function to get a configured classifier.

    Args:
        s3_bucket: S3 bucket (defaults to env var)
        model_name: Name of the model to load

    Returns:
        Configured ContentClassifier instance
    """
    bucket = s3_bucket or os.environ.get("ML_MODEL_BUCKET")
    model_key = f"models/{model_name}/model.pkl"
    vectorizer_key = f"models/{model_name}/vectorizer.pkl"

    return ContentClassifier(
        s3_bucket=bucket,
        model_s3_key=model_key,
        vectorizer_s3_key=vectorizer_key,
        model_version=os.environ.get("ML_MODEL_VERSION", "latest"),
        use_fallback=True
    )
