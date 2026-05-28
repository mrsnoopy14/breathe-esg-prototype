"""
Normalization service.

Each public function takes a parsed row (dict) from one of the parsers and
returns a dict of EmissionRecord field values ready to be passed to
EmissionRecord(**fields).  Records are NOT saved here — that is the
responsibility of the view so it can also create AuditLog and DataIngestion
updates atomically.

Design note: we return plain dicts rather than model instances so that the
flagging service can examine the values before the record hits the database.
"""

from datetime import date
from decimal import Decimal

from ingestion.services.emission_factors import (
    FUEL_FACTORS,
    FUEL_UNIT_TO_LITERS,
    HOTEL_FACTOR,
    get_air_factor,
    get_electricity_factor,
    get_fuel_type_from_description,
    get_ground_factor,
)
from ingestion.parsers.travel import airport_distance_km


# ---------------------------------------------------------------------------
# SAP Fuel (MB51)
# ---------------------------------------------------------------------------

def normalize_sap_fuel_record(parsed_row: dict, company) -> dict:
    """
    Convert a SAP fuel consumption row to EmissionRecord field values.

    Normalizes quantity to liters, infers fuel type from material description,
    looks up the DEFRA 2023 emission factor, and returns a dict ready to
    unpack into EmissionRecord(**…).
    """
    quantity = parsed_row['quantity']  # already a Decimal from parser
    raw_unit = parsed_row['unit']
    description = parsed_row.get('material_description', '')

    # ---- Unit normalization ------------------------------------------------
    conversion = FUEL_UNIT_TO_LITERS.get(raw_unit.lower())
    if conversion is not None:
        normalized_quantity = quantity * Decimal(str(conversion))
        normalized_unit = 'liters'
    elif raw_unit.lower() in ('kg', 'tonnes'):
        # Without density we can't convert to liters.
        # Use per-kg factor directly and keep units as-is.
        normalized_quantity = quantity
        normalized_unit = raw_unit.lower()
    else:
        normalized_quantity = quantity
        normalized_unit = raw_unit

    # ---- Fuel type + factor ------------------------------------------------
    fuel_type = get_fuel_type_from_description(description)

    # Select the right factor key for kg/tonne inputs
    if raw_unit.lower() == 'kg':
        factor_key = f'{fuel_type}_kg' if f'{fuel_type}_kg' in FUEL_FACTORS else fuel_type
    elif raw_unit.lower() == 'tonnes':
        factor_key = f'{fuel_type}_kg' if f'{fuel_type}_kg' in FUEL_FACTORS else fuel_type
        # Convert tonnes → kg for factor lookup
        if normalized_unit == 'tonnes':
            normalized_quantity = normalized_quantity * Decimal('1000')
            normalized_unit = 'kg'
    else:
        factor_key = fuel_type

    emission_factor = FUEL_FACTORS.get(factor_key, FUEL_FACTORS['diesel'])
    co2e_kg = normalized_quantity * Decimal(str(emission_factor))

    return {
        'company': company,
        'scope': 1,
        'category': 'fuel_combustion',
        'activity_date': parsed_row['posting_date'],
        'description': description,
        'raw_quantity': quantity,
        'raw_unit': raw_unit,
        'normalized_quantity': normalized_quantity.quantize(Decimal('0.0001')),
        'normalized_unit': normalized_unit,
        'co2e_kg': co2e_kg.quantize(Decimal('0.0001')),
        'emission_factor': Decimal(str(emission_factor)),
        'emission_factor_source': 'DEFRA_2023',
        'source_plant_code': parsed_row.get('plant_code', ''),
        'source_record_id': parsed_row.get('document_number', ''),
        'source_material': description,
        'raw_source_data': {
            k: str(v) if isinstance(v, (Decimal, date)) else v
            for k, v in parsed_row.items()
        },
        # Flags set by calling code after normalization
        '_fuel_type_inferred': True,  # always flag — analyst must confirm
    }


# ---------------------------------------------------------------------------
# Utility electricity (Green Button)
# ---------------------------------------------------------------------------

