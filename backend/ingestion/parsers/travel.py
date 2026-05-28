"""
Concur Expense Export CSV parser for corporate travel.

Concur exports vary significantly between deployments.  This parser handles the
most common column set while gracefully degrading for optional fields.

Also provides:
  - AIRPORT_COORDS: lat/lon for 30 major airports
  - haversine_km(lat1, lon1, lat2, lon2): great-circle distance
  - airport_distance_km(code1, code2): convenience wrapper
"""

import csv
import math
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Airport coordinates (IATA code → (lat, lon))
# Source: OurAirports / Wikipedia — sufficient precision for emission estimates
# ---------------------------------------------------------------------------

AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    # North America
    'JFK': (40.6413, -73.7781),   # New York JFK
    'LAX': (33.9425, -118.4081),  # Los Angeles
    'ORD': (41.9742, -87.9073),   # Chicago O'Hare
    'ATL': (33.6407, -84.4277),   # Atlanta Hartsfield
    'DFW': (32.8998, -97.0403),   # Dallas Fort Worth
    'MIA': (25.7959, -80.2870),   # Miami
    'SFO': (37.6213, -122.3790),  # San Francisco
    'SEA': (47.4502, -122.3088),  # Seattle
    'BOS': (42.3656, -71.0096),   # Boston
    'IAD': (38.9531, -77.4565),   # Washington Dulles
    'DEN': (39.8561, -104.6737),  # Denver
    'IAH': (29.9844, -95.3414),   # Houston Intercontinental
    'PHX': (33.4373, -112.0078),  # Phoenix
    # Europe / Middle East
    'LHR': (51.4700, -0.4543),    # London Heathrow
    'CDG': (49.0097, 2.5479),     # Paris Charles de Gaulle
    'DXB': (25.2532, 55.3657),    # Dubai
    # Asia Pacific
    'SIN': (1.3644, 103.9915),    # Singapore Changi
    'HKG': (22.3080, 113.9185),   # Hong Kong
    'NRT': (35.7720, 140.3929),   # Tokyo Narita
    'SYD': (-33.9399, 151.1753),  # Sydney
    # India
    'BOM': (19.0896, 72.8656),    # Mumbai (Bombay)
    'DEL': (28.5562, 77.1000),    # Delhi Indira Gandhi
    'BLR': (13.1986, 77.7066),    # Bengaluru Kempegowda
    'MAA': (12.9941, 80.1709),    # Chennai
    'HYD': (17.2403, 78.4294),    # Hyderabad Rajiv Gandhi
    'CCU': (22.6547, 88.4467),    # Kolkata Netaji Subhash Chandra Bose
    'PNQ': (18.5822, 73.9197),    # Pune
    'GOI': (15.3808, 73.8314),    # Goa Dabolim
    'AMD': (23.0772, 72.6347),    # Ahmedabad
    'NAG': (21.0922, 79.0472),    # Nagpur
}

# ---------------------------------------------------------------------------
# Column alias map
# ---------------------------------------------------------------------------

