from quality.semantic_validation import validate_product_rules


def test_semantic_rules_reject_barcode_as_product_name():
    result = validate_product_rules(
        {"code": "6111035000027", "product_name": "6111035000027"}
    )

    assert result.status == "reject"
    assert "identical to barcode" in result.reasons[0]


def test_semantic_rules_accept_descriptive_product():
    result = validate_product_rules(
        {"code": "123", "product_name": "Sparkling water"}
    )

    assert result.status == "pass"