def normalize_utility_record(parsed_row: dict, company, country_code: str = 'IN') -> dict:
    """
    Convert a Green Button electricity row to EmissionRecord field values.

    consumption_kwh is already the normalized quantity.
    Emission factor is the grid intensity for the given country.
    """
    consumption_kwh = parsed_row['consumption_kwh']
    emission_factor = get_electricity_factor(country_code)
    co2e_kg = consumption_kwh * Decimal(str(emission_factor))

    return {
        'company': company,
        'scope': 2,
        'category': 'purchased_electricity',
        'activity_date': parsed_row['interval_start'],
        'description': f"Electricity meter {parsed_row.get('meter_id', '')} {parsed_row.get('meter_number', '')}".strip(),
        'raw_quantity': consumption_kwh,
        'raw_unit': 'kWh',
        'normalized_quantity': consumption_kwh,
        'normalized_unit': 'kWh',
        'co2e_kg': co2e_kg.quantize(Decimal('0.0001')),
        'emission_factor': Decimal(str(emission_factor)),
        'emission_factor_source': f'GRID_{country_code.upper()}_2023',
        'source_meter_id': parsed_row.get('meter_id', ''),
        'raw_source_data': {
            k: str(v) if isinstance(v, (Decimal, date)) else v
            for k, v in parsed_row.items()
        },
        '_wh_converted': parsed_row.get('wh_converted', False),
    }


# ---------------------------------------------------------------------------
# Travel (Concur)
# ---------------------------------------------------------------------------

# Map Concur expense_type strings to EmissionRecord category values
_TRAVEL_CATEGORY_MAP: dict[str, str] = {
    'air':         'business_travel_air',
    'flight':      'business_travel_air',
    'airline':     'business_travel_air',
    'hotel':       'business_travel_hotel',
    'lodging':     'business_travel_hotel',
    'accommodation': 'business_travel_hotel',
    'car rental':  'business_travel_ground',
    'car hire':    'business_travel_ground',
    'taxi':        'business_travel_ground',
    'cab':         'business_travel_ground',
    'uber':        'business_travel_ground',
    'lyft':        'business_travel_ground',
    'rail':        'business_travel_ground',
    'train':       'business_travel_ground',
    'bus':         'business_travel_ground',
    'ground':      'business_travel_ground',
    'metro':       'business_travel_ground',
}


def _classify_travel(expense_type: str) -> str:
    return _TRAVEL_CATEGORY_MAP.get(expense_type.lower().strip(), 'business_travel_ground')


def normalize_travel_record(parsed_row: dict, company) -> dict:
    """
    Convert a Concur travel expense row to EmissionRecord field values.

    - Air: attempts IATA distance lookup; flags if unavailable.
    - Hotel: normalized_unit = 'room_nights'; quantity from Concur field.
    - Ground: normalized_unit = 'km'; uses quantity if provided, else 0 (flagged).
    """
    expense_type = parsed_row.get('expense_type', '')
    category = _classify_travel(expense_type)

    activity_date = parsed_row['transaction_date']
    amount = parsed_row.get('amount', Decimal('0'))
    quantity = parsed_row.get('quantity')  # may be None
    unit = parsed_row.get('unit', '')
    city_from = parsed_row.get('city_from', '')
    city_to = parsed_row.get('city_to', '')

    distance_unavailable = False
    co2e_kg = Decimal('0')
    emission_factor_value = Decimal('0')
    emission_factor_source = 'DEFRA_2023'
    normalized_quantity = quantity or Decimal('0')
    normalized_unit = unit or 'unknown'

    if category == 'business_travel_air':
        # Try airport code distance
        distance_km = airport_distance_km(city_from, city_to)

        if distance_km is not None:
            factor = get_air_factor(distance_km)
            # quantity in Concur air = number of passengers (usually blank = 1)
            passengers = float(quantity) if quantity else 1.0
            normalized_quantity = Decimal(str(round(distance_km * passengers, 4)))
            normalized_unit = 'passenger_km'
            emission_factor_value = Decimal(str(factor))
            co2e_kg = (normalized_quantity * emission_factor_value).quantize(Decimal('0.0001'))
        else:
            # Can't compute distance — zero CO2e, flag for manual entry
            distance_unavailable = True
            normalized_unit = 'passenger_km'
            normalized_quantity = Decimal('0')
            co2e_kg = Decimal('0')
            emission_factor_value = Decimal('0')

    elif category == 'business_travel_hotel':
        # quantity = number of room-nights
        room_nights = quantity if quantity else Decimal('1')
        normalized_quantity = room_nights
        normalized_unit = 'room_nights'
        emission_factor_value = Decimal(str(HOTEL_FACTOR))
        co2e_kg = (normalized_quantity * emission_factor_value).quantize(Decimal('0.0001'))
        emission_factor_source = 'HCMI_2016'

    else:
        # Ground transport — quantity may be km or absent
        ground_type_key = expense_type.lower().strip()
        factor = get_ground_factor(ground_type_key)
        emission_factor_value = Decimal(str(factor))
        normalized_unit = 'km'

        if quantity and float(quantity) > 0:
            normalized_quantity = quantity
            co2e_kg = (normalized_quantity * emission_factor_value).quantize(Decimal('0.0001'))
        else:
            # No distance available — zero CO2e, flag
            distance_unavailable = True
            normalized_quantity = Decimal('0')
            co2e_kg = Decimal('0')

    return {
        'company': company,
        'scope': 3,
        'category': category,
        'activity_date': activity_date,
        'description': f"{expense_type} | {city_from} → {city_to}".strip(' |→'),
        'raw_quantity': quantity or Decimal('0'),
        'raw_unit': unit or 'unknown',
        'normalized_quantity': normalized_quantity.quantize(Decimal('0.0001')),
        'normalized_unit': normalized_unit,
        'co2e_kg': co2e_kg,
        'emission_factor': emission_factor_value,
        'emission_factor_source': emission_factor_source,
        'source_vendor': parsed_row.get('vendor_name', ''),
        'source_record_id': parsed_row.get('report_name', ''),
        'raw_source_data': {
            k: str(v) if isinstance(v, (Decimal, date)) else v
            for k, v in parsed_row.items()
        },
        '_distance_unavailable': distance_unavailable,
    }


