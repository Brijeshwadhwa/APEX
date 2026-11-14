"""Centralized scoring and eligibility configuration for Grant and Scholarship Application Evaluator.

Every scoring rule, weight, income band, achievement point value, and recommendation
threshold is defined here using Python's Decimal type to eliminate floating point
imprecision. A cryptographic configuration hash guarantees rubric version integrity.
"""

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

RUBRIC_VERSION: str = "1.0.0"

# --- SCORING WEIGHTS (Total: 100) ---
ACADEMIC_WEIGHT: Decimal = Decimal("40.0")
FINANCIAL_NEED_WEIGHT: Decimal = Decimal("35.0")
ACHIEVEMENT_WEIGHT: Decimal = Decimal("25.0")

# --- HARD ELIGIBILITY BOUNDARIES ---
MIN_ACADEMIC_PERCENTAGE: Decimal = Decimal("60.0")
MAX_HOUSEHOLD_INCOME: Decimal = Decimal("600000.0")

# --- INCOME SCORING BANDS (Annual Household Income in INR -> Score out of 35) ---
# Format: (min_inc_exclusive, max_inc_inclusive, score)
# Note: ₹0 to ₹150,000 is inclusive on both ends for the lowest bracket.
INCOME_BANDS: List[Tuple[Decimal, Decimal, Decimal]] = [
    (Decimal("0.0"), Decimal("150000.0"), Decimal("35.0")),
    (Decimal("150000.0"), Decimal("250000.0"), Decimal("28.0")),
    (Decimal("250000.0"), Decimal("400000.0"), Decimal("20.0")),
    (Decimal("400000.0"), Decimal("600000.0"), Decimal("10.0")),
]
INCOME_ABOVE_MAX_SCORE: Decimal = Decimal("0.0")

# --- ACHIEVEMENT VALUATION (Project policy points per verified unique achievement) ---
MAX_ACHIEVEMENT_SCORE: Decimal = Decimal("25.0")
ACHIEVEMENT_LEVEL_POINTS: Dict[str, Decimal] = {
    "INTERNATIONAL": Decimal("15.0"),
    "NATIONAL": Decimal("10.0"),
    "STATE": Decimal("6.0"),
    "DISTRICT": Decimal("3.0"),
    "INSTITUTIONAL": Decimal("1.0"),
}

# --- RECOMMENDATION THRESHOLDS (Total Score out of 100) ---
THRESHOLD_HIGH_PRIORITY: Decimal = Decimal("80.0")
THRESHOLD_RECOMMENDED: Decimal = Decimal("65.0")
THRESHOLD_CONSIDER: Decimal = Decimal("50.0")

RECOMMENDATION_HIGH_PRIORITY: str = "High Priority"
RECOMMENDATION_RECOMMENDED: str = "Recommended"
RECOMMENDATION_CONSIDER: str = "Consider"
RECOMMENDATION_LOW_PRIORITY: str = "Low Priority"

# --- PROHIBITED ATTRIBUTES (Strictly prohibited from influencing scores) ---
PROHIBITED_SCORING_ATTRIBUTES: Tuple[str, ...] = (
    "gender",
    "religion",
    "caste",
    "race",
    "ethnicity",
    "political_affiliation",
    "marital_status",
    "nationality",
)


def compute_academic_score(percentage: Optional[Decimal]) -> Optional[Decimal]:
    """Calculate academic score out of 40 based on percentage (0-100).

    Returns None if percentage is None.
    Formula: (percentage / 100) * ACADEMIC_WEIGHT
    """
    if percentage is None:
        return None
    if percentage < Decimal("0.0") or percentage > Decimal("100.0"):
        raise ValueError(f"Academic percentage {percentage} out of bounds (0-100).")
    raw = (percentage / Decimal("100.0")) * ACADEMIC_WEIGHT
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_financial_need_score(household_income: Optional[Decimal]) -> Tuple[Optional[Decimal], Optional[str]]:
    """Determine financial need score out of 35 and band description.

    Returns (None, None) if household_income is None.
    Bands:
      ₹0 – ₹150,000         -> 35
      ₹150,001 – ₹250,000   -> 28
      ₹250,001 – ₹400,000   -> 20
      ₹400,001 – ₹600,000   -> 10
      Above ₹600,000        -> 0
    """
    if household_income is None:
        return None, None
    if household_income < Decimal("0.0"):
        raise ValueError(f"Household income cannot be negative: {household_income}")

    if household_income <= Decimal("150000.0"):
        return Decimal("35.0"), "₹0–₹150,000"
    elif household_income <= Decimal("250000.0"):
        return Decimal("28.0"), "₹150,001–₹250,000"
    elif household_income <= Decimal("400000.0"):
        return Decimal("20.0"), "₹250,001–₹400,000"
    elif household_income <= Decimal("600000.0"):
        return Decimal("10.0"), "₹400,001–₹600,000"
    else:
        return INCOME_ABOVE_MAX_SCORE, "Above ₹600,000"


