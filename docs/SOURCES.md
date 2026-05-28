# Sources

For each of the three data sources: what I researched, what I learned, what the sample data looks like and why, and what would break in a real deployment.

---

## Source 1: SAP Fuel and Procurement

### What I researched

SAP's data model for materials and procurement is built around a few core modules:
- **MM (Materials Management):** Purchase orders, goods receipts, goods issues, inventory management
- **FI/CO (Finance/Controlling):** Cost center accounting, internal orders

For fuel tracking, the relevant transaction is **MB51** (Material Document List). This shows all material movements — including goods issues (consumption) — for a given material, plant, and date range. Movement types determine what happened:
- `201`: Goods issue to cost center (direct consumption from warehouse)
- `261`: Goods issue to production order (consumption for manufacturing)
- `551`: Scrapping
- `101/102`: Goods receipt / reversal (not consumption events — excluded)

For procurement, **ME2N** (Purchase Orders by Material or Account Assignment) shows all purchase orders, filterable by plant, vendor, material, and date. This is the most common report used for Scope 3 Category 1 data collection.

The column headers in SAP exports use **SAP field names** (BUDAT, WERKS, MATNR, MENGE, MEINS, etc.). German installations may show German labels ("Buchungsdatum" for posting date, "Werk" for plant, "Menge" for quantity). The SAP internal names are the same regardless of language; the display text is configurable.

**Units in SAP are stored as SAP-specific codes:** `L` (liters), `KG` (kilograms), `M3` (cubic meters), `TO` (metric tons), `GAL` (gallons), `ST` (pieces/each), `M` (meters). These are ISO units but with SAP's specific capitalization and shorthand.

**Date format:** SAP stores dates as `YYYYMMDD` internally. Exports via SE16N show this format. Exports via ALV report viewer may show DD.MM.YYYY depending on user locale settings. Our parser handles both.

### What I learned

The hardest part of SAP fuel data is **material classification**. SAP doesn't have a "fuel type" field — you know a material is diesel because its short text (MAKTX) says "Diesel HSD IS 1460." Different clients use different material master descriptions. Some use codes (MAT-001 with no description), some use full IS/BIS standard names, some use informal names ("genny diesel"). The parser must infer fuel type from the description using keyword matching, and flag records where inference is uncertain.

Plant codes (WERKS) are four-character alphanumeric codes like `1000`, `2000`, `3010`, `MUMB`. They mean nothing to anyone outside the client's SAP team. Without a plant-to-location lookup table (which we ask the client to provide separately), we can't assign a geographic grid emission factor to each plant for Scope 2 calculations.

### What my sample data looks like and why

The fuel sample (`sap_fuel_mb51.csv`) has:
- 25 rows, three plants (1000, 2000, 3010, 4000)
- Three fuel types: diesel (HSD), petrol (MS), LPG, CNG
- Units L (liters), KG (for LPG by weight), M3 (for natural gas)
- Movement types 201 and 261
- SAP field names as column headers
- One deliberate outlier: row 4900012318 has 14,500 liters — roughly 3× the average — to trigger the statistical outlier flag
- Date format: YYYYMMDD (SAP internal)
- INR currency (client is India-based)

The procurement sample (`sap_procurement_me2n.csv`) has:
- 20 rows across industrial goods categories (packaging, chemicals, lubricants, electrical, steel)
- Realistic Indian vendors and materials with IS standard references
- Mix of materials that are high-emission (steel, chemicals) and lower (packaging)
- Two line items on one PO (4500098702) to test multi-line parsing

### What would break in a real deployment

1. **Material descriptions vary wildly.** "Diesel HSD IS 1460" in one client's SAP might be "HSD Fuel – Generator" or just "DIESEL-GEN" in another's. The keyword matching for fuel type inference needs a client-specific calibration pass.

2. **Plant codes need a lookup.** Without a table mapping WERKS → (plant name, city, country, grid zone), the Scope 2 calculation uses a national grid average. Scope 1 records can't be geographically attributed for regional reporting.

3. **Currency conversion.** SAP exports amounts in the company code currency. For group-level carbon accounting across geographies, you need FX rates. We don't do any currency-based calculations (we use spend-based EEIO factors for procurement), but if we ever move to product-specific LCA factors, currency becomes relevant.

