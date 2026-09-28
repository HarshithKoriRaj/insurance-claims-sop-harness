from datetime import date

import pytest
from pydantic import ValidationError

from app.policies import load_policy


def _write_variant(policies_dir, tmp_path, old, new):
    text = (policies_dir / "defaults.toml").read_text()
    assert old in text, f"test setup: {old!r} not found in defaults.toml"
    path = tmp_path / "defaults.toml"
    path.write_text(text.replace(old, new))
    return path


def test_defaults_match_the_architecture_plan(policies_dir):
    policy = load_policy(policies_dir / "defaults.toml")
    assert policy.version == "2026-09-28"
    assert policy.verification.required_matching_fields == 3
    assert policy.verification.max_failed_submissions == 3
    assert policy.verification.idle_expiry_minutes == 30
    assert policy.verification.permitted_fields == ("full_name", "dob", "phone", "email", "ssn_last4")
    assert policy.session.max_age_hours == 8
    assert policy.session.max_input_characters == 8000
    assert policy.session.recent_turns == 12
    assert policy.session.max_turns == 60
    assert policy.recovery.unrelated_offer_human_at == 2
    assert policy.recovery.unrelated_stop_at == 3
    assert policy.recovery.refusal_stop_at == 2
    assert policy.claims.fact_max_age_minutes == 5
    assert policy.phone.default_country_calling_code == "1"
    assert policy.phone.national_number_length == 10
    assert policy.business.timezone == "America/Los_Angeles"
    assert policy.demo.business_date == date(2026, 3, 1)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("fact_max_age_minutes = 5", "fact_max_age_minutes = 5\n\n[surprise]\nkey = 1"),
        ("max_failed_submissions = 3", "max_failed_submissions = 3\nsurprise = 1"),
    ],
    ids=["top-level-table", "nested-key"],
)
def test_unknown_keys_are_rejected(policies_dir, tmp_path, old, new):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_policy(_write_variant(policies_dir, tmp_path, old, new))


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("required_matching_fields = 3", "required_matching_fields = 2", "greater than or equal to 3"),
        ("required_matching_fields = 3", "required_matching_fields = true", "greater than or equal to 3"),
        ("required_matching_fields = 3", "required_matching_fields = 6", "exceeds the number of permitted fields"),
        (
            'permitted_fields = ["full_name", "dob", "phone", "email", "ssn_last4"]',
            'permitted_fields = ["dob", "dob", "dob"]',
            "must not repeat",
        ),
        ('"ssn_last4"]', '"ssn_last4", "national_id_last4"]', "permitted_fields"),
        ("unrelated_offer_human_at = 2", "unrelated_offer_human_at = 3", "must come before"),
        ("recent_turns = 12", "recent_turns = 61", "cannot exceed max_turns"),
        (
            'default_country_calling_code = "1"\nnational_number_length = 10',
            'default_country_calling_code = "999"\nnational_number_length = 14',
            "exceeds 15 digits",
        ),
        ('timezone = "America/Los_Angeles"', 'timezone = "america/los_angeles"', "unknown IANA time zone"),
        ('version = "2026-09-28"', 'version = ""', "at least 1 character"),
    ],
    ids=[
        "below-three-fields",
        "boolean-threshold",
        "more-fields-than-permitted",
        "repeated-field",
        "national-id-field",
        "offer-after-stop",
        "recent-exceeds-max-turns",
        "phone-longer-than-e164",
        "timezone-wrong-case",
        "empty-version",
    ],
)
def test_unsafe_or_incoherent_settings_are_rejected(policies_dir, tmp_path, old, new, message):
    with pytest.raises(ValidationError, match=message):
        load_policy(_write_variant(policies_dir, tmp_path, old, new))
