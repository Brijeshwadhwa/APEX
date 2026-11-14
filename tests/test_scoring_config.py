"""Unit tests for scoring configuration, boundaries, achievement aggregation, and hash stability."""

from decimal import Decimal
import pytest
from core.scoring_config import (
    ACADEMIC_WEIGHT,
    FINANCIAL_NEED_WEIGHT,
    ACHIEVEMENT_WEIGHT,
    MIN_ACADEMIC_PERCENTAGE,
    MAX_HOUSEHOLD_INCOME,
    compute_academic_score,
    compute_financial_need_score,
    compute_achievement_score,
    resolve_recommendation,
    get_configuration_hash,
    RECOMMENDATION_HIGH_PRIORITY,
    RECOMMENDATION_RECOMMENDED,
    RECOMMENDATION_CONSIDER,
    RECOMMENDATION_LOW_PRIORITY,
)


def test_scoring_weights_sum_to_100():
    total_weights = ACADEMIC_WEIGHT + FINANCIAL_NEED_WEIGHT + ACHIEVEMENT_WEIGHT
    assert total_weights == Decimal("100.0")


def test_academic_score_boundaries():
    # Percentage None remains None
    assert compute_academic_score(None) is None

    # Exactly 0% -> 0.00
    assert compute_academic_score(Decimal("0.0")) == Decimal("0.00")

    # Minimum eligible threshold 60% -> (60/100)*40 = 24.00
    assert compute_academic_score(Decimal("60.0")) == Decimal("24.00")

    # 75.5% -> (75.5/100)*40 = 30.20
    assert compute_academic_score(Decimal("75.5")) == Decimal("30.20")

    # 100% -> 40.00
    assert compute_academic_score(Decimal("100.0")) == Decimal("40.00")

    # Out of bounds raises ValueError
    with pytest.raises(ValueError):
        compute_academic_score(Decimal("-5.0"))
    with pytest.raises(ValueError):
        compute_academic_score(Decimal("105.0"))


def test_financial_income_band_boundaries():
    # None remains None
    score, band = compute_financial_need_score(None)
    assert score is None
    assert band is None

    # Lower boundary ₹0
    score, band = compute_financial_need_score(Decimal("0.0"))
    assert score == Decimal("35.0")
    assert band == "₹0–₹150,000"

    # Exact boundary ₹150,000 -> 35
    score, band = compute_financial_need_score(Decimal("150000.0"))
    assert score == Decimal("35.0")

    # Just above boundary ₹150,001 -> 28
    score, band = compute_financial_need_score(Decimal("150001.0"))
    assert score == Decimal("28.0")
    assert band == "₹150,001–₹250,000"

    # Exact boundary ₹250,000 -> 28
    score, band = compute_financial_need_score(Decimal("250000.0"))
    assert score == Decimal("28.0")

    # Just above boundary ₹250,001 -> 20
    score, band = compute_financial_need_score(Decimal("250001.0"))
    assert score == Decimal("20.0")
    assert band == "₹250,001–₹400,000"

    # Exact boundary ₹400,000 -> 20
    score, band = compute_financial_need_score(Decimal("400000.0"))
    assert score == Decimal("20.0")

    # Just above boundary ₹400,001 -> 10
    score, band = compute_financial_need_score(Decimal("400001.0"))
    assert score == Decimal("10.0")
    assert band == "₹400,001–₹600,000"

    # Exact boundary ₹600,000 -> 10
    score, band = compute_financial_need_score(Decimal("600000.0"))
    assert score == Decimal("10.0")

    # Above ₹600,000 -> 0
    score, band = compute_financial_need_score(Decimal("600001.0"))
    assert score == Decimal("0.0")
    assert band == "Above ₹600,000"

    # Negative income raises ValueError
    with pytest.raises(ValueError):
        compute_financial_need_score(Decimal("-1.0"))


def test_achievement_aggregation_and_deduplication():
    achievements = [
        {"title": "International Coding Olympiad", "level": "INTERNATIONAL", "is_verified": True, "certificate_id": "CERT-101"},
        {"title": "National Science Fair", "level": "NATIONAL", "is_verified": True, "certificate_id": "CERT-102"},
        # Duplicate certificate ID:
        {"title": "Duplicate Fair Award", "level": "NATIONAL", "is_verified": True, "certificate_id": "CERT-102"},
        # Unverified achievement:
        {"title": "State Debate Championship", "level": "STATE", "is_verified": False, "certificate_id": "CERT-103"},
        # Duplicate title without certificate:
        {"title": "District Hackathon", "level": "DISTRICT", "is_verified": True},
        {"title": "District Hackathon", "level": "DISTRICT", "is_verified": True},
    ]

    capped_score, raw_score, verified_cnt, rej_cnt, titles = compute_achievement_score(achievements)
    # Valid verified: International (15) + National (10) + District (3) = raw 28.0
    # Capped at MAX 25.0
    assert raw_score == Decimal("28.0")
    assert capped_score == Decimal("25.0")
    assert verified_cnt == 3
    assert rej_cnt == 3
    assert len(titles) == 3


def test_recommendation_thresholds():
    assert resolve_recommendation(Decimal("85.0")) == RECOMMENDATION_HIGH_PRIORITY
    assert resolve_recommendation(Decimal("80.0")) == RECOMMENDATION_HIGH_PRIORITY
    assert resolve_recommendation(Decimal("79.99")) == RECOMMENDATION_RECOMMENDED
    assert resolve_recommendation(Decimal("65.0")) == RECOMMENDATION_RECOMMENDED
    assert resolve_recommendation(Decimal("64.9")) == RECOMMENDATION_CONSIDER
    assert resolve_recommendation(Decimal("50.0")) == RECOMMENDATION_CONSIDER
    assert resolve_recommendation(Decimal("49.9")) == RECOMMENDATION_LOW_PRIORITY


def test_configuration_hash_stability():
    h1 = get_configuration_hash()
    h2 = get_configuration_hash()
    assert isinstance(h1, str)
    assert len(h1) == 64
    assert h1 == h2

