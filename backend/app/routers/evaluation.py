"""
NETRA Evaluation & Intelligence Router — SETIE API Endpoints

Provides:
1. /api/evaluation/run     — Execute benchmark, train baseline, store results
2. /api/evaluation/latest  — Get latest evaluation results
3. /api/evaluation/history — Get all past evaluation runs
4. /api/intelligence/similar/{case_id} — Find similar cases
5. /api/intelligence/clusters — Get DBSCAN clusters
6. /api/intelligence/discovered-patterns — Get auto-discovered patterns
7. /api/intelligence/graph-stats — Graph algorithm results
8. /api/intelligence/pagerank — Top entities by PageRank
9. /api/intelligence/communities — Detected syndicates
"""

import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    get_db, Case, EvaluationRun, DiscoveredPattern, ScamPattern
)
# NOTE: Embedding, baseline, and graph services are imported lazily inside
# each endpoint to avoid startup failures if scikit-learn/networkx/numpy
# aren't installed yet (Railway builds can be slow).
from app.evaluation.benchmark import EVALUATION_DATASET

logger = logging.getLogger(__name__)

eval_router = APIRouter()
intel_router = APIRouter()


# ---------- Evaluation Endpoints ----------

class EvalRunResponse(BaseModel):
    """Response from running a benchmark evaluation."""
    f1_score: float
    precision: float
    recall: float
    accuracy: float
    total_cases: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    confusion_matrix: dict
    per_category: dict
    baseline_f1: float | None = None
    baseline_precision: float | None = None
    baseline_recall: float | None = None
    improvement_pct: float | None = None
    baseline_model: str | None = None
    llm_model: str | None = None
    duration_seconds: int = 0