def compute_achievement_score(
    achievements: List[Dict[str, Any]],
) -> Tuple[Decimal, Decimal, int, int, List[str]]:
    """Aggregate verified, non-duplicate achievement scores up to 25.

    Returns:
      (capped_score, raw_score, verified_count, duplicate_or_unverified_count, processed_titles)
    """
    seen_identifiers = set()
    raw_total = Decimal("0.0")
    verified_count = 0
    rejected_count = 0
    processed_titles: List[str] = []

    for ach in achievements:
        is_verified = ach.get("is_verified", False)
        title = (ach.get("title") or "").strip().lower()
        level = (ach.get("level") or "").strip().upper()
        cert_id = (ach.get("certificate_id") or "").strip().lower()

        # Deduplication key based on title or certificate ID
        dedup_key = cert_id if cert_id else title

        if not is_verified:
            rejected_count += 1
            continue

        if not dedup_key or dedup_key in seen_identifiers:
            rejected_count += 1
            continue

        seen_identifiers.add(dedup_key)
        points = ACHIEVEMENT_LEVEL_POINTS.get(level, Decimal("1.0"))
        raw_total += points
        verified_count += 1
        processed_titles.append(f"{ach.get('title')} ({level}: {points} pts)")

    capped_total = min(raw_total, MAX_ACHIEVEMENT_SCORE)
    return capped_total, raw_total, verified_count, rejected_count, processed_titles


def resolve_recommendation(total_score: Decimal) -> str:
    """Classify total score into one of four recommendation categories."""
    if total_score >= THRESHOLD_HIGH_PRIORITY:
        return RECOMMENDATION_HIGH_PRIORITY
    elif total_score >= THRESHOLD_RECOMMENDED:
        return RECOMMENDATION_RECOMMENDED
    elif total_score >= THRESHOLD_CONSIDER:
        return RECOMMENDATION_CONSIDER
    else:
        return RECOMMENDATION_LOW_PRIORITY


def get_configuration_dict() -> Dict[str, Any]:
    """Return dictionary representation of all scoring rules and parameters."""
    return {
        "rubric_version": RUBRIC_VERSION,
        "academic_weight": str(ACADEMIC_WEIGHT),
        "financial_need_weight": str(FINANCIAL_NEED_WEIGHT),
        "achievement_weight": str(ACHIEVEMENT_WEIGHT),
        "min_academic_percentage": str(MIN_ACADEMIC_PERCENTAGE),
        "max_household_income": str(MAX_HOUSEHOLD_INCOME),
        "income_bands": [
            {"min": str(b[0]), "max": str(b[1]), "score": str(b[2])}
            for b in INCOME_BANDS
        ],
        "income_above_max_score": str(INCOME_ABOVE_MAX_SCORE),
        "max_achievement_score": str(MAX_ACHIEVEMENT_SCORE),
        "achievement_level_points": {k: str(v) for k, v in ACHIEVEMENT_LEVEL_POINTS.items()},
        "thresholds": {
            "high_priority": str(THRESHOLD_HIGH_PRIORITY),
            "recommended": str(THRESHOLD_RECOMMENDED),
            "consider": str(THRESHOLD_CONSIDER),
        },
        "prohibited_attributes": list(PROHIBITED_SCORING_ATTRIBUTES),
    }


def get_configuration_hash() -> str:
    """Generate SHA-256 hash of scoring configuration for tamper-proofing and audit logs."""
    config_data = get_configuration_dict()
    serialized = json.dumps(config_data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

