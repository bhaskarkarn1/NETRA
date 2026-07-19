"""
NETRA Embedding Service — Semantic Case Intelligence (SETIE Layer 1)

Transforms scam text into 768-dimensional embedding vectors using Gemini
text-embedding-004, enabling:
- Cross-case similarity detection (cosine similarity)
- Automated syndicate detection (shared entities across similar cases)
- Zero-day pattern discovery via DBSCAN clustering (Layer 2)

References:
- Mikolov et al., "Distributed Representations of Words and Phrases" (2013)
- Reimers & Gurevych, "Sentence-BERT" (2019)
- Google, "text-embedding-004 model card" (2024)
"""

import logging
import math
from dataclasses import dataclass
from typing import Any

from google import genai
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import Case

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIM = 768


@dataclass
class SimilarCase:
    """A case with computed similarity score."""
    case_id: str
    scam_type: str | None
    confidence: float
    similarity: float  # Cosine similarity [0, 1]
    shared_entities: list[str]  # Entities appearing in both cases
    snippet: str  # First 200 chars of input_text

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "scam_type": self.scam_type,
            "confidence": self.confidence,
            "similarity": round(self.similarity, 4),
            "shared_entities": self.shared_entities,
            "snippet": self.snippet,
        }


@dataclass
class CaseCluster:
    """A group of semantically similar cases found by DBSCAN."""
    cluster_id: int
    case_ids: list[str]
    avg_similarity: float
    dominant_scam_type: str | None
    is_known_pattern: bool  # Whether it matches an existing scam_patterns entry
    keywords: list[str]


