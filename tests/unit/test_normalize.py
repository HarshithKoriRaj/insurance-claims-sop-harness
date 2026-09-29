import pytest

from app.identity.normalize import (
    Normalized,
    Problem,
    normalize,
    normalize_dob,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_ssn_last4,
)


def _us_phone(raw):
    return normalize_phone(raw, default_country_code="1", national_length=10)


@pytest.mark.parametrize(
    "raw", ["Margaret Chen", "  MARGARET   chen ", "Mrs. Margaret Chen", "margaret-chen", "Ｍａｒｇａｒｅｔ Ｃｈｅｎ"]
)
def test_name_variants_normalize_to_one_value(raw):
    assert normalize_name(raw) == Normalized("margaretchen")


def test_spacing_inside_a_name_does_not_matter():
    assert normalize_name("Yawen Li").value == normalize_name("Ya-Wen Li").value == "yawenli"


def test_name_word_order_is_not_normalized():
    assert normalize_name("Tian Ma").value != normalize_name("Ma Tian").value


def test_first_name_alone_is_incomplete():
    assert normalize_name("Margaret").problem is Problem.INCOMPLETE
    assert normalize_name("Mrs Chen").problem is Problem.INCOMPLETE


def test_combining_marks_stay_in_the_name():
    # Kiran Kumar and Karan Kumar differ only by a vowel sign, which is a combining mark.
    assert normalize_name("किरण कुमार").value != normalize_name("करण कुमार").value
    assert normalize_name("किरण").problem is Problem.INCOMPLETE


def test_invisible_characters_are_rejected():
    assert normalize_name("Margaret\u200b Chen").problem is Problem.CONTROL_CHARACTERS
    assert normalize_email("margaret@email.com\u200d").problem is Problem.CONTROL_CHARACTERS


def test_tabs_and_newlines_are_spacing_but_other_controls_are_rejected():
    assert normalize_name("Margaret\tChen\r\n") == Normalized("margaretchen")
    assert normalize_name("Margaret\x00Chen").problem is Problem.CONTROL_CHARACTERS
    assert normalize_name("Margaret\ue000 Chen").problem is Problem.CONTROL_CHARACTERS


@pytest.mark.parametrize(
    "normalizer",
    [normalize_dob, _us_phone, normalize_ssn_last4],
    ids=["dob", "phone", "ssn"],
)
def test_every_field_rejects_invisible_characters(normalizer):
    assert normalizer("1985\u200b").problem is Problem.CONTROL_CHARACTERS


@pytest.mark.parametrize(
    "raw", ["1985-03-15", "March 15, 1985", "15 March 1985", "Mar 15th 1985", "03/15/1985", "15/03/1985"]
)
def test_unambiguous_dates_of_birth(raw):
    assert normalize_dob(raw) == Normalized("1985-03-15")


def test_day_month_ambiguity_returns_both_readings():
    result = normalize_dob("03/04/1985")
    assert result.problem is Problem.AMBIGUOUS
    assert result.candidates == ("1985-03-04", "1985-04-03")


def test_same_day_and_month_is_not_ambiguous():
    assert normalize_dob("05/05/1990") == Normalized("1990-05-05")


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        ("03/15/85", Problem.INCOMPLETE),
        ("March 15, 85", Problem.INCOMPLETE),
        ("1985-02-30", Problem.INVALID),
        ("sometime in 1985", Problem.INVALID),
        ("Marching 15 1985", Problem.INVALID),
        ("1899-12-31", Problem.INVALID),
        ("2101-01-01", Problem.INVALID),
    ],
)
def test_unusable_dates_of_birth(raw, problem):
    assert normalize_dob(raw).problem is problem


@pytest.mark.parametrize(
    "raw",
    [
        "March 1\u0665 1985",
        "March 1\u06f5, 1985",
        "March 1\u096bth 1985",
        "March 1\u041e 1985",
        "March 2\u039f 1985",
        "\u0416may 15 1985",
    ],
    ids=["arabic-indic-5", "persian-5", "devanagari-5", "cyrillic-o", "greek-omicron", "cyrillic-letter"],
)
def test_a_mixed_script_date_is_refused_not_misread(raw):
    # Dropping the non-ASCII character would turn "March 15" into March 1.
    assert normalize_dob(raw).problem is Problem.INVALID