@eval_router.post("/run", response_model=EvalRunResponse)
async def run_evaluation(db: AsyncSession = Depends(get_db)):
    """
    Execute the full evaluation suite:
    1. Run all 60 test cases through NETRA's detection pipeline
    2. Train TF-IDF + Logistic Regression baseline on the same data
    3. Compare F1 scores and compute improvement percentage
    4. Store results in evaluation_runs table
    """
    from app.agents.detection import DetectionAgent

    start_time = time.monotonic()
    agent = DetectionAgent(db)

    # Tracking
    tp, tn, fp, fn = 0, 0, 0, 0
    category_results: dict[str, dict] = {}
    misclassifications = []
    netra_model_used = None

    logger.info(f"Starting evaluation with {len(EVALUATION_DATASET)} test cases")

    for i, tc in enumerate(EVALUATION_DATASET):
        try:
            result = await agent.analyze(tc.text, "text")

            predicted_scam = bool(result.get("is_scam", False))
            confidence = result.get("confidence", 0)

            if netra_model_used is None:
                netra_model_used = result.get("model_used", "unknown")

            # Threshold: scam if is_scam=True AND confidence >= 0.4
            if tc.is_scam:
                if predicted_scam and confidence >= 0.4:
                    tp += 1
                    correct = True
                else:
                    fn += 1
                    correct = False
            else:
                if not predicted_scam or confidence < 0.4:
                    tn += 1
                    correct = True
                else:
                    fp += 1
                    correct = False

            # Per-category tracking
            cat = tc.category
            if cat not in category_results:
                category_results[cat] = {"correct": 0, "total": 0, "tp": 0, "fp": 0, "fn": 0}
            category_results[cat]["total"] += 1
            if correct:
                category_results[cat]["correct"] += 1
            if tc.is_scam and predicted_scam and confidence >= 0.4:
                category_results[cat]["tp"] += 1
            if not tc.is_scam and predicted_scam and confidence >= 0.4:
                category_results[cat]["fp"] += 1
            if tc.is_scam and (not predicted_scam or confidence < 0.4):
                category_results[cat]["fn"] += 1

            if not correct:
                misclassifications.append({
                    "text": tc.text[:100],
                    "expected": tc.expected_type or "benign",
                    "got": result.get("scam_type", "benign"),
                    "confidence": confidence,
                })

            logger.info(f"Eval [{i+1}/{len(EVALUATION_DATASET)}] {'✓' if correct else '✗'} {tc.category}")

        except Exception as e:
            logger.error(f"Eval case {i} failed: {e}")
            if tc.is_scam:
                fn += 1
            else:
                tn += 1  # Assume safe if error

    # Compute NETRA metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0

    # Confusion matrix
    confusion = {
        "scam": {"scam": tp, "benign": fn},
        "benign": {"scam": fp, "benign": tn},
    }

    # Per-category metrics
    per_cat = {}
    for cat, stats in category_results.items():
        cat_precision = stats["tp"] / (stats["tp"] + stats["fp"]) if (stats["tp"] + stats["fp"]) > 0 else 0
        cat_recall = stats["tp"] / (stats["tp"] + stats["fn"]) if (stats["tp"] + stats["fn"]) > 0 else 0
        cat_f1 = 2 * cat_precision * cat_recall / (cat_precision + cat_recall) if (cat_precision + cat_recall) > 0 else 0
        per_cat[cat] = {
            "precision": round(cat_precision, 4),
            "recall": round(cat_recall, 4),
            "f1": round(cat_f1, 4),
            "accuracy": round(stats["correct"] / stats["total"], 4) if stats["total"] > 0 else 0,
            "total": stats["total"],
        }

    # --- Train Baseline Model ---
    from app.services.baseline_model import BaselineClassifier
    baseline = BaselineClassifier()
    baseline_texts = [tc.text for tc in EVALUATION_DATASET]
    baseline_labels = [tc.expected_type or "benign" for tc in EVALUATION_DATASET]

    try:
        baseline_metrics = baseline.train(baseline_texts, baseline_labels)
        baseline_f1 = baseline_metrics.f1_score
        baseline_precision = baseline_metrics.precision
        baseline_recall = baseline_metrics.recall
        improvement = ((f1 - baseline_f1) / baseline_f1 * 100) if baseline_f1 > 0 else 0
        logger.info(f"Baseline F1: {baseline_f1:.4f}, NETRA F1: {f1:.4f}, Improvement: {improvement:.1f}%")
    except Exception as e:
        logger.warning(f"Baseline training failed: {e}")
        baseline_f1 = None
        baseline_precision = None
        baseline_recall = None
        improvement = None

    duration = int(time.monotonic() - start_time)

    # Store in DB
    eval_run = EvaluationRun(
        total_cases=len(EVALUATION_DATASET),
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        accuracy=accuracy,
        confusion_matrix=confusion,
        per_category=per_cat,
        misclassifications=misclassifications[:20],
        baseline_model="tfidf_logreg" if baseline_f1 else None,
        baseline_f1=baseline_f1,
        baseline_precision=baseline_precision,
        baseline_recall=baseline_recall,
        improvement_pct=improvement,
        llm_model=netra_model_used,
        duration_seconds=duration,
    )
    db.add(eval_run)
    await db.flush()

    logger.info(f"Evaluation complete: F1={f1:.4f}, P={precision:.4f}, R={recall:.4f} in {duration}s")

    return EvalRunResponse(
        f1_score=round(f1, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        accuracy=round(accuracy, 4),
        total_cases=len(EVALUATION_DATASET),
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        confusion_matrix=confusion,
        per_category=per_cat,
        baseline_f1=round(baseline_f1, 4) if baseline_f1 else None,
        baseline_precision=round(baseline_precision, 4) if baseline_precision else None,
        baseline_recall=round(baseline_recall, 4) if baseline_recall else None,
        improvement_pct=round(improvement, 1) if improvement else None,
        baseline_model="tfidf_logreg" if baseline_f1 else None,
        llm_model=netra_model_used,
        duration_seconds=duration,
    )


@eval_router.get("/latest")
async def get_latest_evaluation(db: AsyncSession = Depends(get_db)):
    """Get the most recent evaluation run results."""
    stmt = select(EvaluationRun).order_by(desc(EvaluationRun.run_date)).limit(1)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        return {"status": "no_evaluation_run", "message": "No evaluation has been run yet. POST /api/evaluation/run to start."}

    return {
        "f1_score": run.f1_score,
        "precision": run.precision,
        "recall": run.recall,
        "accuracy": run.accuracy,
        "total_cases": run.total_cases,
        "true_positives": run.true_positives,
        "true_negatives": run.true_negatives,
        "false_positives": run.false_positives,
        "false_negatives": run.false_negatives,
        "confusion_matrix": run.confusion_matrix,
        "per_category": run.per_category,
        "baseline_model": run.baseline_model,
        "baseline_f1": run.baseline_f1,
        "baseline_precision": run.baseline_precision,
        "baseline_recall": run.baseline_recall,
        "improvement_pct": run.improvement_pct,
        "llm_model": run.llm_model,
        "duration_seconds": run.duration_seconds,
        "run_date": run.run_date.isoformat() if run.run_date else None,
    }


@eval_router.get("/history")
async def get_evaluation_history(db: AsyncSession = Depends(get_db)):
    """Get all past evaluation runs."""
    stmt = select(EvaluationRun).order_by(desc(EvaluationRun.run_date)).limit(20)
    result = await db.execute(stmt)
    runs = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "f1_score": r.f1_score,
            "precision": r.precision,
            "recall": r.recall,
            "accuracy": r.accuracy,
            "baseline_f1": r.baseline_f1,
            "improvement_pct": r.improvement_pct,
            "total_cases": r.total_cases,
            "llm_model": r.llm_model,
            "duration_seconds": r.duration_seconds,
            "run_date": r.run_date.isoformat() if r.run_date else None,
        }
        for r in runs
    ]


