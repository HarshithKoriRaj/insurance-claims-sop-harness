"""Maps document labels from claims and guidance onto shared document codes."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class UnknownDocumentLabel(KeyError):
    pass


def normalize_label(label: str) -> str:
    return " ".join(label.casefold().split())


@dataclass(frozen=True)
class DocumentCatalog:
    version: str
    label_to_code: Mapping[str, str]

    def code_for(self, label: str) -> str:
        try:
            return self.label_to_code[normalize_label(label)]
        except KeyError:
            raise UnknownDocumentLabel(label) from None


def load_document_catalog(path: Path) -> DocumentCatalog:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    label_to_code: dict[str, str] = {}
    for code, entry in data["codes"].items():
        for label in entry["labels"]:
            key = normalize_label(label)
            if key in label_to_code:
                raise ValueError(f"document label {label!r} maps to both {label_to_code[key]} and {code}")
            label_to_code[key] = code
    return DocumentCatalog(version=data["version"], label_to_code=label_to_code)
