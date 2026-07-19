"""
NETRA Baseline Model — TF-IDF + Logistic Regression for Scam Classification

Classical ML baseline to benchmark against NETRA's LLM-based detection.
This proves the LLM approach adds measurable value over simple ML.

Pipeline:
1. TF-IDF vectorizer (unigrams + bigrams, max 5000 features)
2. Logistic Regression with L2 regularization
3. Trained on ground-truth evaluation dataset
4. Evaluated with precision, recall, F1, confusion matrix

References:
- Joachims, "Text Categorization with Support Vector Machines" (1998)
- Zhang et al., "A Comparative Study of TF-IDF, LSI and Multi-Words
  for Text Classification" (2011)
"""

import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BaselineMetrics:
    """Evaluation metrics from the baseline model."""
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    confusion_matrix: dict  # {actual_label: {predicted_label: count}}
    per_category: dict  # {category: {precision, recall, f1, support}}
    model_name: str = "tfidf_logreg"
    n_features: int = 0
    n_samples: int = 0

    def to_dict(self) -> dict:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "accuracy": round(self.accuracy, 4),
            "confusion_matrix": self.confusion_matrix,
            "per_category": self.per_category,
            "model_name": self.model_name,
            "n_features": self.n_features,
            "n_samples": self.n_samples,
        }


class BaselineClassifier:
    """
    TF-IDF + Logistic Regression baseline for scam classification.

    Used solely for benchmarking — proves that NETRA's LLM reasoning
    outperforms a classical ML approach on the same dataset.
    """

    def __init__(self):
        self.vectorizer = None
        self.classifier = None
        self.is_trained = False
        self.label_map: dict[str, int] = {}
        self.inverse_label_map: dict[int, str] = {}

    def train(self, texts: list[str], labels: list[str]) -> BaselineMetrics:
        """
        Train TF-IDF + Logistic Regression on ground-truth dataset.

        Uses 5-fold stratified cross-validation for robust metrics,
        then trains final model on full dataset.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_predict, StratifiedKFold
        from sklearn.metrics import (
            precision_score, recall_score, f1_score, accuracy_score,
            confusion_matrix, classification_report
        )
        import numpy as np

        logger.info(f"Training baseline on {len(texts)} samples")

        # Build label mapping
        unique_labels = sorted(set(labels))
        self.label_map = {label: i for i, label in enumerate(unique_labels)}
        self.inverse_label_map = {i: label for label, i in self.label_map.items()}

        y = np.array([self.label_map[label] for label in labels])

        # TF-IDF: unigrams + bigrams, max 5000 features
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,  # Apply sublinear TF scaling (1 + log(tf))
            min_df=1,
            max_df=0.95,
        )
        X = self.vectorizer.fit_transform(texts)

        # Logistic Regression with L2 regularization
        self.classifier = LogisticRegression(
            C=1.0,
            max_iter=1000,
            multi_class="multinomial",
            solver="lbfgs",
            class_weight="balanced",  # Handle class imbalance
            random_state=42,
        )

        # Cross-validated predictions for honest evaluation
        n_folds = min(5, min(np.bincount(y)))
        if n_folds >= 2:
            cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
            y_pred = cross_val_predict(self.classifier, X, y, cv=cv)
        else:
            # Too few samples per class — train/predict on full set (overfitting acknowledged)
            self.classifier.fit(X, y)
            y_pred = self.classifier.predict(X)

        # Train final model on full dataset
        self.classifier.fit(X, y)
        self.is_trained = True

        # Compute metrics
        precision = precision_score(y, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y, y_pred, average="weighted", zero_division=0)
        accuracy = accuracy_score(y, y_pred)

        # Confusion matrix
        cm = confusion_matrix(y, y_pred)
        cm_dict = {}
        for i, actual_label in enumerate(unique_labels):
            cm_dict[actual_label] = {}
            for j, pred_label in enumerate(unique_labels):
                cm_dict[actual_label][pred_label] = int(cm[i][j])

        # Per-category metrics
        report = classification_report(y, y_pred, target_names=unique_labels, output_dict=True, zero_division=0)
        per_cat = {}
        for label in unique_labels:
            if label in report:
                per_cat[label] = {
                    "precision": round(report[label]["precision"], 4),
                    "recall": round(report[label]["recall"], 4),
                    "f1": round(report[label]["f1-score"], 4),
                    "support": int(report[label]["support"]),
                }

        metrics = BaselineMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            accuracy=accuracy,
            confusion_matrix=cm_dict,
            per_category=per_cat,
            n_features=X.shape[1],
            n_samples=len(texts),
        )

        logger.info(
            f"Baseline trained: F1={f1:.4f}, P={precision:.4f}, R={recall:.4f}, "
            f"Acc={accuracy:.4f} | {X.shape[1]} features, {len(texts)} samples"
        )
        return metrics

    def predict(self, text: str) -> tuple[str, float]:
        """
        Predict scam type for a single text.

        Returns: (predicted_label, confidence)
        """
        if not self.is_trained:
            return ("unknown", 0.0)

        import numpy as np

        X = self.vectorizer.transform([text])
        proba = self.classifier.predict_proba(X)[0]
        pred_idx = np.argmax(proba)

        return (self.inverse_label_map[pred_idx], float(proba[pred_idx]))

    def predict_batch(self, texts: list[str]) -> list[tuple[str, float]]:
        """Predict scam types for multiple texts."""
        if not self.is_trained:
            return [("unknown", 0.0)] * len(texts)

        import numpy as np

        X = self.vectorizer.transform(texts)
        probas = self.classifier.predict_proba(X)
        results = []
        for proba in probas:
            pred_idx = np.argmax(proba)
            results.append((self.inverse_label_map[pred_idx], float(proba[pred_idx])))
        return results