# ---------- Intelligence Endpoints ----------

@intel_router.get("/similar/{case_id}")
async def find_similar_cases(case_id: str, db: AsyncSession = Depends(get_db)):
    """Find cases semantically similar to a given case using embedding cosine similarity."""
    # Load the target case
    from uuid import UUID
    try:
        stmt = select(Case).where(Case.id == UUID(case_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid case ID format")

    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not case.embedding:
        # Generate embedding on-the-fly
        from app.services.embeddings import get_embedding_service
        svc = get_embedding_service()
        embedding = await svc.embed_text(case.input_text)
        case.embedding = embedding
        await db.flush()
    else:
        embedding = case.embedding

    from app.services.embeddings import get_embedding_service as _get_embed_svc
    svc = _get_embed_svc()
    similar = await svc.find_similar_cases(
        embedding, db, threshold=0.75, limit=10, exclude_case_id=case_id
    )

    return {
        "case_id": case_id,
        "similar_cases": [s.to_dict() for s in similar],
        "total_found": len(similar),
    }


@intel_router.get("/clusters")
async def get_case_clusters(db: AsyncSession = Depends(get_db)):
    """Run DBSCAN clustering on all case embeddings to discover patterns."""
    from app.services.embeddings import get_embedding_service
    svc = get_embedding_service()
    clusters = await svc.cluster_cases(db)

    return {
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "case_ids": c.case_ids,
                "size": len(c.case_ids),
                "avg_similarity": round(c.avg_similarity, 4),
                "dominant_scam_type": c.dominant_scam_type,
                "is_known_pattern": c.is_known_pattern,
                "keywords": c.keywords,
            }
            for c in clusters
        ],
        "total_clusters": len(clusters),
    }


@intel_router.get("/discovered-patterns")
async def get_discovered_patterns(db: AsyncSession = Depends(get_db)):
    """Get auto-discovered scam patterns from embedding clustering."""
    stmt = select(DiscoveredPattern).order_by(desc(DiscoveredPattern.created_at)).limit(20)
    result = await db.execute(stmt)
    patterns = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "pattern_name": p.pattern_name,
            "description": p.description,
            "cluster_size": p.cluster_size,
            "avg_similarity": p.avg_similarity,
            "keywords": p.keywords,
            "status": p.status,
            "first_seen": p.first_seen.isoformat() if p.first_seen else None,
        }
        for p in patterns
    ]


