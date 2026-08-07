from processing.run_pipeline import clean_product, safe_float


def test_safe_float_accepts_number() -> None:
    assert safe_float("5.25") == 5.25


def test_safe_float_rejects_invalid_value() -> None:
    assert safe_float("not-a-number") is None


def test_clean_product_requires_barcode() -> None:
    product = {
        "product_name": "Example product",
        "nutriments": {},
    }

    assert clean_product(product) is None


def test_clean_product_rejects_barcode_as_product_name() -> None:
    product = {
        "code": "6111035000027",
        "product_name": "6111035000027",
    }

    assert clean_product(product) is None


def test_clean_product_creates_expected_values() -> None:
    product = {
        "code": "123456789",
        "product_name": "Example product",
        "brands": "Example Brand",
        "categories_tags": ["en:beverages"],
        "ingredients_text": "Water and fruit",
        "nutriments": {
            "energy-kcal_100g": 45,
        },
    }

    result = clean_product(product)

    assert result is not None
    assert result["barcode"] == "123456789"
    assert result["energy_kcal_100g"] == 45
