"""Loads the supplied fixtures read-only, validates each file, and checks the
references between files. Nothing here writes to the fixture directory, and no
error message carries a record's personal data."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.claims.documents import DocumentCatalog, UnknownDocumentLabel
from app.contracts.fixtures import (
    Claim,
    ClaimSchemaDoc,
    ConsentScenario,
    DocumentGuideline,
    Policyholder,
    Representative,
)


class FixtureError(ValueError):
    pass


@dataclass(frozen=True)
class FixtureStore:
    policyholders: tuple[Policyholder, ...]
    claims: tuple[Claim, ...]
    claim_schema: ClaimSchemaDoc
    consent_scenarios: Mapping[str, ConsentScenario]
    representatives: tuple[Representative, ...]
    guideline: DocumentGuideline
    claim_versions: Mapping[str, str]

    def policyholder(self, party_id: str) -> Policyholder | None:
        return next((p for p in self.policyholders if p.party_id == party_id), None)

    def claim(self, case_id: str) -> Claim | None:
        return next((c for c in self.claims if c.case_id == case_id), None)

    def claims_for_party(self, party_id: str) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.party_id == party_id)


_FILES: dict[str, TypeAdapter[Any]] = {
    "policyholders.json": TypeAdapter(tuple[Policyholder, ...]),
    "claims.json": TypeAdapter(tuple[Claim, ...]),
    "claim_schema.json": TypeAdapter(ClaimSchemaDoc),
    "consent_scenarios.json": TypeAdapter(dict[str, ConsentScenario]),
    "representatives.json": TypeAdapter(tuple[Representative, ...]),
    "required_document_guideline.json": TypeAdapter(DocumentGuideline),
}


def load_fixtures(directory: Path, catalog: DocumentCatalog) -> FixtureStore:
    raw: dict[str, Any] = {}
    parsed: dict[str, Any] = {}
    for name, adapter in _FILES.items():
        try:
            text = (directory / name).read_text(encoding="utf-8")
            raw[name] = json.loads(text, object_pairs_hook=_reject_repeated_keys)
        except (OSError, ValueError) as exc:
            # from None: JSONDecodeError.doc and UnicodeDecodeError.object hold the whole file.
            raise FixtureError(f"{name}: {exc}") from None
        try:
            parsed[name] = adapter.validate_python(raw[name])
        except ValidationError as exc:
            # Report where and why, never the rejected values: fixtures hold personal data.
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_input=False, include_url=False)
            )
            raise FixtureError(f"{name}: {details}") from None

    store = FixtureStore(
        policyholders=parsed["policyholders.json"],
        claims=parsed["claims.json"],
        claim_schema=parsed["claim_schema.json"],
        consent_scenarios=MappingProxyType(parsed["consent_scenarios.json"]),
        representatives=parsed["representatives.json"],
        guideline=parsed["required_document_guideline.json"],
        claim_versions=MappingProxyType(
            {record["case_id"]: _content_hash(record) for record in raw["claims.json"]}
        ),
    )
    _check_references(store, catalog)
    return store


def _reject_repeated_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        raise ValueError(f"repeated key in one JSON object: {', '.join(repeated)}")
    return dict(pairs)


def _content_hash(record: Any) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_references(store: FixtureStore, catalog: DocumentCatalog) -> None:
    party_ids = [p.party_id for p in store.policyholders]
    _require_unique("party_id", party_ids)
    _require_unique_policy_numbers(store.policyholders)
    _require_unique("case_id", [c.case_id for c in store.claims])

    for claim in store.claims:
        if claim.party_id not in party_ids:
            raise FixtureError(f"claims.json: {claim.case_id} belongs to unknown party {claim.party_id}")
        for label in claim.documents_needed:
            _require_code(catalog, label, f"claims.json: {claim.case_id}")

    for index, rep in enumerate(store.representatives):
        holder = store.policyholder(rep.buyer_party_id)
        if holder is None or holder.name != rep.buyer_name:
            raise FixtureError(
                f"representatives.json: [{index}] buyer does not match a policyholder ({rep.buyer_party_id})"
            )

    guideline = store.guideline
    _require_unique("follow-up topic", [rule.topic for rule in guideline.claim_followup_guidance])
    for key in guideline.document_guidance:
        _require_code(catalog, key, "required_document_guideline.json: document_guidance")
    for key in guideline.document_alternative_guidance:
        if key != "default":
            _require_code(catalog, key, "required_document_guideline.json: document_alternative_guidance")
    if "default" not in guideline.document_alternative_guidance:
        raise FixtureError("required_document_guideline.json: document_alternative_guidance has no default")


def _require_unique(field: str, values: list[str]) -> None:
    """For values that are not personal data: IDs and topics."""
    duplicates = sorted({v for v in values if values.count(v) > 1})
    if duplicates:
        raise FixtureError(f"duplicate {field}: {', '.join(duplicates)}")


def _require_unique_policy_numbers(holders: tuple[Policyholder, ...]) -> None:
    # A policy number identifies a customer, so name the pseudonymous party IDs instead.
    parties_by_number: dict[str, list[str]] = {}
    for holder in holders:
        parties_by_number.setdefault(holder.policy_number, []).append(holder.party_id)
    shared = sorted(sorted(ids) for ids in parties_by_number.values() if len(ids) > 1)
    if shared:
        groups = "; ".join(", ".join(ids) for ids in shared)
        raise FixtureError(f"policyholders.json: parties share a policy number: {groups}")


def _require_code(catalog: DocumentCatalog, label: str, where: str) -> None:
    try:
        catalog.code_for(label)
    except UnknownDocumentLabel:
        raise FixtureError(f"{where}: document label {label!r} has no document code") from None
