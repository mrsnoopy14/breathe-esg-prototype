"""
SAP flat-file CSV parsers.

SAP exports are notoriously inconsistent: the same transaction can produce
English headers (BUDAT) or German headers (Buchungsdatum), and encoding
ranges from UTF-8 to Windows-1252.  Both parsers normalise column names
before accessing data so callers always receive the same dict keys.
"""

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


# ---------------------------------------------------------------------------
# Column alias maps — maps every known header variant → canonical key
# ---------------------------------------------------------------------------

_FUEL_COLUMN_ALIASES: dict[str, str] = {
    # Posting date
    'budat': 'posting_date',
    'buchungsdatum': 'posting_date',
    'posting date': 'posting_date',
    'document date': 'posting_date',
    # Plant
    'werks': 'plant_code',
    'werk': 'plant_code',
    'plant': 'plant_code',
    # Material number
    'matnr': 'material_number',
    'material': 'material_number',
    'material number': 'material_number',
    # Material description
    'maktx': 'material_description',
    'materialkurztext': 'material_description',
    'material description': 'material_description',
    'material short text': 'material_description',
    # Movement type
    'bwart': 'movement_type',
    'bewegungsart': 'movement_type',
    'movement type': 'movement_type',
    # Quantity
    'menge': 'quantity',
    'qty': 'quantity',
    'quantity': 'quantity',
    # Base unit
    'meins': 'unit',
    'basismengeneinheit': 'unit',
    'base unit': 'unit',
    'unit': 'unit',
    # Cost centre
    'kostl': 'cost_center',
    'kostenstelle': 'cost_center',
    'cost center': 'cost_center',
    'cost centre': 'cost_center',
    # Amount
    'dmbtr': 'amount',
    'betrag in hauswährung': 'amount',
    'amount': 'amount',
    'amount in local currency': 'amount',
    # Currency
    'waers': 'currency',
    'währung': 'currency',
    'currency': 'currency',
    # Document number (optional)
    'mblnr': 'document_number',
    'materialbelegnnummer': 'document_number',
    'material document': 'document_number',
    'document number': 'document_number',
}

_PROCUREMENT_COLUMN_ALIASES: dict[str, str] = {
    # PO date
    'bedat': 'po_date',
    'bestelldatum': 'po_date',
    'po date': 'po_date',
    'order date': 'po_date',
    # PO number
    'ebeln': 'po_number',
    'po number': 'po_number',
    'purchasing document': 'po_number',
    # Material number
    'matnr': 'material_number',
    'material': 'material_number',
    'material number': 'material_number',
    # Short text
    'txz01': 'short_text',
    'kurztext': 'short_text',
    'short text': 'short_text',
    'item text': 'short_text',
    # Quantity
    'menge': 'quantity',
    'quantity': 'quantity',
    'qty': 'quantity',
    # Unit
    'meins': 'unit',
    'unit': 'unit',
    'base unit': 'unit',
    # Net price
    'netpr': 'net_price',
    'net price': 'net_price',
    'price': 'net_price',
    # Price unit
    'peinh': 'price_unit',
    'price unit': 'price_unit',
    # Currency
    'waers': 'currency',
    'currency': 'currency',
    # Vendor
    'name1': 'vendor_name',
    'lieferant': 'vendor_name',
    'vendor': 'vendor_name',
    'vendor name': 'vendor_name',
    'supplier': 'vendor_name',
    # Plant
    'werks': 'plant_code',
    'plant': 'plant_code',
}

# Goods-issue movement types we treat as fuel consumption
_FUEL_MOVEMENT_TYPES = {'201', '261', '262', '551'}

# SAP unit → canonical unit string
_UNIT_MAP: dict[str, str] = {
    'l': 'liters',
    'ltr': 'liters',
    'lit': 'liters',
    'liters': 'liters',
    'litre': 'liters',
    'litres': 'liters',
    'gal': 'gallons',
    'gall': 'gallons',
    'gallons': 'gallons',
    'gallon': 'gallons',
    'kg': 'kg',
    'kgs': 'kg',
    'kilogram': 'kg',
    'kilograms': 'kg',
    'm3': 'm3',
    'cbm': 'm3',
    'cubic meter': 'm3',
    'cubic metre': 'm3',
    'to': 'tonnes',
    'ton': 'tonnes',
    'tons': 'tonnes',
    'tonne': 'tonnes',
    'tonnes': 'tonnes',
    'mt': 'tonnes',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_csv(filepath: str) -> tuple[list[dict], str]:
    """
    Read a CSV file trying UTF-8 first, then Latin-1.
    Returns (rows_as_dicts, encoding_used).
    """
    for encoding in ('utf-8-sig', 'latin-1'):
        try:
            with open(filepath, newline='', encoding=encoding) as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            return rows, encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot read {filepath}: tried utf-8 and latin-1 encodings.")


def _normalise_headers(row: dict, alias_map: dict[str, str]) -> dict[str, Any]:
    """
    Return a new dict where every key is lowercased and resolved through
    alias_map.  Unknown columns are preserved as-is so callers can inspect them.
    """
    out: dict[str, Any] = {}
    for key, value in row.items():
        normalised = alias_map.get(key.strip().lower(), key.strip().lower())
        out[normalised] = value.strip() if isinstance(value, str) else value
    return out


def _parse_date(value: str) -> date:
    """
    Parse a date string.  SAP most commonly exports DD.MM.YYYY or YYYY-MM-DD.
    """
    value = value.strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y%m%d'):
        try:
            from datetime import datetime
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{value}'")


def _parse_decimal(value: str) -> Decimal:
    """
    Parse a decimal that may use comma as thousands separator or decimal separator.
    SAP German locales export '1.234,56'; English locales export '1234.56'.
    """
    value = value.strip()
    # If both comma and period present, the last one is the decimal separator
    if ',' in value and '.' in value:
        if value.rfind(',') > value.rfind('.'):
            # German format: 1.234,56
            value = value.replace('.', '').replace(',', '.')
        else:
            # English format with comma thousands: 1,234.56
            value = value.replace(',', '')
    elif ',' in value:
        # Could be decimal comma (no period): 1234,56
        value = value.replace(',', '.')
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"Cannot parse number: '{value}'")


