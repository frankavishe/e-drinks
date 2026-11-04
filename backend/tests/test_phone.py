import pytest

from app.services.phone import InvalidPhone, normalise_phone


@pytest.mark.parametrize(
    "raw",
    ["0712345678", "255712345678", "+255712345678", "+255 712-345-678", " 0712 345 678 "],
)
def test_all_formats_are_the_same_number(raw):
    assert normalise_phone(raw) == "255712345678"


def test_06_numbers_are_mobiles_too():
    assert normalise_phone("0612345678") == "255612345678"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "abc",
        "0222123456",  # landline
        "071234567",  # too short
        "07123456789",  # too long
        "712345678",  # no prefix
        "+447712345678",  # foreign
        "2550712345678",  # 255 and 0 together
        "٠٧١٢٣٤٥٦٧٨",  # non-ASCII digits
    ],
)
def test_rejects(raw):
    with pytest.raises(InvalidPhone):
        normalise_phone(raw)
