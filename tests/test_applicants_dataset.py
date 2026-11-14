"""Unit tests for the 17 fictional mock applicants dataset."""

import json
import os
import pytest
from core.schemas import ApplicantProfile


@pytest.fixture
def applicants_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", "applicants.json")
    assert os.path.exists(json_path), f"Applicants dataset not found at: {json_path}"
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_applicants_dataset_count_and_validation(applicants_data):
    # Assignment requires at least 15 fictional applicants
    assert len(applicants_data) >= 15

    validated_profiles = []
    for item in applicants_data:
        profile = ApplicantProfile.model_validate(item)
        validated_profiles.append(profile)

    assert len(validated_profiles) == len(applicants_data)


def test_applicants_dataset_coverage(applicants_data):
    profiles = [ApplicantProfile.model_validate(item) for item in applicants_data]

    # Check for incomplete / missing data cases
    missing_pct = [p for p in profiles if p.academic_percentage is None]
    assert len(missing_pct) >= 1

    missing_inc = [p for p in profiles if p.household_income is None]
    assert len(missing_inc) >= 1

    # Check for ineligible candidates (< 60% academic)
    ineligible_acad = [p for p in profiles if p.academic_percentage is not None and p.academic_percentage < 60.0]
    assert len(ineligible_acad) >= 1

    # Check for ineligible candidates (> 600k income)
    ineligible_inc = [p for p in profiles if p.household_income is not None and p.household_income > 600000.0]
    assert len(ineligible_inc) >= 1

    # Check for high performers (> 85% academic and <= 150k income)
    high_perf = [
        p for p in profiles
        if p.academic_percentage is not None and p.academic_percentage >= 85.0
        and p.household_income is not None and p.household_income <= 150000.0
    ]
    assert len(high_perf) >= 2