def _check_required_columns(row: dict, required: list[str], source: str) -> None:
    missing = [col for col in required if col not in row]
    if missing:
        raise ValueError(
            f"{source}: required columns not found after alias resolution: {missing}. "
            f"Available columns: {list(row.keys())}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_sap_fuel(filepath: str) -> tuple[list[dict], list[dict]]:
    """
    Parse an MB51-style SAP material document CSV export.

    Returns
    -------
    records : list[dict]
        Dicts with keys: posting_date, plant_code, material_number,
        material_description, movement_type, quantity, unit, cost_center,
        amount, currency, document_number.
    errors : list[dict]
        Dicts with keys: row (1-based index), error (str).
    """
    raw_rows, _enc = _read_csv(filepath)

    if not raw_rows:
        return [], []

    # Check required columns using the first row as a probe
    probe = _normalise_headers(raw_rows[0], _FUEL_COLUMN_ALIASES)
    required = ['posting_date', 'plant_code', 'material_number', 'movement_type', 'quantity', 'unit']
    _check_required_columns(probe, required, 'parse_sap_fuel')

    records: list[dict] = []
    errors: list[dict] = []

    for idx, raw_row in enumerate(raw_rows, start=2):  # row 1 = header
        # Skip completely blank rows
        if not any(v.strip() for v in raw_row.values() if isinstance(v, str)):
            continue

        row = _normalise_headers(raw_row, _FUEL_COLUMN_ALIASES)

        try:
            movement_type = row.get('movement_type', '').strip()
            if movement_type not in _FUEL_MOVEMENT_TYPES:
                # Not a consumption event — silently skip
                continue

            posting_date = _parse_date(row['posting_date'])
            quantity = _parse_decimal(row['quantity'])

            raw_unit = row.get('unit', '').strip()
            unit = _UNIT_MAP.get(raw_unit.lower(), raw_unit.lower())

            amount_raw = row.get('amount', '').strip()
            amount = _parse_decimal(amount_raw) if amount_raw else Decimal('0')

            records.append({
                'posting_date': posting_date,
                'plant_code': row.get('plant_code', ''),
                'material_number': row.get('material_number', ''),
                'material_description': row.get('material_description', ''),
                'movement_type': movement_type,
                'quantity': quantity,
                'unit': unit,
                'cost_center': row.get('cost_center', ''),
                'amount': amount,
                'currency': row.get('currency', ''),
                'document_number': row.get('document_number', ''),
            })

        except (ValueError, KeyError) as exc:
            errors.append({'row': idx, 'error': str(exc)})

    return records, errors


def parse_sap_procurement(filepath: str) -> tuple[list[dict], list[dict]]:
    """
    Parse an ME2N-style SAP purchase-order-by-material CSV export.

    Returns
    -------
    records : list[dict]
        Dicts with keys: po_date, po_number, material_number, short_text,
        quantity, unit, net_price, price_unit, currency, vendor_name, plant_code.
    errors : list[dict]
        Dicts with keys: row (1-based index), error (str).
    """
    raw_rows, _enc = _read_csv(filepath)

    if not raw_rows:
        return [], []

    probe = _normalise_headers(raw_rows[0], _PROCUREMENT_COLUMN_ALIASES)
    required = ['po_date', 'po_number', 'quantity', 'currency', 'vendor_name']
    _check_required_columns(probe, required, 'parse_sap_procurement')

    records: list[dict] = []
    errors: list[dict] = []

    for idx, raw_row in enumerate(raw_rows, start=2):
        if not any(v.strip() for v in raw_row.values() if isinstance(v, str)):
            continue

        row = _normalise_headers(raw_row, _PROCUREMENT_COLUMN_ALIASES)

        try:
            po_date = _parse_date(row['po_date'])
            quantity = _parse_decimal(row.get('quantity', '0') or '0')

            net_price_raw = row.get('net_price', '').strip()
            net_price = _parse_decimal(net_price_raw) if net_price_raw else Decimal('0')

            price_unit_raw = row.get('price_unit', '1').strip()
            price_unit = _parse_decimal(price_unit_raw) if price_unit_raw else Decimal('1')

            records.append({
                'po_date': po_date,
                'po_number': row.get('po_number', ''),
                'material_number': row.get('material_number', ''),
                'short_text': row.get('short_text', ''),
                'quantity': quantity,
                'unit': row.get('unit', ''),
                'net_price': net_price,
                'price_unit': price_unit,
                'currency': row.get('currency', ''),
                'vendor_name': row.get('vendor_name', ''),
                'plant_code': row.get('plant_code', ''),
            })

        except (ValueError, KeyError) as exc:
            errors.append({'row': idx, 'error': str(exc)})

    return records, errors
