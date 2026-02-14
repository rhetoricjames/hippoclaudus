"""Pure math tests for recency_decay, access_score, and composite_score."""

import math
import sys
import time
from pathlib import Path

import pytest

MCP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_ROOT))

from hippoclaudus.scoring import recency_decay, access_score, composite_score, ScoringWeights


# ---------------------------------------------------------------------------
# recency_decay
# ---------------------------------------------------------------------------

class TestRecencyDecay:

    def test_brand_new_memory(self):
        now = time.time()
        score = recency_decay(now, half_life_days=14.0, now=now)
        assert abs(score - 1.0) < 0.001

    def test_one_half_life(self):
        now = time.time()
        created = now - (14 * 86400)  # 14 days ago
        score = recency_decay(created, half_life_days=14.0, now=now)
        assert abs(score - 0.5) < 0.01

    def test_two_half_lives(self):
        now = time.time()
        created = now - (28 * 86400)  # 28 days ago
        score = recency_decay(created, half_life_days=14.0, now=now)
        assert abs(score - 0.25) < 0.01

    def test_very_old_memory(self):
        now = time.time()
        created = now - (365 * 86400)  # 1 year ago
        score = recency_decay(created, half_life_days=14.0, now=now)
        assert score < 0.001

    def test_future_timestamp_clamped(self):
        """Memory created in the future should still get ~1.0 (clamped by max(0, age))."""
        now = time.time()
        created = now + 86400  # 1 day in the future
        score = recency_decay(created, half_life_days=14.0, now=now)
        assert abs(score - 1.0) < 0.001

    @pytest.mark.xfail(reason="Known: ZeroDivisionError with zero half-life")
    def test_zero_half_life(self):
        now = time.time()
        created = now - 86400
        score = recency_decay(created, half_life_days=0.0, now=now)
        assert score == 0.0

    @pytest.mark.xfail(reason="Known: Negative half-life produces inverted (>1.0) scores")
    def test_negative_half_life(self):
        now = time.time()
        created = now - (7 * 86400)
        score = recency_decay(created, half_life_days=-14.0, now=now)
        assert 0.0 <= score <= 1.0

    def test_short_half_life(self):
        now = time.time()
        created = now - (1 * 86400)  # 1 day ago
        score = recency_decay(created, half_life_days=1.0, now=now)
        assert abs(score - 0.5) < 0.01

    def test_monotonically_decreasing(self):
        now = time.time()
        scores = []
        for days in range(0, 100, 10):
            created = now - (days * 86400)
            scores.append(recency_decay(created, half_life_days=14.0, now=now))
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], f"Not monotonic at index {i}"


# ---------------------------------------------------------------------------
# access_score
# ---------------------------------------------------------------------------

class TestAccessScore:

    def test_zero_access(self):
        assert access_score(0) == 0.0

    def test_negative_access(self):
        assert access_score(-5) == 0.0

    def test_one_access(self):
        score = access_score(1)
        assert 0.0 < score < 0.5  # Should be low

    def test_fifty_accesses(self):
        score = access_score(50)
        assert abs(score - 1.0) < 0.01  # Saturates around 50

    def test_huge_access_capped(self):
        score = access_score(10000)
        assert score <= 1.0

    def test_monotonically_increasing(self):
        scores = [access_score(i) for i in range(0, 100)]
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1], f"Not monotonic at index {i}"


# ---------------------------------------------------------------------------
# composite_score
# ---------------------------------------------------------------------------

class TestCompositeScore:

    def test_perfect_memory(self):
        """Brand new, high similarity, many accesses → near max."""
        now = time.time()
        score = composite_score(
            cosine_sim=1.0,
            created_at=now,
            access_count=50,
            weights=ScoringWeights(relevance=0.6, recency=0.3, access=0.1, half_life_days=14.0),
        )
        assert score > 0.9

    def test_worthless_memory(self):
        """Very old, zero similarity, no accesses → near zero."""
        now = time.time()
        score = composite_score(
            cosine_sim=0.0,
            created_at=now - (365 * 86400),
            access_count=0,
        )
        assert score < 0.05

    def test_custom_weights(self):
        """Relevance-only weights should ignore recency/access."""
        now = time.time()
        score = composite_score(
            cosine_sim=0.8,
            created_at=now - (365 * 86400),  # very old
            access_count=0,
            weights=ScoringWeights(relevance=1.0, recency=0.0, access=0.0),
        )
        assert abs(score - 0.8) < 0.01

    def test_cosine_sim_clamped(self):
        """Cosine sim > 1.0 should be clamped to 1.0."""
        now = time.time()
        score = composite_score(cosine_sim=1.5, created_at=now, access_count=0)
        # With default weights: 0.6 * 1.0 (clamped) + 0.3 * 1.0 (new) + 0.1 * 0.0 = 0.9
        assert score <= 1.0

    def test_cosine_sim_negative_clamped(self):
        """Cosine sim < 0 should be clamped to 0.0."""
        now = time.time()
        score = composite_score(cosine_sim=-0.5, created_at=now, access_count=0)
        # 0.6 * 0.0 + 0.3 * 1.0 + 0.1 * 0.0 = 0.3
        assert abs(score - 0.3) < 0.01

    @pytest.mark.xfail(reason="Known: No output clamping with extreme weights")
    def test_extreme_weights_no_clamping(self):
        """Extreme weights could produce score > 1.0 since there's no final clamp."""
        now = time.time()
        score = composite_score(
            cosine_sim=1.0,
            created_at=now,
            access_count=50,
            weights=ScoringWeights(relevance=5.0, recency=5.0, access=5.0),
        )
        assert 0.0 <= score <= 1.0

    def test_default_weights(self):
        """Default weights should sum to 1.0."""
        w = ScoringWeights()
        assert abs((w.relevance + w.recency + w.access) - 1.0) < 0.001
