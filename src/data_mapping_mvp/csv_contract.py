from __future__ import annotations

import csv
import io
from typing import Any, Dict, List


CSV_COLUMNS = [
    "SourceFile",
    "CustomerName",
    "ReportingPeriod",
    "LineItemName",
    "Quantity",
    "UnitPrice",
    "TotalAmount",
    "Currency",
    "ConfidenceScore",
]

MIN_CONFIDENCE_SCORE = 0.75


class ValidationError(ValueError):
    pass


def _normalize_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_number(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return format(value, ".2f")
    return str(value).strip()


def map_canonical_payload_to_csv(payload: Dict[str, Any], source_file: str) -> Dict[str, str]:
    customer_name = _normalize_string(payload.get("customerName"))
    reporting_period = _normalize_string(payload.get("reportingPeriod"))
    currency = _normalize_string(payload.get("currency"))
    confidence_score = payload.get("confidenceScore")

    if not customer_name:
        raise ValidationError("customerName is required")
    if not reporting_period:
        raise ValidationError("reportingPeriod is required")
    if not currency:
        raise ValidationError("currency is required")

    if confidence_score is None:
        raise ValidationError("confidenceScore is required")
    if float(confidence_score) < MIN_CONFIDENCE_SCORE:
        raise ValidationError("confidenceScore below threshold")

    line_items = payload.get("lineItems") or []
    if not isinstance(line_items, list) or not line_items:
        raise ValidationError("lineItems must contain at least one item")

    first_line_item = line_items[0]
    line_item_name = _normalize_string(first_line_item.get("name"))
    quantity = _normalize_number(first_line_item.get("quantity"))
    unit_price = _normalize_number(first_line_item.get("unitPrice"))
    total_amount = _normalize_number(first_line_item.get("totalAmount"))

    if not line_item_name:
        raise ValidationError("lineItems[0].name is required")
    if not quantity:
        raise ValidationError("lineItems[0].quantity is required")
    if not unit_price:
        raise ValidationError("lineItems[0].unitPrice is required")
    if not total_amount:
        raise ValidationError("lineItems[0].totalAmount is required")

    return {
        "SourceFile": _normalize_string(source_file),
        "CustomerName": customer_name,
        "ReportingPeriod": reporting_period,
        "LineItemName": line_item_name,
        "Quantity": str(int(float(quantity))) if quantity else "",
        "UnitPrice": unit_price if len(unit_price.split(".")) == 2 else f"{unit_price}.00",
        "TotalAmount": total_amount if len(total_amount.split(".")) == 2 else f"{total_amount}.00",
        "Currency": currency,
        "ConfidenceScore": str(confidence_score),
    }


def build_csv_content(rows: List[Dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
