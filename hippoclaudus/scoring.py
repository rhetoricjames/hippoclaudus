"""Weighted decay scoring for memory retrieval relevance.

Formula (from Phase 2B spec):
    Score = (w_r * cosine_similarity) + (w_t * recency_decay) + (w_a * access_frequency)

Where:
    - cosine_similarity: semantic match between query and memory embedding
    - recency_decay: exponential decay based on age (half-life configurable)
    - access_frequency: how often a memory has been retrieved (log-scaled)
"""

import math
import time
from dataclasses import dataclass


@dataclass
class ScoringWeights:
    """Tunable weights for the scoring formula."""
    relevance: float = 0.6    # w_r: semantic similarity weight
    recency: float = 0.3      # w_t: time decay weight
    access: float = 0.1       # w_a: access frequency weight
    half_life_days: float = 14.0  # days until recency score halves


def recency_decay(created_at: float, half_life_days: float = 14.0, now: float = None) -> float:
    """Exponential decay based on memory age.

    Returns a value between 0.0 and 1.0, where 1.0 is brand new
    and 0.5 is exactly one half-life old.
    """
    if now is None:
        now = time.time()
    age_seconds = max(0, now - created_at)
    age_days = age_seconds / 86400.0
    return math.exp(-0.693 * age_days / half_life_days)  # ln(2) ≈ 0.693


def access_score(access_count: int) -> float:
    """Log-scaled access frequency. Returns 0.0 for never-accessed, ~1.0 for heavily used."""
    if access_count <= 0:
        return 0.0
    return min(1.0, math.log1p(access_count) / math.log1p(50))  # saturates around 50 accesses


def composite_score(
    cosine_sim: float,
    created_at: float,
    access_count: int = 0,
    weights: ScoringWeights = None,
) -> float:
    """Compute the weighted composite score for a memory.

    Args:
        cosine_sim: Cosine similarity between query and memory (0.0 to 1.0)
        created_at: Unix timestamp of memory creation
        access_count: Number of times this memory has been retrieved
        weights: Scoring weight configuration

    Returns:
        Composite score between 0.0 and 1.0
    """
    if weights is None:
        weights = ScoringWeights()

    r = max(0.0, min(1.0, cosine_sim))
    t = recency_decay(created_at, weights.half_life_days)
    a = access_score(access_count)

    return (weights.relevance * r) + (weights.recency * t) + (weights.access * a)
