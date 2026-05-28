"""
Flagging service.

Examines normalized EmissionRecord field values and returns a set of flags
and human-readable reasons.  This runs synchronously during ingestion so
analysts immediately see which records need review.

Flag design principle: flags are informational — they raise questions, not
verdicts.  The analyst can approve a flagged record after confirming the data.
"""

import statistics
from datetime import date
from decimal import Decimal
from typing import Any

# Units we understand.  Anything else is flagged as unrecognised.
_KNOWN_UNITS = {
    # fuel
    'liters', 'litres', 'l', 'ltr', 'gallons', 'gal', 'kg', 'tonnes', 'mt', 'm3', 'cbm',
    # electricity
    'kwh', 'mwh', 'wh',
    # travel
    'passenger_km', 'room_nights', 'km', 'miles',
    # procurement / spend-based
    'usd', 'eur', 'gbp', 'inr', 'unit',
    # generic
    'unknown',
}


def flag_record(
    record_data: dict[str, Any],
    all_company_records_for_category: list[dict[str, Any]],
) -> tuple[dict[str, bool], list[str]]:
    """
    Evaluate a set of flag conditions for a single record.

    Parameters
    ----------
    record_data
        Dict of EmissionRecord field values (as produced by the normalizer),
        plus private '_*' keys set by the normalizer for flag hints.
    all_company_records_for_category
        List of existing EmissionRecord-like dicts for the same company + category.
        Used only for statistical outlier detection.

    Returns
    -------
    flags : dict[str, bool]
        Each key is a flag name; value is True if the condition fired.
    flag_reasons : list[str]
        Human-readable explanations for each True flag (same order as flags).
    """
    flags: dict[str, bool] = {}
    flag_reasons: list[str] = []

    raw_quantity = record_data.get('raw_quantity', Decimal('0'))
    co2e_kg = record_data.get('co2e_kg', Decimal('0'))
    activity_date = record_data.get('activity_date')
    raw_unit = record_data.get('raw_unit', '')

    # ------------------------------------------------------------------
    # 1. Zero or negative quantity
    # ------------------------------------------------------------------
    is_zero = float(raw_quantity) <= 0
    flags['zero_quantity'] = is_zero
    if is_zero:
        flag_reasons.append(
            f"Raw quantity is {raw_quantity} — zero or negative values cannot produce valid CO2e."
        )

    # ------------------------------------------------------------------
    # 2. Future activity date
    # ------------------------------------------------------------------
    today = date.today()
    is_future = isinstance(activity_date, date) and activity_date > today
    flags['future_date'] = is_future
    if is_future:
        flag_reasons.append(
            f"Activity date {activity_date} is in the future (today is {today})."
        )

    # ------------------------------------------------------------------
    # 3. Unrecognised unit
    # ------------------------------------------------------------------
    unrecognised = raw_unit.lower() not in _KNOWN_UNITS
    flags['unrecognized_unit'] = unrecognised
    if unrecognised:
        flag_reasons.append(
            f"Unit '{raw_unit}' is not in the recognised unit list. "
            f"Verify conversion and re-map if necessary."
        )

    # ------------------------------------------------------------------
    # 4. Statistical outlier (z-score / μ + 3σ rule)
    # Requires at least 5 existing records in the same category to be
    # meaningful; below that the statistics are too noisy to be actionable.
    # ------------------------------------------------------------------
    is_outlier = False
    if len(all_company_records_for_category) >= 5:
        existing_values = [
            float(r.get('co2e_kg', 0))
            for r in all_company_records_for_category
            if r.get('co2e_kg') is not None
        ]
        if len(existing_values) >= 5:
            mean = statistics.mean(existing_values)
            stdev = statistics.stdev(existing_values)
            threshold = mean + 3 * stdev
            current_val = float(co2e_kg)
            if current_val > threshold and stdev > 0:
                is_outlier = True
                ratio = current_val / mean if mean > 0 else float('inf')
                flag_reasons.append(
                    f"CO2e value ({co2e_kg:.2f} kgCO2e) is {ratio:.1f}x the category mean "
                    f"({mean:.2f} kgCO2e) and exceeds the μ + 3σ threshold ({threshold:.2f})."
                )

    flags['statistical_outlier'] = is_outlier

    # ------------------------------------------------------------------
    # 5. Fuel type inferred from description (SAP fuel only)
    # ------------------------------------------------------------------
    fuel_inferred = bool(record_data.get('_fuel_type_inferred', False))
    flags['fuel_type_inferred'] = fuel_inferred
    if fuel_inferred:
        flag_reasons.append(
            "Fuel type was inferred from the material description. "
            "Please verify the correct fuel type and emission factor."
        )

    # ------------------------------------------------------------------
    # 6. Airport distance unavailable (air or ground travel)
    # ------------------------------------------------------------------
    dist_unavailable = bool(record_data.get('_distance_unavailable', False))
    flags['distance_unavailable'] = dist_unavailable
    if dist_unavailable:
        flag_reasons.append(
            f"Distance could not be computed from city codes "
            f"('{record_data.get('description', '')}').  "
            f"CO2e is set to 0 — enter the distance manually and recalculate."
        )

    # ------------------------------------------------------------------
    # 7. Spend-based emission factor (procurement)
    # ------------------------------------------------------------------
    spend_based = bool(record_data.get('_spend_based_factor', False))
    flags['spend_based_factor'] = spend_based
    if spend_based:
        flag_reasons.append(
            "This record uses a spend-based EEIO emission factor (0.5 kgCO2e/USD), "
            "which is a rough proxy for Scope 3 Category 1.  "
            "Replace with a supplier-specific factor when available."
        )

    return flags, flag_reasons
