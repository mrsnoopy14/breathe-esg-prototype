"""
Green Button Data (GBD) CSV parser for utility electricity consumption.

Green Button is a US / Canadian standard for energy usage data exchange.
Utilities export per-interval readings; this parser handles the common CSV
flavour (as opposed to the XML/ESPI flavour).

Anomaly handling:
- Consumption > 10 000 for a reading that appears to be hourly is likely in Wh;
  we divide by 1 000 to convert to kWh and set a flag.
- Missing optional columns (Demand, Cost) are tolerated gracefully.
"""

import csv
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Column alias map
# ---------------------------------------------------------------------------

_COLUMN_ALIASES: dict[str, str] = {
    'service point id': 'meter_id',
    'service_point_id': 'meter_id',
    'service point': 'meter_id',
    'spid': 'meter_id',

    'meter number': 'meter_number',
    'meter_number': 'meter_number',
    'meter no': 'meter_number',
    'meter no.': 'meter_number',

    'start time': 'interval_start',
    'start_time': 'interval_start',
    'interval start': 'interval_start',
    'start': 'interval_start',

    'end time': 'interval_end',
    'end_time': 'interval_end',
    'interval end': 'interval_end',
    'end': 'interval_end',

    'duration (hours)': 'duration_hours',
    'duration_hours': 'duration_hours',
    'duration': 'duration_hours',
    'hours': 'duration_hours',

    'consumption (kwh)': 'consumption_kwh',
    'consumption_kwh': 'consumption_kwh',
    'consumption': 'consumption_kwh',
    'energy (kwh)': 'consumption_kwh',
    'usage (kwh)': 'consumption_kwh',
    'kwh': 'consumption_kwh',

    'demand (kw)': 'demand_kw',
    'demand_kw': 'demand_kw',
    'demand': 'demand_kw',
    'peak demand (kw)': 'demand_kw',

    'cost (usd)': 'cost_usd',
    'cost_usd': 'cost_usd',
    'cost': 'cost_usd',
    'charges': 'cost_usd',
    'amount': 'cost_usd',

    'tariff code': 'tariff_code',
    'tariff_code': 'tariff_code',
    'rate code': 'tariff_code',
    'tariff': 'tariff_code',

    'read type': 'read_type',
    'read_type': 'read_type',
    'reading type': 'read_type',
}

# Threshold above which an "hourly" kWh reading is suspect (likely Wh)
_WH_SUSPECT_THRESHOLD = 10_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _parse_datetime(value: str) -> datetime:
    """Parse ISO or US datetime / date strings into a datetime object."""
    value = value.strip()
    formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y %H:%M',
        '%m/%d/%Y',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: '{value}'")


def _parse_decimal_optional(value: str | None) -> Decimal | None:
    if not value or not value.strip():
        return None
    try:
        return Decimal(value.strip().replace(',', ''))
    except InvalidOperation:
        return None


def _parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value.strip().replace(',', ''))
    except InvalidOperation:
        raise ValueError(f"Cannot parse number: '{value}'")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_utility_electricity(filepath: str) -> tuple[list[dict], list[dict]]:
    """
    Parse a Green Button Data CSV export.

    Returns
    -------
    records : list[dict]
        Keys: interval_start (date), interval_end (date), duration_hours,
        consumption_kwh, demand_kw, cost_usd, tariff_code,
        meter_id, meter_number, wh_converted (bool flag).
    errors : list[dict]
        Keys: row (1-based index), error (str).
    """
    raw_rows = _read_csv(filepath)

    if not raw_rows:
        return [], []

    # Validate required columns using the first row as probe
    probe = _normalise_headers(raw_rows[0])
    for required in ('interval_start', 'consumption_kwh'):
        if required not in probe:
            raise ValueError(
                f"parse_utility_electricity: required column '{required}' not found. "
                f"Available columns: {list(probe.keys())}"
            )

    records: list[dict] = []
    errors: list[dict] = []

    for idx, raw_row in enumerate(raw_rows, start=2):
        if not any(v.strip() for v in raw_row.values() if isinstance(v, str)):
            continue

        row = _normalise_headers(raw_row)

        try:
            start_dt = _parse_datetime(row['interval_start'])
            interval_start: date = start_dt.date()

            end_raw = row.get('interval_end', '').strip()
            interval_end: date = _parse_datetime(end_raw).date() if end_raw else interval_start

            duration_raw = row.get('duration_hours', '').strip()
            duration_hours = _parse_decimal_optional(duration_raw) or Decimal('1')

            consumption_kwh = _parse_decimal(row['consumption_kwh'])

            # Detect Wh readings: if > threshold and duration is ~1 hour, convert
            wh_converted = False
            if float(consumption_kwh) > _WH_SUSPECT_THRESHOLD and float(duration_hours) <= 1.5:
                consumption_kwh = consumption_kwh / Decimal('1000')
                wh_converted = True

            demand_kw = _parse_decimal_optional(row.get('demand_kw'))
            cost_usd = _parse_decimal_optional(row.get('cost_usd'))

            records.append({
                'interval_start': interval_start,
                'interval_end': interval_end,
                'duration_hours': duration_hours,
                'consumption_kwh': consumption_kwh,
                'demand_kw': demand_kw,
                'cost_usd': cost_usd,
                'tariff_code': row.get('tariff_code', ''),
                'meter_id': row.get('meter_id', ''),
                'meter_number': row.get('meter_number', ''),
                'wh_converted': wh_converted,
            })

        except (ValueError, KeyError) as exc:
            errors.append({'row': idx, 'error': str(exc)})

    return records, errors
