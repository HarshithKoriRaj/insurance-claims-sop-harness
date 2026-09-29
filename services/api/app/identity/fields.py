"""Which normalized values a policyholder record holds for each permitted field.
Aliases count as the same field, and a national ID never answers for an SSN. A
stored value that cannot be normalized is a data error and raises; it is never
silently dropped."""

from __future__ import annotations

from app.contracts.fixtures import Policyholder
from app.identity.normalize import Normalized, normalize_email, normalize_name
from app.policies import IdentityField


class UnusableRecordValue(ValueError):
    pass


def _usable(result: Normalized, record: Policyholder, field: IdentityField) -> str:
    if result.value is None:
        raise UnusableRecordValue(
            f"{record.party_id}: a stored {field} cannot be normalized ({result.problem})"
        )
    return result.value


def record_values(record: Policyholder, field: IdentityField) -> frozenset[str]:
    match field:
        case "full_name":
            names = (record.name, *record.name_aliases)
            return frozenset(_usable(normalize_name(name), record, field) for name in names)
        case "dob":
            return frozenset({record.dob.isoformat()})
        case "phone":
            return frozenset((record.phone, *record.phone_aliases))
        case "email":
            emails = (record.email, *record.email_aliases)
            return frozenset(_usable(normalize_email(email), record, field) for email in emails)
        case "ssn_last4":
            return frozenset({record.id_last4}) if record.id_type == "ssn_last4" else frozenset()
    raise ValueError(f"unknown identity field {field!r}")


def field_matches(record: Policyholder, field: IdentityField, normalized_value: str) -> bool:
    return normalized_value in record_values(record, field)
