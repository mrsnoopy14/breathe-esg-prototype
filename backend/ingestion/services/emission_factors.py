"""
Emission factor constants and lookup functions.

Sources:
  - DEFRA 2023 Greenhouse Gas Conversion Factors for Company Reporting
  - CEA (India) 2022 CO2 baseline factors for electricity
  - EPA 2022 eGRID national average for US electricity
  - HCMI 2016 global average hotel carbon intensity
  - EEIO spend-based factors for procurement

All fuel combustion factors are kgCO2e per base unit (liters or m3 or kg).
All electricity factors are kgCO2e per kWh.
Air travel factors are kgCO2e per passenger-km (include Radiative Forcing Index).
Ground factors are kgCO2e per vehicle-km (proxy for one passenger).
"""

# ---------------------------------------------------------------------------
# Fuel combustion — kgCO2e per liter (Scope 1, DEFRA 2023)
# ---------------------------------------------------------------------------

FUEL_FACTORS: dict[str, float] = {
    'diesel':          2.68619,   # per litre
    'petrol':          2.31492,   # per litre
    'gasoline':        2.31492,   # per litre (alias for petrol)
    'lpg':             1.51991,   # per litre
    'natural_gas_m3':  1.93916,   # per m3
    'natural_gas_kg':  2.66827,   # per kg
}

# Unit conversion to liters (None = not directly convertible without fuel density)
FUEL_UNIT_TO_LITERS: dict[str, float | None] = {
    'liters':   1.0,
    'l':        1.0,
    'ltr':      1.0,
    'gallons':  3.78541,
    'gal':      3.78541,
    'kg':       None,     # requires fuel-specific density
    'tonnes':   None,     # requires fuel-specific density
    'm3':       1000.0,   # approx for LPG / natural gas (liquid state)
}

# ---------------------------------------------------------------------------
# Electricity — kgCO2e per kWh (Scope 2, location-based grid average)
# ---------------------------------------------------------------------------

ELECTRICITY_FACTORS: dict[str, float] = {
    'IN': 0.716,    # India (CEA 2022)
    'GB': 0.23314,  # UK (DEFRA 2023)
    'US': 0.38600,  # USA (EPA eGRID 2022 national average)
    'DE': 0.38400,  # Germany (UBA 2022)
    'AU': 0.79000,  # Australia (DCCEW 2023)
    'SG': 0.40800,  # Singapore (EMA 2022)
    'AE': 0.53400,  # UAE
    'default': 0.45000,  # Global average fallback (IEA)
}

# ---------------------------------------------------------------------------
# Business travel — air (kgCO2e per passenger-km, DEFRA 2023, includes RFI)
# ---------------------------------------------------------------------------

AIR_FACTORS: dict[str, float] = {
    'domestic':   0.30720,  # < 500 km
    'short_haul': 0.25510,  # 500 – 3 699 km
    'long_haul':  0.19510,  # >= 3 700 km
}

# ---------------------------------------------------------------------------
# Hotel stays — kgCO2e per room-night
# No official DEFRA figure; using HCMI (Hotel Carbon Measurement Initiative)
# 2016 global average.  Flag all hotel records for analyst review.
# ---------------------------------------------------------------------------

HOTEL_FACTOR: float = 0.070  # 70 gCO2e per room-night

# ---------------------------------------------------------------------------
# Ground transport — kgCO2e per km (DEFRA 2023)
# ---------------------------------------------------------------------------

GROUND_FACTORS: dict[str, float] = {
    'car_rental': 0.16844,   # average car
    'car rental': 0.16844,
    'taxi':       0.14931,
    'rail':       0.03549,   # national rail UK
    'bus':        0.10312,
    'default':    0.16844,   # fallback = average car
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_air_factor(distance_km: float) -> float:
    """Return the appropriate kgCO2e/passenger-km factor for the flight distance."""
    if distance_km < 500:
        return AIR_FACTORS['domestic']
    elif distance_km < 3700:
        return AIR_FACTORS['short_haul']
    else:
        return AIR_FACTORS['long_haul']


def get_fuel_type_from_description(description: str) -> str:
    """
    Infer fuel type from SAP material description text.

    This is intentionally heuristic — callers should always flag the result
    so an analyst can confirm before the record is approved.
    """
    desc_lower = description.lower()

    if any(k in desc_lower for k in ('diesel', 'hsd', 'hfo', 'gasoil', 'gas oil')):
        return 'diesel'

    if any(k in desc_lower for k in ('petrol', 'gasoline', 'unleaded', 'ms ', 'motor spirit')):
        return 'petrol'

    if any(k in desc_lower for k in ('lpg', 'liquefied petroleum', 'autogas')):
        return 'lpg'

    if any(k in desc_lower for k in ('natural gas', 'cng', 'lng', 'compressed natural')):
        return 'natural_gas_m3'

    # Default with flag — analyst must confirm
    return 'diesel'


def get_electricity_factor(country_code: str) -> float:
    """Return grid emission factor for the given ISO-3166 country code."""
    return ELECTRICITY_FACTORS.get(country_code.upper(), ELECTRICITY_FACTORS['default'])


def get_ground_factor(expense_type: str) -> float:
    """Return ground transport emission factor by expense type string."""
    key = expense_type.lower().strip()
    return GROUND_FACTORS.get(key, GROUND_FACTORS['default'])
