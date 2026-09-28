from datetime import date

import pytest
from pydantic import ValidationError

from app.policies import load_policy


def test_defaults_match_the_architecture_plan(policies_dir):
    policy = load_policy(policies_dir / "defaults.toml")
    assert policy.verification.required_matching_fields == 3
    assert policy.verification.max_failed_submissions == 3
    assert policy.verification.idle_expiry_minutes == 30
    assert policy.verification.permitted_fields == ("full_name", "dob", "phone", "email", "ssn_last4")
    assert policy.session.max_age_hours == 8
    assert policy.session.max_input_characters == 8000
    assert policy.recovery.unrelated_offer_human_at == 2
    assert policy.recovery.unrelated_stop_at == 3
    assert policy.recovery.refusals_before_stop == 2
    assert policy.claims.fact_max_age_minutes == 5
    assert policy.demo.business_date == date(2026, 3, 1)


def test_unknown_keys_are_rejected(policies_dir, tmp_path):
    path = tmp_path / "defaults.toml"
    path.write_text((policies_dir / "defaults.toml").read_text() + "\n[surprise]\nkey = 1\n")
    with pytest.raises(ValidationError):
        load_policy(path)


def test_national_id_cannot_be_added_as_a_permitted_field(policies_dir, tmp_path):
    path = tmp_path / "defaults.toml"
    text = (policies_dir / "defaults.toml").read_text()
    path.write_text(text.replace('"ssn_last4"]', '"ssn_last4", "national_id_last4"]'))
    with pytest.raises(ValidationError):
        load_policy(path)