@pytest.mark.parametrize("raw", ["+1 (650) 521-2836", "650-521-2836", "16505212836", "650.521.2836"])
def test_us_phone_formats(raw):
    assert _us_phone(raw) == Normalized("+16505212836")


def test_explicit_country_code_is_kept():
    assert _us_phone("+44 20 7946 0958") == Normalized("+442079460958")


def test_explicit_international_numbers_of_8_to_15_digits_are_kept():
    assert _us_phone("+12345678") == Normalized("+12345678")
    assert _us_phone("+123456789012345") == Normalized("+123456789012345")


@pytest.mark.parametrize(
    ("raw", "problem"),
    [
        ("521-2836", Problem.INCOMPLETE),
        ("44 20 7946 0958", Problem.AMBIGUOUS),
        ("1 650 521 283", Problem.AMBIGUOUS),
        ("0650521283", Problem.AMBIGUOUS),
        ("11650521283", Problem.AMBIGUOUS),
        ("+44 (0) 20 7946 0958", Problem.AMBIGUOUS),
        ("650-CALL-NOW", Problem.INVALID),
        ("+0 650 521 2836", Problem.INVALID),
        ("+1234567", Problem.INVALID),
        ("+1234567890123456", Problem.INVALID),
        ("650+521-2836", Problem.INVALID),
        ("()", Problem.INVALID),
        ("-", Problem.INVALID),
    ],
)
def test_unusable_phone_numbers_are_not_guessed(raw, problem):
    assert _us_phone(raw).problem is problem


def test_email_is_trimmed_and_case_folded_but_otherwise_kept():
    assert normalize_email(" Margaret@Email.COM ") == Normalized("margaret@email.com")
    assert normalize_email("yawen.li+claims@gmail.com") == Normalized("yawen.li+claims@gmail.com")


@pytest.mark.parametrize("raw", ["not-an-email", "a@b", "a@@b.com", "a b@c.com"])
def test_invalid_emails(raw):
    assert normalize_email(raw).problem is Problem.INVALID


def test_ssn_last4_keeps_leading_zeros_and_ignores_spacing():
    assert normalize_ssn_last4("0042") == Normalized("0042")
    assert normalize_ssn_last4("44 72") == Normalized("4472")


def test_full_width_characters_are_read_as_ascii(policy):
    assert normalize_ssn_last4("４４７２") == Normalized("4472")
    assert normalize("phone", "６５０-５２１-２８３６", policy) == Normalized("+16505212836")
    assert normalize_dob("１９８５-０３-１５") == Normalized("1985-03-15")
    assert normalize_email("ｍａｒｇａｒｅｔ＠ｅｍａｉｌ．ｃｏｍ") == Normalized("margaret@email.com")


@pytest.mark.parametrize(
    ("normalizer", "raw"),
    [
        (normalize_ssn_last4, "٤٤٧٢"),
        (normalize_dob, "١٩٨٥-٠٣-١٥"),
        (_us_phone, "٦٥٠٥٢١٢٨٣٦"),
    ],
    ids=["ssn", "dob", "phone"],
)
def test_digits_from_other_scripts_are_rejected(normalizer, raw):
    assert normalizer(raw).problem is Problem.INVALID


@pytest.mark.parametrize(
    ("raw", "problem"), [("447", Problem.INCOMPLETE), ("123-45-4472", Problem.INVALID), ("abcd", Problem.INVALID)]
)
def test_unusable_ssn_values(raw, problem):
    assert normalize_ssn_last4(raw).problem is problem


def test_dispatcher_uses_policy_phone_settings(policy):
    assert normalize("phone", "650-521-2836", policy) == Normalized("+16505212836")
    assert normalize("dob", "March 15, 1985", policy) == Normalized("1985-03-15")


def test_a_result_holds_a_value_or_a_problem_but_not_both():
    with pytest.raises(ValueError):
        Normalized("margaretchen", Problem.INVALID)
    with pytest.raises(ValueError):
        Normalized(None)
    with pytest.raises(ValueError):
        Normalized(None, Problem.INVALID, ("1985-03-04",))


def test_repr_leaves_out_personal_values():
    assert "margaret" not in repr(normalize_name("Margaret Chen"))
    assert "1985" not in repr(normalize_dob("03/04/1985"))
