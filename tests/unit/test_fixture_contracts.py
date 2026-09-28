import json
from datetime import date
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


@pytest.mark.parametrize("bad", [1450.0, "1450", "1,450.00", "abc", "-1.00"])
def test_money_must_be_a_two_place_decimal_string(bad):
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "net_pay": bad})


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError):
        Claim.model_validate({**VALID_CLAIM, "surprise": True})


def test_id_last4_keeps_leading_zeros():
    assert Policyholder.model_validate(VALID_HOLDER).id_last4 == "0042"


def test_id_last4_must_be_a_four_digit_string():
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, "id_last4": 42})


@pytest.mark.parametrize(("field", "value"), [("email", "not-an-email"), ("email_aliases", ["a@b"])])
def test_emails_on_file_must_be_addresses(field, value):
    with pytest.raises(ValidationError):
        Policyholder.model_validate({**VALID_HOLDER, field: value})