class EmbeddingService:
    """
    Generate and compare text embeddings for scam intelligence.

    Uses Gemini text-embedding-004 (768-dim) with cosine similarity
    for cross-case linking and pattern discovery.
    """

    def __init__(self):
        self.settings = get_settings()
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.settings.GOOGLE_API_KEY)
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate a 768-dim embedding for the given text.

        Uses Gemini text-embedding-004 which produces normalized vectors,
        so cosine similarity can be computed as a simple dot product.
        """
        try:
            # Truncate to 2048 tokens (model limit for embeddings)
            truncated = text[:8000]

            result = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=truncated,
            )

            embedding = result.embeddings[0].values
            logger.info(f"Generated embedding: dim={len(embedding)}")
            return list(embedding)

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Return zero vector as fallback (will have 0 similarity with everything)
            return [0.0] * EMBEDDING_DIM

    async def find_similar_cases(
        self,
        embedding: list[float],
        db: AsyncSession,
        threshold: float = 0.80,
        limit: int = 5,
        exclude_case_id: str | None = None,
    ) -> list[SimilarCase]:
        """
        Find cases with cosine similarity above threshold.

        Loads all case embeddings from DB and computes similarity in-memory.
        For production, this would use pgvector or a vector DB.
        """
        try:
            stmt = select(Case).where(Case.embedding.isnot(None))
            if exclude_case_id:
                stmt = stmt.where(Case.id != exclude_case_id)

            result = await db.execute(stmt)
            cases = result.scalars().all()

            if not cases:
                return []

            similar = []
            for case in cases:
                case_embedding = case.embedding
                if not case_embedding or len(case_embedding) != len(embedding):
                    continue

                sim = self._cosine_similarity(embedding, case_embedding)

                if sim >= threshold:
                    similar.append(SimilarCase(
                        case_id=str(case.id),
                        scam_type=case.scam_type,
                        confidence=case.confidence or 0.0,
                        similarity=sim,
                        shared_entities=[],  # Populated by caller
                        snippet=case.input_text[:200] if case.input_text else "",
                    ))

            # Sort by similarity descending
            similar.sort(key=lambda x: x.similarity, reverse=True)
            return similar[:limit]

        except Exception as e:
            logger.error(f"Similar case search failed: {e}")
            return []

    async def cluster_cases(self, db: AsyncSession) -> list[CaseCluster]:
        """
        DBSCAN clustering on case embeddings to discover patterns.

        DBSCAN is used instead of K-Means because:
        1. No need to specify number of clusters in advance
        2. Naturally handles noise (unclustered cases)
        3. Finds arbitrarily shaped clusters in embedding space

        Parameters tuned for scam detection:
        - eps=0.25: Cosine distance threshold (1 - similarity)
        - min_samples=2: Minimum cases to form a cluster (low for demo)
        """
        try:
            stmt = select(Case).where(Case.embedding.isnot(None))
            result = await db.execute(stmt)
            cases = result.scalars().all()

            if len(cases) < 2:
                logger.info("Not enough cases for clustering")
                return []

            # Import here to avoid hard dependency
            from sklearn.cluster import DBSCAN
            from sklearn.metrics.pairwise import cosine_distances
            import numpy as np

            # Build embedding matrix
            embeddings = []
            valid_cases = []
            for case in cases:
                emb = case.embedding
                if emb and len(emb) == EMBEDDING_DIM:
                    embeddings.append(emb)
                    valid_cases.append(case)

            if len(embeddings) < 2:
                return []

            X = np.array(embeddings)

            # DBSCAN with cosine distance
            distance_matrix = cosine_distances(X)
            clustering = DBSCAN(eps=0.25, min_samples=2, metric="precomputed")
            labels = clustering.fit_predict(distance_matrix)

            # Group cases by cluster
            clusters_map: dict[int, list] = {}
            for idx, label in enumerate(labels):
                if label == -1:  # Noise
                    continue
                if label not in clusters_map:
                    clusters_map[label] = []
                clusters_map[label].append(valid_cases[idx])

            # Build CaseCluster objects
            clusters = []
            for cluster_id, cluster_cases in clusters_map.items():
                case_ids = [str(c.id) for c in cluster_cases]

                # Compute average pairwise similarity
                cluster_indices = [
                    i for i, l in enumerate(labels) if l == cluster_id
                ]
                pairwise_sims = []
                for i in range(len(cluster_indices)):
                    for j in range(i + 1, len(cluster_indices)):
                        sim = 1 - distance_matrix[cluster_indices[i]][cluster_indices[j]]
                        pairwise_sims.append(sim)
                avg_sim = sum(pairwise_sims) / len(pairwise_sims) if pairwise_sims else 0

                # Find dominant scam type
                type_counts: dict[str, int] = {}
                for c in cluster_cases:
                    if c.scam_type:
                        type_counts[c.scam_type] = type_counts.get(c.scam_type, 0) + 1
                dominant = max(type_counts, key=type_counts.get) if type_counts else None

                # Extract keywords from case texts
                all_text = " ".join(c.input_text for c in cluster_cases if c.input_text)
                keywords = self._extract_keywords(all_text)

                clusters.append(CaseCluster(
                    cluster_id=cluster_id,
                    case_ids=case_ids,
                    avg_similarity=avg_sim,
                    dominant_scam_type=dominant,
                    is_known_pattern=dominant is not None,
                    keywords=keywords[:10],
                ))

            logger.info(f"DBSCAN found {len(clusters)} clusters from {len(valid_cases)} cases")
            return clusters

        except ImportError:
            logger.warning("scikit-learn not installed — clustering disabled")
            return []
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            return []

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _extract_keywords(text: str, top_n: int = 10) -> list[str]:
        """Extract top keywords using simple TF approach."""
        import re
        from collections import Counter

        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "not", "no", "nor", "if", "then", "so", "that",
            "this", "it", "its", "i", "you", "he", "she", "we", "they",
            "me", "him", "her", "us", "them", "my", "your", "his", "our",
            "their", "what", "which", "who", "when", "where", "how",
            "all", "each", "every", "both", "few", "more", "most",
            "other", "some", "such", "than", "too", "very", "just",
            "sir", "madam", "please", "dear", "customer", "hello",
        }

        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        filtered = [w for w in words if w not in stopwords]
        counts = Counter(filtered)
        return [word for word, _ in counts.most_common(top_n)]


# Singleton
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
