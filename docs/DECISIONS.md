# Decisions

Every ambiguity I resolved, what I chose, and why.

---

## Source 1: SAP — Which export mechanism?

**The options:** IDoc (Intermediate Document), OData service, BAPI, direct table extract (SE16), or scheduled report flat file.

**What I chose:** Scheduled report flat file — specifically simulating the output of SAP Transaction **MB51** (Material Document List) for fuel, and **ME2N** (Purchase Orders by Material) for procurement. Tab-separated or comma-separated, with SAP's internal field names as column headers.

**Why:**

IDocs are SAP's native inter-system document format. They're the right answer for real-time EDI integration between SAP and an external system — but they require the client's SAP team to configure an IDoc partner profile and outbound port, which is a multi-week Basis engagement. No client hands this to an analytics vendor in week one.

OData (via the SAP Gateway or S/4 HANA's standard APIs) is the modern answer and would be correct for a productionized integration. But it requires: (a) the client exposes their Gateway externally or via VPN; (b) OAuth/SAML setup; (c) ongoing API version management as they upgrade. These are procurement and IT security conversations that take months.

BAPIs are function modules callable via RFC. Same access problem.

In practice, what actually happens: the client's SAP functional consultant runs a standard report, exports to spreadsheet/CSV, and emails or SFTPs it. This is ugly, but it's what every ESG data collection project actually deals with in year one. We handle the realistic shape.

**What I'd ask the PM:** Is there an active S/4 HANA OData feed we could negotiate access to? If so, the parser architecture supports swapping the ingestion method while keeping the normalization logic identical — the parser just produces the same dict format.

**Which subset of SAP I'm handling:**
- Fuel: movement types 201 (goods issue to cost center) and 261 (goods issue to production order). These are consumption events. Movement types 101/102 (GR/GR reversal) and 501/502 (transfers) are ignored.
- Procurement: confirmed purchase orders (not requisitions). I'm not computing lifecycle emissions — this is spend-based Scope 3 Category 1 using EEIO factors, which is the correct GHG Protocol approach when product-level LCA data isn't available.
- I'm not handling: payroll (Scope 3 Category 7, employee commuting), capital goods (Category 2), or waste (Category 5). These require different data sources.

---

## Source 2: Utility electricity — Which format?

**The options:** PDF bill parsing, utility portal API (if offered), portal CSV export, Green Button Data XML, Green Button CSV.

**What I chose:** Green Button Data CSV.

**Why:**

PDF parsing is the realistic thing many facilities teams do — they photograph or scan a bill and hand it off. But PDF parsing is unreliable (layout changes per bill, scanned PDFs need OCR), and the information density is high enough (tariff codes, reactive power, taxes vs. base charges) that parsing errors would be hard to detect. Dedicated tools like Camelot or Adobe's Extract API exist for this. In this prototype, we'd need a hard dependency on an OCR service, which is a deployment complexity we're deliberately deferring (see TRADEOFFS.md).

Utility portal APIs: a small number of utilities (mostly US: PG&E, Xcel, etc.) offer OAuth-based Green Button Connect APIs. Most Indian utilities (MSEDCL, BESCOM, TPDDL) do not. This isn't a realistic option for an enterprise with multi-state Indian plants.

Portal CSV export is what facilities managers actually use. The Green Button Data standard is the US NAESB/ANSI ESPI standard that defines exactly what these CSVs should contain. Most major US utilities, and an increasing number of international ones, use this format or a recognizable variant of it.

I chose the Green Button CSV variant over XML because: (a) the CSV is what portal download buttons actually produce in most utility web portals; (b) the XML schema is verbose and requires an XML parser with namespace handling, adding complexity for no analytical benefit; (c) the CSV contains the same data at the interval level.

**What I'd ask the PM:** Which utility providers does this client use, and do they export to Green Button? If not, we need a field mapping exercise per utility — the column names and units vary.

**What I'm handling:** Hourly interval meter data. Not: reactive power (kVAR), power factor, demand charges as a separate line item, time-of-day tariff breakdowns (we store the tariff code but don't use it for emissions — CO2e is consumption-based, not tariff-based).

**The unit problem I'm handling:** Some utility portals export consumption in Wh (watt-hours), some in kWh. I detect this heuristically: if an hourly reading exceeds 10,000 kWh for what appears to be a single industrial meter, I divide by 1000 and flag the record for analyst confirmation.

---

## Source 3: Corporate travel — Which platform and format?

**The options:** Concur API, Navan (TripActions) API, Egencia, file export, manual paste.

**What I chose:** Concur expense export CSV.

**Why:**