4. **File encoding.** SAP exports can be UTF-8, Latin-1 (ISO-8859-1), or Windows-1252 depending on the SAP system's locale. We handle this by trying UTF-8 first, then Latin-1.

5. **German column headers.** Some SAP configurations export with German field labels. We handle a predefined set of aliases, but a client with a custom SAP variant might have column names we don't recognize.

---

## Source 2: Utility Data — Electricity

### What I researched

The **Green Button Data (GBD)** standard is the US NAESB/ANSI ESPI (Energy Services Provider Interface) standard, originally developed in 2011 as part of a White House initiative. It defines a standard format for utilities to provide consumption data to customers. Key specs:

- **Green Button Download My Data:** User downloads their own data from the utility portal. XML (ESPI schema) or CSV.
- **Green Button Connect My Data:** Third-party app pulls data via OAuth API. Requires utility to implement the server side.
- **Coverage:** 60+ US utilities (PG&E, ConEd, National Grid, Xcel, etc.), adopted voluntarily by Canadian and some international utilities.

For Indian utilities (MSEDCL, BESCOM, TPDDL, CESC, etc.), there is no Green Button standard. However, all major Indian utilities with smart metering programs (AMISP rollout under RDSS) provide portal CSV downloads that contain the same information in a similar structure. We use the Green Button column names because they're the most standardized reference point.

**Data granularity:** Smart meters report at 15-minute or 30-minute intervals. Older interval meters report hourly. Billing meters (the most common type for industrial customers in India) report daily or monthly totals. We assume interval-level data (hourly), which is what industrial/HV customers typically have.

**Tariff codes** are utility-specific. MSEDCL's HV tariff codes include TOD-HV-PEAK (peak hours), TOD-HV-OFF (off-peak), and the differential matters for billing but not for emissions calculation. CO2e is based on consumption, not tariff.

### What I learned

The billing period problem: utility bills cover a billing period, not a calendar month. MSEDCL bills on a 30–35 day cycle that doesn't align with January 1. When you aggregate electricity consumption by month for ESG reporting, you need to attribute consumption to calendar months, not billing periods. With interval data this is trivial (sum all readings within the calendar month). With monthly billing totals, you need to pro-rate.

**Demand vs. consumption:** The export includes both consumption (kWh, what we care about for emissions) and peak demand (kW, what drives demand charges in billing). We ingest consumption only; demand is stored but not used in emission calculations.

### What my sample data looks like and why

