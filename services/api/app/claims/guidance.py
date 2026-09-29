"""Approved guidance snippets with provenance, and rendering of the follow-up
templates. A template renders only when every placeholder has a value."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import quote

from app.claims.documents import DocumentCatalog
from app.contracts.fixtures import Claim, DocumentGuideline, FollowupRule

SOURCE = "required_document_guideline.json"
_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")


class UnknownTopic(KeyError):
    pass


class GuidanceRenderError(ValueError):
    pass


@dataclass(frozen=True)
class GuidanceSnippet:
    topic: str
    text: str
    source: str


def natural_list(items: Sequence[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def render_template(template: str, values: Mapping[str, str]) -> str:
    remainder = _PLACEHOLDER.sub("", template)
    if "{" in remainder or "}" in remainder:
        raise GuidanceRenderError("template has an unmatched brace")

    def fill(match: re.Match[str]) -> str:
        value = values.get(match.group(1))
        if value is None or not value.strip():
            raise GuidanceRenderError(f"no value for placeholder {match.group(0)}")
        return value

    return _PLACEHOLDER.sub(fill, template)


class GuidanceLibrary:
    def __init__(self, guideline: DocumentGuideline, catalog: DocumentCatalog) -> None:
        self._guideline = guideline
        self._catalog = catalog
        self._document_keys = _keys_by_code(guideline.document_guidance, catalog)
        self._alternative_keys = _keys_by_code(
            {k: v for k, v in guideline.document_alternative_guidance.items() if k != "default"}, catalog
        )
        self._rules: dict[str, tuple[int, FollowupRule]] = {
            rule.topic: (index, rule) for index, rule in enumerate(guideline.claim_followup_guidance)
        }

    @property
    def topics(self) -> tuple[str, ...]:
        return tuple(self._rules)

    def topic_examples(self, topic: str) -> tuple[str, ...]:
        return self._rule(topic)[1].match_any

    def for_documents(self, case_type: str, labels: Sequence[str]) -> tuple[GuidanceSnippet, ...]:
        guideline = self._guideline
        snippets = [GuidanceSnippet("default", guideline.default_guidance.en, _source("default_guidance", "en"))]
        if case_type in guideline.case_type_guidance:
            snippets.append(
                GuidanceSnippet(
                    f"case_type:{case_type}",
                    guideline.case_type_guidance[case_type].en,
                    _source("case_type_guidance", case_type, "en"),
                )
            )
        seen: set[str] = set()
        for label in labels:
            code = self._catalog.code_for(label)
            key = self._document_keys.get(code)
            # Two labels for one document (an alias and its canonical name) give one snippet.
            if key is not None and code not in seen:
                seen.add(code)
                snippets.append(
                    GuidanceSnippet(
                        f"document:{code}",
                        guideline.document_guidance[key].en,
                        _source("document_guidance", key, "en"),
                    )
                )
        return tuple(snippets)

    def alternatives(self, label: str) -> GuidanceSnippet:
        code = self._catalog.code_for(label)
        key = self._alternative_keys.get(code)
        if key is None:
            return GuidanceSnippet(
                "alternative:default",
                self._guideline.document_alternative_guidance["default"].en,
                _source("document_alternative_guidance", "default", "en"),
            )
        return GuidanceSnippet(
            f"alternative:{code}",
            self._guideline.document_alternative_guidance[key].en,
            _source("document_alternative_guidance", key, "en"),
        )

    def human_review_rule(self) -> GuidanceSnippet:
        settings = self._guideline.claim_followup_settings
        return GuidanceSnippet(
            "human_review",
            settings.human_review_after_document_alternatives_exhausted.en,
            _source("claim_followup_settings", "human_review_after_document_alternatives_exhausted", "en"),
        )

    def fallback(self) -> GuidanceSnippet:
        return GuidanceSnippet(
            "fallback", self._guideline.claim_followup_fallback.en, _source("claim_followup_fallback", "en")
        )

    def followup(self, claim: Claim, topic: str) -> GuidanceSnippet:
        index, rule = self._rule(topic)
        if rule.requires_documents and not claim.documents_needed:
            return self.fallback()
        settings = self._guideline.claim_followup_settings
        values = {
            "case_id": claim.case_id,
            "documents": natural_list(claim.documents_needed),
            "average_processing_time_after_submission": settings.average_processing_time_after_submission.en,
        }
        return GuidanceSnippet(
            f"followup:{topic}",
            render_template(rule.en, values),
            _source("claim_followup_guidance", index, "en"),
        )

    def _rule(self, topic: str) -> tuple[int, FollowupRule]:
        try:
            return self._rules[topic]
        except KeyError:
            raise UnknownTopic(topic) from None


def _source(*path: str | int) -> str:
    """The file plus an RFC 6901 JSON Pointer in URI-fragment form, so a key with a
    space, "/", or "~" still points at exactly one entry."""
    tokens = (quote(str(part).replace("~", "~0").replace("/", "~1"), safe="") for part in path)
    return f"{SOURCE}#/" + "/".join(tokens)


def _keys_by_code(entries: Mapping[str, object], catalog: DocumentCatalog) -> dict[str, str]:
    keys: dict[str, str] = {}
    for key in entries:
        code = catalog.code_for(key)
        if code in keys:
            raise ValueError(f"guidance keys {keys[code]!r} and {key!r} share document code {code}")
        keys[code] = key
    return keys
