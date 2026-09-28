"""Maps document labels from claims and guidance onto shared document codes."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]


class UnknownDocumentLabel(KeyError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _CodeEntry(_Strict):
    labels: tuple[Label, ...] = Field(min_length=1)


class _CatalogFile(_Strict):
    version: str = Field(min_length=1)
    codes: dict[Code, _CodeEntry] = Field(min_length=1)


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
        parsed = _CatalogFile.model_validate(tomllib.load(handle))
    label_to_code: dict[str, str] = {}
    for code, entry in parsed.codes.items():
        for label in entry.labels:
            key = normalize_label(label)
            if key in label_to_code:
                raise ValueError(f"document label {label!r} maps to both {label_to_code[key]} and {code}")
            label_to_code[key] = code
    return DocumentCatalog(version=parsed.version, label_to_code=MappingProxyType(label_to_code))