# ---------------------------------------------------------------------------
# SAP Procurement (ME2N) — Scope 3 Category 1
# ---------------------------------------------------------------------------

# EEIO average spend-based factor for industrial goods (kgCO2e per USD)
_PROCUREMENT_EEIO_FACTOR = Decimal('0.5')


def normalize_sap_procurement_record(parsed_row: dict, company) -> dict:
    """
    Convert a SAP procurement row to EmissionRecord field values.

    Uses a spend-based EEIO factor (0.5 kgCO2e/USD) which is a rough proxy.
    ALL procurement records are flagged as needing review.

    If currency is not USD, we cannot convert without FX rates, so we apply
    the factor directly to the recorded amount (still flagged as approximate).
    """
    net_price = parsed_row.get('net_price', Decimal('0'))
    quantity = parsed_row.get('quantity', Decimal('1'))
    price_unit = parsed_row.get('price_unit', Decimal('1'))
    currency = parsed_row.get('currency', 'USD')

    # Total spend = (net_price / price_unit) * quantity
    if price_unit and float(price_unit) > 0:
        unit_price = net_price / price_unit
    else:
        unit_price = net_price

    total_spend = unit_price * quantity

    co2e_kg = (total_spend * _PROCUREMENT_EEIO_FACTOR).quantize(Decimal('0.0001'))

    return {
        'company': company,
        'scope': 3,
        'category': 'purchased_goods',
        'activity_date': parsed_row['po_date'],
        'description': parsed_row.get('short_text', ''),
        'raw_quantity': quantity,
        'raw_unit': parsed_row.get('unit', 'unit'),
        'normalized_quantity': total_spend.quantize(Decimal('0.0001')),
        'normalized_unit': currency,  # spend is the proxy activity unit
        'co2e_kg': co2e_kg,
        'emission_factor': _PROCUREMENT_EEIO_FACTOR,
        'emission_factor_source': 'EEIO_SPEND_BASED',
        'source_plant_code': parsed_row.get('plant_code', ''),
        'source_vendor': parsed_row.get('vendor_name', ''),
        'source_material': parsed_row.get('short_text', ''),
        'source_record_id': parsed_row.get('po_number', ''),
        'raw_source_data': {
            k: str(v) if isinstance(v, (Decimal, date)) else v
            for k, v in parsed_row.items()
        },
        '_spend_based_factor': True,  # always flag
    }
