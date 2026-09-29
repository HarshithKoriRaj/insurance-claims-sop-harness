import pytest

from app.identity.verify import verify


def _evidence(**fields):
    return fields


def test_three_matching_fields_verify_exactly_one_policyholder(store, policy):
    outcome = verify(_evidence(full_name="margaretchen", dob="1985-03-15", ssn_last4="4472"), store.policyholders, policy.verification)
    assert (outcome.kind, outcome.party_id) == ("verified", "P9")
    assert set(outcome.matched_fields) == {"full_name", "dob", "ssn_last4"}


def test_two_fields_are_not_enough(store, policy):
    outcome = verify(_evidence(full_name="margaretchen", dob="1985-03-15"), store.policyholders, policy.verification)
    assert outcome.kind == "need_more"


def test_a_contradicting_fourth_field_blocks_verification(store, policy):
    evidence = _evidence(full_name="margaretchen", dob="1985-03-15", ssn_last4="4472", phone="+16505212830")
    assert verify(evidence, store.policyholders, policy.verification).kind == "no_match"


def test_aliases_count_for_the_same_record(store, policy):
    evidence = _evidence(full_name="yavenli", dob="1989-12-03", email="yawen.li@example.com")
    outcome = verify(evidence, store.policyholders, policy.verification)
    assert (outcome.kind, outcome.party_id) == ("verified", "P13")


def test_a_national_id_never_counts_as_an_ssn(store, policy):
    evidence = _evidence(full_name="matian", dob="1964-09-10", ssn_last4="6688")
    assert verify(evidence, store.policyholders, policy.verification).kind == "no_match"


def test_two_equally_matching_records_are_ambiguous_not_first_wins(store, policy):
    twin = store.policyholder("P9").model_copy(update={"party_id": "P99", "policy_number": "POL-0000"})
    evidence = _evidence(full_name="margaretchen", dob="1985-03-15", ssn_last4="4472")
    assert verify(evidence, (*store.policyholders, twin), policy.verification).kind == "ambiguous"


@pytest.mark.parametrize("party_id", ["P9", "P7", "P12", "P13"])
def test_every_policyholder_can_verify_with_name_dob_and_phone(store, policy, party_id):
    holder = store.policyholder(party_id)
    from app.identity.normalize import normalize_name

    evidence = _evidence(full_name=normalize_name(holder.name).value, dob=holder.dob.isoformat(), phone=holder.phone)
    assert verify(evidence, store.policyholders, policy.verification).party_id == party_id
