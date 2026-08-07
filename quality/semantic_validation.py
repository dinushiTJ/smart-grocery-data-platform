#!/usr/bin/env python3
"""Hybrid semantic validation using local rules and optional Ollama."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:7b"


@dataclass
class ValidationResult:
    barcode: str
    status: str
    confidence: float
    reasons: list[str]
    validator: str


def validate_product_rules(product: dict[str, Any]) -> ValidationResult:
    barcode = str(product.get("code", "")).strip()
    name = str(product.get("product_name", "")).strip()
    reasons: list[str] = []

    if not barcode:
        reasons.append("Missing barcode")
    if not name:
        reasons.append("Missing product name")
    if barcode and name and name.casefold() == barcode.casefold():
        reasons.append("Product name is identical to barcode")
    if name and re.fullmatch(r"[0-9\s-]+", name):
        reasons.append("Product name contains no descriptive text")

    return ValidationResult(
        barcode=barcode,
        status="reject" if reasons else "pass",
        confidence=0.99 if reasons else 0.95,
        reasons=reasons,
        validator="deterministic-semantic-rules",
    )


def validate_product_with_ollama(
    product: dict[str, Any], model: str = DEFAULT_MODEL
) -> ValidationResult:
    rule_result = validate_product_rules(product)
    if rule_result.status == "reject":
        return rule_result

    prompt = (
        "Review this grocery product for semantic quality. Return JSON only with "
        "status (pass or reject), confidence (0 to 1), and reasons (array of strings). "
        "Use reject only for a clear contradiction or unusable value. Do not reject "
        "a product only because optional fields are missing.\n\n"
        + json.dumps(
            {
                "barcode": product.get("code"),
                "product_name": product.get("product_name"),
                "brands": product.get("brands"),
                "categories_tags": product.get("categories_tags"),
                "ingredients_text": product.get("ingredients_text"),
                "nutriments": product.get("nutriments"),
            },
            ensure_ascii=True,
        )
    )
    response = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "format": "json", "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    answer = response.json().get("response", "{}")
    parsed = json.loads(answer)
    status = parsed.get("status", "review")
    if status not in {"pass", "reject"}:
        status = "reject"
    confidence = min(1.0, max(0.0, float(parsed.get("confidence", 0.5))))
    reasons = [str(reason) for reason in parsed.get("reasons", [])]
    return ValidationResult(
        barcode=str(product.get("code", "")),
        status=status,
        confidence=confidence,
        reasons=reasons,
        validator=f"ollama:{model}",
    )


def validate_products(
    products: list[dict[str, Any]], use_ollama: bool = False, model: str = DEFAULT_MODEL
) -> list[ValidationResult]:
    results = []
    for product in products:
        result = (
            validate_product_with_ollama(product, model)
            if use_ollama
            else validate_product_rules(product)
        )
        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--ollama", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    body = json.loads(args.input.read_text(encoding="utf-8"))
    products = body.get("products", [])
    results = validate_products(products, args.ollama, args.model)
    payload = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "validator": "ollama+deterministic-rules" if args.ollama else "deterministic-rules",
        "results": [asdict(result) for result in results],
    }
    output = json.dumps(payload, indent=2, ensure_ascii=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