@intel_router.post("/discover")
async def run_pattern_discovery(db: AsyncSession = Depends(get_db)):
    """
    Run the full SETIE discovery pipeline:
    1. Cluster all case embeddings with DBSCAN
    2. Identify clusters that don't match known patterns
    3. Generate pattern descriptions for new clusters via LLM
    4. Store as discovered_patterns
    """
    from app.services.llm import get_llm_service

    from app.services.embeddings import get_embedding_service
    svc = get_embedding_service()
    clusters = await svc.cluster_cases(db)

    if not clusters:
        return {"discovered": 0, "message": "Not enough cases for clustering. Analyze more scams first."}

    # Load known pattern names
    stmt = select(ScamPattern.name)
    result = await db.execute(stmt)
    known_names = {name.lower() for name in result.scalars().all()}

    new_patterns = []
    llm = get_llm_service()

    for cluster in clusters:
        # Check if cluster's dominant type is unknown or not in known patterns
        if cluster.is_known_pattern and cluster.dominant_scam_type and cluster.dominant_scam_type.lower() in known_names:
            continue

        # This is a potentially new pattern — generate description
        try:
            keyword_str = ", ".join(cluster.keywords[:10])
            prompt = f"""Analyze these keywords from a cluster of {len(cluster.case_ids)} related scam cases and suggest a name and description for this emerging scam pattern.

Keywords: {keyword_str}

Respond in JSON:
{{"pattern_name": "Short descriptive name", "description": "2-3 sentence description of the scam pattern"}}"""

            response = await llm.generate(prompt=prompt, response_format="json", tier="fast", temperature=0.3)
            parsed = response.parse_json()

            if parsed:
                pattern = DiscoveredPattern(
                    pattern_name=parsed.get("pattern_name", f"Unknown Pattern #{cluster.cluster_id}"),
                    description=parsed.get("description", ""),
                    cluster_size=len(cluster.case_ids),
                    avg_similarity=cluster.avg_similarity,
                    representative_cases=cluster.case_ids[:5],
                    keywords=cluster.keywords,
                    status="candidate",
                )
                db.add(pattern)
                new_patterns.append(pattern.pattern_name)

        except Exception as e:
            logger.warning(f"Pattern generation failed for cluster {cluster.cluster_id}: {e}")

    if new_patterns:
        await db.flush()

    return {
        "discovered": len(new_patterns),
        "patterns": new_patterns,
        "total_clusters": len(clusters),
    }


# --- Graph Intelligence Endpoints ---

@intel_router.get("/graph-stats")
async def get_graph_stats(db: AsyncSession = Depends(get_db)):
    """Get comprehensive graph statistics including algorithm results."""
    from app.services.graph_intelligence import GraphIntelligenceService
    svc = GraphIntelligenceService()
    stats = await svc.get_graph_stats(db)
    return stats.to_dict()


@intel_router.get("/pagerank")
async def get_pagerank(top_n: int = 10, db: AsyncSession = Depends(get_db)):
    """Get top entities ranked by PageRank algorithm."""
    from app.services.graph_intelligence import GraphIntelligenceService
    svc = GraphIntelligenceService()
    ranked = await svc.get_pagerank(db, top_n=top_n)
    return {
        "algorithm": "PageRank",
        "description": "Entities ranked by importance in the fraud network (higher = more connected to other important entities)",
        "entities": [r.to_dict() for r in ranked],
    }


@intel_router.get("/communities")
async def get_communities(db: AsyncSession = Depends(get_db)):
    """Detect fraud syndicates using Louvain community detection."""
    from app.services.graph_intelligence import GraphIntelligenceService
    svc = GraphIntelligenceService()
    communities = await svc.detect_communities(db)
    return {
        "algorithm": "Louvain Community Detection",
        "description": "Groups of densely connected entities that may represent coordinated fraud syndicates",
        "communities": [c.to_dict() for c in communities],
        "total": len(communities),
    }


@intel_router.get("/centrality")
async def get_centrality(top_n: int = 10, db: AsyncSession = Depends(get_db)):
    """Get multi-metric centrality analysis (degree, betweenness, eigenvector)."""
    from app.services.graph_intelligence import GraphIntelligenceService
    svc = GraphIntelligenceService()
    centrality = await svc.get_centrality(db, top_n=top_n)
    return {
        "algorithms": ["Degree Centrality", "Betweenness Centrality", "Eigenvector Centrality"],
        "results": centrality,
    }
