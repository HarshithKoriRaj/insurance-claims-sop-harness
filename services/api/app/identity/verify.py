"""Identity verification: the supplied, normalized evidence must match at least the
required number of distinct permitted fields on exactly one policyholder, with no
supplied field contradicting that record. Every record is evaluated; there is no
first-match shortcut."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from app.contracts.fixtures import Policyholder
from app.identity.fields import field_matches, record_values
from app.policies import IdentityField, VerificationPolicy

OutcomeKind = Literal["need_more", "verified", "ambiguous", "no_match"]


@dataclass(frozen=True)
class VerificationOutcome:
    kind: OutcomeKind
    party_id: str | None = None
    matched_fields: tuple[IdentityField, ...] = ()


def verify(
    evidence: Mapping[IdentityField, str],
    records: Iterable[Policyholder],
    verification: VerificationPolicy,
) -> VerificationOutcome:
    supplied = [field for field in verification.permitted_fields if field in evidence]
    if len(supplied) < verification.required_matching_fields:
        return VerificationOutcome("need_more")
    candidates: list[tuple[str, tuple[IdentityField, ...]]] = []
    for record in records:
        matched = tuple(field for field in supplied if field_matches(record, field, evidence[field]))
        # A supplied value the record holds but does not match is a contradiction. A field the
        # record has no value for (a national ID holder's SSN) is simply unusable, not a conflict.
        contradicted = any(
            field not in matched and record_values(record, field) for field in supplied
        )
        if len(matched) >= verification.required_matching_fields and not contradicted:
            candidates.append((record.party_id, matched))
    if len(candidates) == 1:
        party_id, matched = candidates[0]
        return VerificationOutcome("verified", party_id, matched)
    if len(candidates) > 1:
        return VerificationOutcome("ambiguous")
    return VerificationOutcome("no_match")
