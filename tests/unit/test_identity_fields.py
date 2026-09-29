from datetime import date

import pytest

from app.identity.fields import UnusableRecordValue, field_matches, record_values
from app.identity.normalize import Normalized, normalize, normalize_email, normalize_name


def test_ssn_last4_matches_an_ssn_record(store):
    assert field_matches(store.policyholder("P9"), "ssn_last4", "4472")


@pytest.mark.parametrize(("party_id", "digits"), [("P12", "6688"), ("P13", "5317")])
def test_national_id_never_counts_as_ssn(store, party_id, digits):
    holder = store.policyholder(party_id)
    assert record_values(holder, "ssn_last4") == frozenset()
    assert not field_matches(holder, "ssn_last4", digits)


def test_name_aliases_and_spacing_variants_match(store):
    holder = store.policyholder("P13")
    assert field_matches(holder, "full_name", normalize_name("Yaven Li").value)
    assert field_matches(holder, "full_name", normalize_name("Yawen Li").value)


def test_reversed_name_order_does_not_match(store):
    holder = store.policyholder("P12")
    assert field_matches(holder, "full_name", normalize_name("Ma Tian").value)
    assert not field_matches(holder, "full_name", normalize_name("Tian Ma").value)


def test_duplicate_phone_alias_is_one_value(store):
    assert record_values(store.policyholder("P13"), "phone") == frozenset({"+16505212830"})


def test_email_alias_matches(store):
    assert field_matches(store.policyholder("P13"), "email", normalize_email("yawen.li@example.com").value)


def test_phone_one_digit_off_does_not_match(store):
    holder = store.policyholder("P9")
    assert field_matches(holder, "phone", "+16505212836")
    assert not field_matches(holder, "phone", "+16505212830")


def test_dob_matches_the_iso_value(store):
    assert field_matches(store.policyholder("P9"), "dob", "1985-03-15")


def test_every_stored_identity_value_is_usable(store):
    for holder in store.policyholders:
        for field in ("full_name", "dob", "phone", "email"):
            assert record_values(holder, field), (holder.party_id, field)


def test_stored_phones_are_already_what_a_caller_normalizes_to(store, policy):
    for holder in store.policyholders:
        for phone in record_values(holder, "phone"):
            assert normalize("phone", phone, policy) == Normalized(phone), holder.party_id


@pytest.mark.parametrize(
    ("field", "update", "secret"),
    [
        ("full_name", {"name_aliases": ("Margaret",)}, "margaret"),
        ("email", {"email_aliases": ("margaret.chen",)}, "margaret"),
        ("dob", {"dob": date(1899, 12, 31)}, "1899"),
    ],
    ids=["name", "email", "dob"],
)
def test_an_unusable_stored_value_raises_without_echoing_it(store, field, update, secret):
    holder = store.policyholder("P9").model_copy(update=update)
    with pytest.raises(UnusableRecordValue, match=f"P9: a stored {field} cannot be normalized") as caught:
        record_values(holder, field)
    assert secret not in str(caught.value).casefold()


def test_an_unknown_field_is_refused(store):
    with pytest.raises(ValueError, match="unknown identity field 'policy_number'"):
        record_values(store.policyholder("P9"), "policy_number")