_COLUMN_ALIASES: dict[str, str] = {
    'transaction date': 'transaction_date',
    'transaction_date': 'transaction_date',
    'date': 'transaction_date',
    'expense date': 'transaction_date',

    'expense type': 'expense_type',
    'expense_type': 'expense_type',
    'type': 'expense_type',
    'category': 'expense_type',

    'vendor name': 'vendor_name',
    'vendor_name': 'vendor_name',
    'vendor': 'vendor_name',
    'supplier': 'vendor_name',
    'merchant': 'vendor_name',

    'city from': 'city_from',
    'city_from': 'city_from',
    'from': 'city_from',
    'departure city': 'city_from',
    'origin': 'city_from',

    'city to': 'city_to',
    'city_to': 'city_to',
    'to': 'city_to',
    'arrival city': 'city_to',
    'destination': 'city_to',

    'amount': 'amount',
    'total': 'amount',
    'transaction amount': 'amount',
    'approved amount': 'amount',

    'currency': 'currency',
    'transaction currency': 'currency',
    'currency code': 'currency',

    'quantity': 'quantity',
    'qty': 'quantity',
    'nights': 'quantity',
    'distance': 'quantity',
    'km': 'quantity',

    'unit': 'unit',
    'uom': 'unit',

    'report name': 'report_name',
    'report_name': 'report_name',
    'expense report': 'report_name',
    'report': 'report_name',

    'employee id': 'employee_id',
    'employee_id': 'employee_id',
    'emp id': 'employee_id',
    'staff id': 'employee_id',
    'employee number': 'employee_id',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the great-circle distance between two points on Earth (km).

    Uses the Haversine formula which is accurate to within ~0.5% for most
    inter-city distances — more than adequate for emission factor calculations.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def airport_distance_km(code1: str, code2: str) -> float | None:
    """
    Return the great-circle distance (km) between two airports by IATA code.
    Returns None if either code is not in AIRPORT_COORDS.
    """
    c1 = code1.upper().strip()
    c2 = code2.upper().strip()
    coords1 = AIRPORT_COORDS.get(c1)
    coords2 = AIRPORT_COORDS.get(c2)

    if coords1 is None or coords2 is None:
        return None

    return haversine_km(coords1[0], coords1[1], coords2[0], coords2[1])


def _read_csv(filepath: str) -> list[dict]:
    for encoding in ('utf-8-sig', 'latin-1'):
        try:
            with open(filepath, newline='', encoding=encoding) as fh:
                reader = csv.DictReader(fh)
                return list(reader)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot read {filepath}: tried utf-8 and latin-1 encodings.")


def _normalise_headers(row: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        normalised = _COLUMN_ALIASES.get(key.strip().lower(), key.strip().lower())
        out[normalised] = value.strip() if isinstance(value, str) else value
    return out


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{value}'")


def _parse_decimal_optional(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    cleaned = value.strip().replace(',', '')
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_decimal(value: str) -> Decimal:
    cleaned = value.strip().replace(',', '')
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Cannot parse number: '{value}'")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_travel(filepath: str) -> tuple[list[dict], list[dict]]:
    """
    Parse a Concur expense export CSV.

    Returns
    -------
    records : list[dict]
        Keys: transaction_date (date), expense_type, vendor_name, city_from,
        city_to, amount, currency, quantity, unit, report_name, employee_id.
    errors : list[dict]
        Keys: row (1-based), error (str).
    """
    raw_rows = _read_csv(filepath)

    if not raw_rows:
        return [], []

    probe = _normalise_headers(raw_rows[0])
    for required in ('transaction_date', 'expense_type', 'amount', 'currency'):
        if required not in probe:
            raise ValueError(
                f"parse_travel: required column '{required}' not found. "
                f"Available columns: {list(probe.keys())}"
            )

    records: list[dict] = []
    errors: list[dict] = []

    for idx, raw_row in enumerate(raw_rows, start=2):
        if not any(v.strip() for v in raw_row.values() if isinstance(v, str)):
            continue

        row = _normalise_headers(raw_row)

        try:
            transaction_date = _parse_date(row['transaction_date'])
            amount = _parse_decimal(row.get('amount', '0') or '0')
            quantity = _parse_decimal_optional(row.get('quantity'))

            records.append({
                'transaction_date': transaction_date,
                'expense_type': row.get('expense_type', ''),
                'vendor_name': row.get('vendor_name', ''),
                'city_from': row.get('city_from', ''),
                'city_to': row.get('city_to', ''),
                'amount': amount,
                'currency': row.get('currency', ''),
                'quantity': quantity,
                'unit': row.get('unit', ''),
                'report_name': row.get('report_name', ''),
                'employee_id': row.get('employee_id', ''),
            })

        except (ValueError, KeyError) as exc:
            errors.append({'row': idx, 'error': str(exc)})

    return records, errors