The utility sample (`utility_greenbutton.csv`) has:
- Two service points / meters at the same facility (SP-MH-001-A is the HV industrial meter, SP-MH-001-B is the LT industrial meter)
- Hourly intervals across Jan–Mar 2024
- Missing hours (intentional — meters don't report every hour in real systems; data gaps are normal)
- Realistic load curve: low consumption at night (130–150 kWh/hr), ramp up from 7am, peak 10am–12pm (~310 kWh/hr), taper in afternoon
- Two tariff codes: TOD-HV-PEAK and TOD-HV-OFF (realistic for Maharashtra HV tariff)
- Cost in USD (even for an India-based client) to test currency handling

### What would break in a real deployment

1. **Non-Green Button utilities.** Every Indian state utility has a different portal CSV format. BESCOM's CSV has different column names than MSEDCL's. We'd need per-utility column mapping configuration.

2. **Data gaps.** Meters go offline, communication fails, and readings are missed. Our parser handles missing rows gracefully, but gap detection (flagging a period where we have zero readings) requires knowing the expected interval frequency — we don't model that.

3. **Cumulative vs. interval readings.** Some meters report cumulative register readings (like a gas meter — today's value minus yesterday's = consumption). Green Button's `Read Type` field distinguishes these, but not all exports set this correctly. If we naively sum cumulative readings as if they're interval readings, we massively overcount.

4. **Unit ambiguity (Wh vs kWh).** We detect and handle this heuristically, but the heuristic can fail for very large industrial consumers (>10 MW) where 10,000+ kWh per hour is possible.

---

## Source 3: Corporate Travel

### What I researched

**SAP Concur** is the dominant corporate travel and expense management platform (used by ~47% of Fortune 500). Its Expense module processes expense reports submitted by employees. The standard Concur **Expense Extract** or **Expense Report Detail Report** produces a CSV/Excel with one row per expense line item.

I reviewed the [Concur Expense Extract documentation](https://developer.concur.com/api-reference/expense/expense-report/v3.reports.html) and the standard report schema. Key fields:
- Report-level: Report Name, Report ID, Employee, Submission Date
- Line-level: Transaction Date, Expense Type, Vendor, Amount, Currency

**Expense Types** in Concur are configurable per client. Standard types relevant to carbon:
- `01` / "Air" or "Airfare"
- `02` / "Hotel" or "Lodging"
- `03` / "Car Rental" or "Auto Rental"
- `07` / "Taxi" or "Ground Transportation"
- `11` / "Rail" or "Train"
- `12` / "Bus"

The city/airport for flights is often stored in the booking detail, not the expense line item. Concur's travel booking data (itinerary) and expense data (reimbursement) are separate — an expense report may just show "Air — $450" with no routing. The routing comes from the connected travel booking, which requires Concur Travel (not just Concur Expense) and API access to the itinerary endpoint.

**Navan (TripActions):** Growing fast, used by many tech companies. Exports to Excel. No publicly documented CSV schema. Would require a discovery call with their integrations team.

### What I learned

The hardest problem in travel data is distance for flights. Options:
1. **From the booking:** If the client has Concur Travel (not just Expense), the itinerary contains the flight segments with routing. Requires API access.
2. **From IATA airport codes:** Map city codes to coordinates and compute haversine distance. This is what we do.
3. **From a flight database:** Services like OAG or Cirium publish actual route distances. Expensive.

The haversine formula gives great-circle distance (straight line through the Earth's surface). Actual flight paths are longer by 8–12% due to routing, airways, and weather. DEFRA and GHG Protocol both document that great-circle + a routing factor of 1.08 is acceptable for Scope 3 Category 6.

**Hotel emission factors** are poorly standardized. The HCMI (Hotel Carbon Measurement Initiative) publishes a global average of ~70gCO2e per occupied room-night, but this varies enormously by hotel class (budget vs. luxury), region (coal-heavy vs. hydro-heavy grid), and property vintage. For a prototype, we use the global average and flag all hotel records for analyst review.

### What my sample data looks like and why

The travel sample (`concur_travel_export.csv`) has:
- 33 rows from 5 employees across Q1 2024
- Mix of domestic India (BOM↔DEL, BOM↔HYD, DEL↔BLR, DEL↔CCU), international short-haul (BOM↔DXB, BOM↔SIN), and long-haul (BOM↔LHR, BOM↔JFK, BOM↔FRA)
- Hotels with room-nights specified
- Ground transport (taxi, car rental) with distance in km
- Rail (Deutsche Bahn FRA↔MUC, 304 km actual distance)
- Multi-leg itinerary (BOM→DXB→JFK) showing that connecting flights must be split
- One route (FRA→MUC) where both city codes are in the airport lookup, one (MUC→BOM) where distance is computable, and the rail leg has an explicit distance — tests all three path in the distance calculation

The INR amounts are realistic for 2024 Indian corporate travel pricing. Dollar/Euro amounts would require FX conversion if we were doing cost-per-tonne analysis (we're not, for now).

### What would break in a real deployment

1. **Expense type names vary by client.** Concur expense types are configurable — what one client calls "Air" another calls "Airfare" or "01 - Domestic Air". Our parser normalizes to a standard set, but unknown types silently default to "other" and produce zero emissions. These should be flagged for the analyst to classify.

2. **Airport codes outside our lookup table.** We include ~50 major airports. A flight to Ahmedabad (AMD) or Goa (GOI) from a mid-sized Indian company's travel data would hit an unknown code, set co2e = 0, and flag the record. Production needs a full IATA database (14,000+ airports) — freely available from OpenFlights.org.

3. **Missing City From/To for flights.** Some Concur configurations only store the city name, not the airport code (e.g., "Mumbai" vs "BOM"). Name-to-IATA resolution is an NLP/fuzzy-matching problem.

4. **Multi-leg journeys.** A BOM→DXB→JFK booking might appear as one expense line item with the total fare, but two legs each with different emission factors. We handle this only if the connecting city is explicitly listed as a separate row. If the client exports only origin-destination (BOM→JFK), we'll use a long-haul factor for the whole trip — which is close to correct but not exact.

5. **Non-Concur platforms.** About 30% of large enterprises use something other than SAP Concur (Navan, Egencia, Emburse, TravelBank). Each has a different export format. A production system needs a travel platform adapter layer.