Concur (now SAP Concur) holds ~50% of the corporate travel management market, particularly in large enterprises. The company described in this brief — with fuel and procurement in SAP — almost certainly uses SAP Concur for T&E (the products are sold as a bundle). Concur's Expense extract produces a well-documented CSV.

Navan (formerly TripActions) is growing fast but skews toward tech companies and newer enterprises. Its export format is less standardized and the API docs are behind a partnership agreement.

API integration for either platform is the right long-term answer, but requires OAuth app registration with the travel platform, which needs IT security approval and can take weeks. CSV export is what a sustainability lead can do today.

**What I'd ask the PM:** Does the client use Concur, Navan, or something else? If Concur, do they have the Intelligence Reporting module, or just standard expense exports?

**The distance problem:**

Flights are reported as city pairs (BOM → DEL), not distances. Airlines don't include distance in expense data. I calculate great-circle distance using the haversine formula from IATA airport coordinates (stored as a lookup dictionary for ~50 major airports). This produces an underestimate (actual flight paths are longer by 8–12%). DEFRA and GHG Protocol both recommend this approach for Scope 3 Category 6 calculations when actual route data isn't available.

For airport codes not in our lookup table, the record is ingested with co2e_kg = 0 and flagged with `distance_unavailable = True`. The analyst must manually provide the distance before the record can be approved.

**What I'm handling:** Air, hotel, car rental, taxi, rail, bus. Not: private aviation (different factors entirely), freight forwarding billed to travel (Scope 3 Category 4, not 6), personal car mileage reimbursement (would need a separate mileage claim report).

---

## Ingestion mechanism per source

| Source | Mechanism | Why |
|---|---|---|
| SAP Fuel | File upload (CSV) | No API access; file export is the realistic delivery mode |
| SAP Procurement | File upload (CSV) | Same |
| Utility Electricity | File upload (CSV) | Portal export; no real-time API for most Indian utilities |
| Corporate Travel | File upload (CSV) | Expense exports are available immediately; API needs OAuth setup |

All three use the same upload UI pattern (multipart POST to `/api/upload/<source_type>/`). The source type determines which parser and normalizer runs.

---

## Multi-tenancy approach

FK-based row-level filtering, enforced in the application layer. Every queryset in every view applies `filter(company=request.user.company)`.

**Why not database row-level security (RLS)?** RLS in PostgreSQL is the correct production choice — it enforces at the DB layer so a missed view filter can't leak data. But Django's ORM doesn't integrate cleanly with RLS without custom middleware. For a prototype evaluated on data model design, not infrastructure security, FK filtering is simpler and sufficient.

**What I'd ask the PM:** Do we need cross-company reporting (e.g., a portfolio view for the Breathe ESG analyst who manages multiple clients)? If yes, we need a separate superuser role that isn't scoped to a company, and the data model needs a `is_internal_admin` flag.

---

## Emission factor sources

| Category | Source | Year | Notes |
|---|---|---|---|
| Fuel combustion | DEFRA Conversion Factors | 2023 | Used for diesel, petrol, LPG |
| Electricity (India) | CEA CO2 Baseline | 2022 | 0.716 kgCO2e/kWh national grid average |
| Electricity (UK) | DEFRA | 2023 | 0.23314 kgCO2e/kWh |
| Electricity (US) | EPA eGRID | 2022 | 0.386 kgCO2e/kWh national average |
| Business travel air | DEFRA | 2023 | Includes radiative forcing index (RFI) |
| Hotel | HCMI Hotel Carbon Measurement Initiative | 2016 | No DEFRA equivalent; industry standard |
| Ground transport | DEFRA | 2023 | Average car/taxi/rail/bus |
| Purchased goods | EEIO US model | 2021 | Spend-based, ~0.5 kgCO2e/USD for industrial goods |

The EEIO (Environmentally Extended Input-Output) spend-based factor for procurement is a rough approximation. The GHG Protocol Scope 3 standard acknowledges this is the lowest-quality but most accessible method. All procurement records are auto-flagged with `spend_based_factor = True` to ensure an analyst reviews them before audit submission.

---

## What I would ask the PM before committing to production

1. **Which Indian grid zone is this client on?** CEA publishes state-level and regional grid emission factors (ranging from 0.65 to 0.82 kgCO2e/kWh). National average understates emissions for coal-heavy states like UP.
2. **Does the client have renewable energy procurement (RECs/CPPAs)?** If yes, Scope 2 should use market-based accounting, not location-based.
3. **What's the reporting boundary?** Operational control or equity share? This affects which plant codes are in scope.
4. **Is Scope 3 procurement required for year one?** BRSR Core (India's mandatory ESG reporting) and GRI don't require Category 1 in the first year. It might be out of scope.
5. **What audit standard applies?** ISO 14064-3, ISAE 3410, or something else? This affects what the "locked" state needs to produce as output.
