import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts.fixtures import (
    Claim,
    ClaimSchemaDoc,
    ConsentScenario,
    DocumentGuideline,
    Policyholder,
    Representative,
)

VALID_CLAIM = {
    "case_id": "CL-1",
    "party_id": "P1",
    "case_type": "healthcare",
    "created_at": "2026-01-01",
    "status": "open",
    "summary": "test",
    "expected_reimbursement_amount": "1.00",
    "allowed_max_amount": "1.00",
    "net_pay": "0.00",
    "net_fee": "1.00",
}

VALID_HOLDER = {
    "party_id": "P1",
    "name": "Test Person",
    "policy_number": "POL-1",
    "dob": "1990-01-01",
    "id_type": "ssn_last4",
    "id_last4": "0042",
    "phone": "+16500000000",
    "email": "test@example.com",
}


def _read(fixtures_dir, name):
    return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))


def test_policyholders_validate(fixtures_dir):
    holders = TypeAdapter(tuple[Policyholder, ...]).validate_python(_read(fixtures_dir, "policyholders.json"))
    assert [h.party_id for h in holders] == ["P9", "P7", "P12", "P13"]
    assert holders[0].dob == date(1985, 3, 15)
    assert (holders[0].id_type, holders[0].id_last4) == ("ssn_last4", "4472")
    assert holders[2].id_type == "national_id_last4"
    assert holders[3].name_aliases == ("Yaven Li",)


def test_claims_validate_with_decimal_money_and_real_dates(fixtures_dir):
    claims = TypeAdapter(tuple[Claim, ...]).validate_python(_read(fixtures_dir, "claims.json"))
    denied = next(c for c in claims if c.case_id == "CL-2048")
    assert denied.allowed_max_amount == Decimal("1450.00")
    assert isinstance(denied.net_pay, Decimal)
    assert denied.appeal_deadline == date(2026, 3, 18)
    assert denied.documents_needed == ("pathology report", "office note")


def test_remaining_fixture_files_validate(fixtures_dir):
    ClaimSchemaDoc.model_validate(_read(fixtures_dir, "claim_schema.json"))
    TypeAdapter(dict[str, ConsentScenario]).validate_python(_read(fixtures_dir, "consent_scenarios.json"))
    TypeAdapter(tuple[Representative, ...]).validate_python(_read(fixtures_dir, "representatives.json"))
    DocumentGuideline.model_validate(_read(fixtures_dir, "required_document_guideline.json"))


@pytest.mark.parametrize(
    "bad",
    [
        1450.0,
        "1450",
        "1,450.00",
        "abc",
        "-1.00",
        "١٤٥٠.٠٠",
        Decimal("1450.5"),
        Decimal("-1.00"),
        Decimal("-0.00"),
        Decimal("NaN"),
    ],
)
def test_money_must_be_a_two_place_decimal_string(bad):
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "net_pay": bad})


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "surprise": True})


def test_unknown_keys_are_rejected_in_nested_models(fixtures_dir):
    guideline = _read(fixtures_dir, "required_document_guideline.json")
    guideline["claim_followup_settings"]["surprise"] = {"en": "x"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DocumentGuideline.model_validate(guideline)


def test_id_last4_keeps_leading_zeros():
    assert Policyholder.model_validate(VALID_HOLDER).id_last4 == "0042"


def test_id_last4_must_be_a_four_digit_string():
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, "id_last4": 4472})


@pytest.mark.parametrize(("field", "value"), [("email", "not-an-email"), ("email_aliases", ["a@b"])])
def test_emails_on_file_must_be_addresses(field, value):
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, field: value})


@pytest.mark.parametrize(
    "bad", ["1773792000", 0, "1985-03-15T00:00:00", "03/15/1985", "٢٠٢٦-٠٣-١٨", "20260318", datetime(2026, 3, 18)]
)
def test_dates_must_be_iso_strings(bad):
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "created_at": bad})


@pytest.mark.parametrize(("field", "value"), [("id_last4", "٠٠٤٢"), ("phone", "+１６５００００００００")])
def test_only_ascii_digits_are_accepted(field, value):
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, field: value})


def test_models_round_trip_through_python_values(fixtures_dir):
    claims = TypeAdapter(tuple[Claim, ...]).validate_python(_read(fixtures_dir, "claims.json"))
    holders = TypeAdapter(tuple[Policyholder, ...]).validate_python(_read(fixtures_dir, "policyholders.json"))
    for record in (*claims, *holders):
        assert type(record).model_validate(record.model_dump()) == record


def test_a_denied_claim_without_a_reason_still_loads():
    claim = Claim.model_validate({**VALID_CLAIM, "status": "denied"})
    assert (claim.denial_reason, claim.appeal_deadline, claim.documents_needed) == (None, None, ())


def test_requires_documents_must_be_a_real_boolean(fixtures_dir):
    guideline = _read(fixtures_dir, "required_document_guideline.json")
    guideline["claim_followup_guidance"][0]["requires_documents"] = "no"
    with pytest.raises(ValidationError):
        DocumentGuideline.model_validate(guideline)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (Policyholder, {**VALID_HOLDER, "id_type": "passport_last4"}),
        (Policyholder, {**VALID_HOLDER, "party_id": ""}),
        (ConsentScenario, {"status_sequence": []}),
        (Claim, {**VALID_CLAIM, "status": "denied", "denial_reason": ""}),
    ],
    ids=["unknown-id-type", "empty-party-id", "empty-consent-sequence", "empty-denial-reason"],
)
def test_other_invalid_records_are_rejected(model, data):
    with pytest.raises(ValidationError):
        model.model_validate(data)
