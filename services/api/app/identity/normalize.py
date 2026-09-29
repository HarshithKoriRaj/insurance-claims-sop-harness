"""Deterministic normalization of caller-supplied identity values. Nothing here
guesses: unclear input comes back with a problem the conversation can ask about.
Input is NFKC-normalized (full-width characters become ASCII); numeric fields then
accept only ASCII digits, matching the stored values."""

from __future__ import annotations

import dataclasses
import re
import unicodedata
from datetime import date
from enum import StrEnum

from app.policies import IdentityField, Policy


class Problem(StrEnum):
    INVALID = "invalid"
    AMBIGUOUS = "ambiguous"
    INCOMPLETE = "incomplete"
    CONTROL_CHARACTERS = "control_characters"


@dataclasses.dataclass(frozen=True)
class Normalized:
    """A value or a problem, never both; only an ambiguous result has candidates.
    Values are personal data, so repr leaves them out."""

    value: str | None = dataclasses.field(repr=False)
    problem: Problem | None = None
    candidates: tuple[str, ...] = dataclasses.field(default=(), repr=False)

    def __post_init__(self) -> None:
        if (self.value is None) == (self.problem is None):
            raise ValueError("a normalized result holds exactly one of value and problem")
        if self.candidates and self.problem is not Problem.AMBIGUOUS:
            raise ValueError("only an ambiguous result has candidates")


def _problem(problem: Problem, candidates: tuple[str, ...] = ()) -> Normalized:
    return Normalized(None, problem, candidates)


_INVISIBLE_CATEGORIES = {"Cc", "Cf", "Co", "Cs"}
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}


def has_invisible_characters(text: str) -> bool:
    return any(
        unicodedata.category(ch) in _INVISIBLE_CATEGORIES and ch not in _ALLOWED_CONTROLS for ch in text
    )


_HONORIFICS = {"mr", "mrs", "ms", "miss", "mx", "dr"}


def _name_words(text: str) -> list[str]:
    # Letters and combining marks make up words; anything else separates them. Dropping
    # a mark (a Devanagari vowel sign, say) would make two different names equal.
    return "".join(ch if unicodedata.category(ch)[0] in "LM" else " " for ch in text).split()


def normalize_name(raw: str) -> Normalized:
    """Case, spacing, punctuation, and Unicode form are normalized; word order is not."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    words = _name_words(unicodedata.normalize("NFKC", raw).casefold())
    while words and words[0] in _HONORIFICS:
        words.pop(0)
    if len(words) < 2:
        return _problem(Problem.INCOMPLETE)
    return Normalized("".join(words))


_MONTH_NAMES = [
    ("january", "jan"),
    ("february", "feb"),
    ("march", "mar"),
    ("april", "apr"),
    ("may",),
    ("june", "jun"),
    ("july", "jul"),
    ("august", "aug"),
    ("september", "sep", "sept"),
    ("october", "oct"),
    ("november", "nov"),
    ("december", "dec"),
]
_MONTHS = {name: number for number, names in enumerate(_MONTH_NAMES, start=1) for name in names}
_ISO = re.compile(r"([0-9]{4})[-/.]([0-9]{1,2})[-/.]([0-9]{1,2})")
_NUMERIC = re.compile(r"([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{2}|[0-9]{4})")
_DATE_FILLER = {"st", "nd", "rd", "th", "of", "the"}


def _date_or_none(year: int, month: int, day: int) -> date | None:
    if not 1900 <= year <= 2100:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def normalize_dob(raw: str) -> Normalized:
    """Returns an ISO date, or a problem. Numeric dates where day and month could be
    swapped come back AMBIGUOUS with both readings; two-digit years are INCOMPLETE."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    text = unicodedata.normalize("NFKC", raw).strip().casefold()

    if match := _ISO.fullmatch(text):
        parsed = _date_or_none(*(int(part) for part in match.groups()))
        return Normalized(parsed.isoformat()) if parsed else _problem(Problem.INVALID)

    if match := _NUMERIC.fullmatch(text):
        first, second, year_text = match.groups()
        if len(year_text) == 2:
            return _problem(Problem.INCOMPLETE)
        year = int(year_text)
        readings = {
            reading
            for reading in (_date_or_none(year, int(first), int(second)), _date_or_none(year, int(second), int(first)))
            if reading is not None
        }
        if not readings:
            return _problem(Problem.INVALID)
        if len(readings) == 2:
            return _problem(Problem.AMBIGUOUS, tuple(sorted(r.isoformat() for r in readings)))
        return Normalized(readings.pop().isoformat())

    tokens = [t for t in re.findall(r"[a-z]+|[0-9]+", text) if t not in _DATE_FILLER]
    months = [t for t in tokens if t in _MONTHS]
    numbers = [t for t in tokens if t.isdigit()]
    if len(tokens) != 3 or len(months) != 1 or len(numbers) != 2:
        return _problem(Problem.INVALID)
    years = [n for n in numbers if len(n) == 4]
    days = [n for n in numbers if len(n) <= 2]
    if not years:
        return _problem(Problem.INCOMPLETE)
    if len(years) != 1 or len(days) != 1:
        return _problem(Problem.INVALID)
    parsed = _date_or_none(int(years[0]), _MONTHS[months[0]], int(days[0]))
    return Normalized(parsed.isoformat()) if parsed else _problem(Problem.INVALID)


_PHONE_CHARACTERS = re.compile(r"[0-9\s()+.\-]+")
_E164_DIGITS = re.compile(r"[1-9][0-9]{7,14}")


def normalize_phone(raw: str, *, default_country_code: str, national_length: int) -> Normalized:
    """Returns E.164. The default country code applies only to national-length numbers;
    anything else without an explicit country code is not guessed."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    text = unicodedata.normalize("NFKC", raw).strip()
    if not _PHONE_CHARACTERS.fullmatch(text) or "+" in text[1:]:
        return _problem(Problem.INVALID)
    digits = re.sub(r"[^0-9]", "", text)
    if text.startswith("+"):
        return Normalized(f"+{digits}") if _E164_DIGITS.fullmatch(digits) else _problem(Problem.INVALID)
    if len(digits) == national_length:
        return Normalized(f"+{default_country_code}{digits}")
    if len(digits) == len(default_country_code) + national_length and digits.startswith(default_country_code):
        return Normalized(f"+{digits}")
    if len(digits) < national_length:
        return _problem(Problem.INCOMPLETE)
    return _problem(Problem.AMBIGUOUS)


def normalize_email(raw: str) -> Normalized:
    """NFKC-normalizes, trims, and case-folds. Dots and plus tags in the local part are
    kept as given."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    text = unicodedata.normalize("NFKC", raw).strip()
    local, separator, domain = text.partition("@")
    if (
        not separator
        or not local
        or "@" in domain
        or "." not in domain.strip(".")
        or any(ch.isspace() for ch in text)
    ):
        return _problem(Problem.INVALID)
    return Normalized(f"{local.casefold()}@{domain.casefold()}")


def normalize_ssn_last4(raw: str) -> Normalized:
    """Exactly four digits, leading zeros kept. A full SSN is refused, not trimmed."""
    if has_invisible_characters(raw):
        return _problem(Problem.CONTROL_CHARACTERS)
    digits = re.sub(r"[\s\-]", "", unicodedata.normalize("NFKC", raw).strip())
    if re.fullmatch(r"[0-9]{4}", digits):
        return Normalized(digits)
    if re.fullmatch(r"[0-9]{1,3}", digits):
        return _problem(Problem.INCOMPLETE)
    return _problem(Problem.INVALID)


def normalize(field: IdentityField, raw: str, policy: Policy) -> Normalized:
    match field:
        case "full_name":
            return normalize_name(raw)
        case "dob":
            return normalize_dob(raw)
        case "phone":
            return normalize_phone(
                raw,
                default_country_code=policy.phone.default_country_calling_code,
                national_length=policy.phone.national_number_length,
            )
        case "email":
            return normalize_email(raw)
        case "ssn_last4":
            return normalize_ssn_last4(raw)
    raise ValueError(f"unknown identity field {field!r}")
