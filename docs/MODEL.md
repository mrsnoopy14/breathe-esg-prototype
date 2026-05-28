# Data Model

## Overview

The model has three layers: tenancy (who owns data), provenance (where data came from and when), and the normalized emission record itself. These are separate concerns and kept separate.

---

## Tables

### Company

The tenant anchor. Every record in the system belongs to a Company. This is the multi-tenancy boundary — every query is scoped with `WHERE company_id = ?`.

We chose simple FK-based tenancy over schema-per-tenant (PostgreSQL schemas) because:
- Schema-per-tenant breaks Django's ORM without significant middleware work
- At prototype scale with < 100 clients, FK filtering is fast with a proper index
- It keeps migrations simple — one `migrate` serves all tenants

What we don't do: row-level security in the database layer. That's a valid production choice (especially with PostgREST or Supabase) but adds complexity the prototype doesn't need.

---

### User

`AbstractUser` extended with `company` FK and `role`. Role is either ANALYST or ADMIN.

The only two access patterns that matter:
1. All users can only see their own company's data (enforced in every view's queryset)
2. ANALYST can approve/reject records; ADMIN can do everything including locking

We don't implement field-level permissions. An analyst can see emission factors, raw source data, etc. The assumption is that all users are internal and trusted — the access boundary is between companies, not within them.

---

### DataIngestion

Represents one file upload. Immutable once created. Fields:

| Field | Why |
|---|---|
| `source_type` | Discriminates parser and downstream Scope/category defaults |
| `original_filename` | Audit trail — what the client actually sent |
| `file` | Stored in media storage; never deleted (audit evidence) |
| `uploaded_by` | Who ingested it |
| `uploaded_at` | When |
| `status` | QUEUED → PROCESSING → COMPLETED or FAILED |
| `row_count` | Total rows parsed from file |
| `parsed_count` | Rows that produced EmissionRecords |
| `error_count` | Rows that failed parsing |
| `error_log` | JSON array of {row_number, raw_line, error_message} |

The file is kept even after processing because in an audit, the auditor may ask "show me the original file this number came from." Deleting uploads destroys that evidence trail.

`error_log` is JSON rather than a separate table because: (a) it's only ever read as a whole batch attached to its ingestion, never queried individually; (b) keeping it as JSON avoids a join for the common display case.

---

### EmissionRecord

The central table. One row = one discrete emission activity event.

The key design tension: raw source data vs. normalized data. We store both, separated clearly:

**Raw (immutable once ingested):**
- `raw_quantity`, `raw_unit` — exactly as it came from the source file
- `raw_source_data` — the entire original row as JSON

This exists because: (1) if our emission factor or unit conversion was wrong, we can reprocess without re-uploading; (2) auditors may want to trace a CO2e figure back to the exact source value.

**Normalized:**
- `normalized_quantity`, `normalized_unit` — converted to the base unit for the category
- `co2e_kg` — the calculated output

Base units per category:
- `fuel_combustion` → liters (diesel, petrol, LPG; natural gas normalized to liter-equivalent)
- `purchased_electricity` → kWh
- `business_travel_air` → passenger-km (great-circle × 1.08 routing factor, not straight-line)
- `business_travel_hotel` → room-nights
- `business_travel_ground` → km
- `purchased_goods` → USD spend (EEIO spend-based approach)

**Emission calculation fields:**
- `emission_factor` — the value used (kgCO2e per normalized unit)
- `emission_factor_source` — provenance of the factor (e.g., `DEFRA_2023`, `CEA_2022`, `EEIO_SPEND_BASED`)

These are stored per-record rather than looked up dynamically because: emission factor databases are updated annually; an approved record locked for audit must use the factor that was current when it was processed, not whatever's in the lookup table today.

**Source metadata:**
- `source_plant_code` — SAP WERKS; required for Scope 1 spatial attribution
- `source_meter_id` — utility meter number; links back to a physical asset
- `source_record_id` — the original row identifier (SAP document number, etc.)
- `source_vendor`, `source_material` — SAP procurement metadata

**Review workflow fields:**
- `status`: PENDING → APPROVED or REJECTED (or FLAGGED → PENDING/APPROVED/REJECTED)
- `flags`, `flag_reasons`: what the system detected automatically
- `reviewed_by`, `reviewed_at`, `review_note`: who signed off and why
- `is_locked`: set to True after the period is locked for audit export. Locked records cannot be edited or re-reviewed.

**Edit tracking:**
- `is_edited` — quick boolean filter for "show me everything an analyst changed"
- `edit_history` — JSON array of `{field, old_value, new_value, changed_by, changed_at}`

We store edit history in JSON rather than a separate table for the same reason as error_log: it's always displayed with the record, not queried in isolation.

---

### AuditLog

Append-only. One row per action on any EmissionRecord. Actions: INGESTED, APPROVED, REJECTED, FLAGGED, EDITED, LOCKED.

`before_state` and `after_state` are JSON snapshots of the relevant fields. This means we can reconstruct the full history of any record without relying on edit_history (which is on the record itself and could theoretically be corrupted).

We don't soft-delete or update AuditLog rows. Ever. The application code never issues UPDATE or DELETE against this table.

---

## Scope Classification Logic

| Source | Activity | Scope | Category |
|---|---|---|---|
| SAP MB51 (fuel) | Diesel/petrol/LPG combustion at company-owned plant | 1 | fuel_combustion |
| SAP MB51 (fuel) | Natural gas consumption | 1 | fuel_combustion |
| Utility Green Button | Grid electricity purchased | 2 | purchased_electricity |
| Concur Export | Flights | 3 | business_travel_air |
| Concur Export | Hotels | 3 | business_travel_hotel |
| Concur Export | Car rental / taxi / bus | 3 | business_travel_ground |
| Concur Export | Rail | 3 | business_travel_ground |
| SAP ME2N | Purchased goods & materials | 3 | purchased_goods |

Scope 1 applies only when the company directly owns or controls the combustion asset (i.e., their plant). If SAP goods issues go to a third-party vendor's cost center, that would be Scope 3 — but distinguishing this would require a plant ownership lookup table that we don't have in the prototype. We flag all plant codes we can't confirm as owned, for analyst review.

---

## Multi-tenancy Security

Every ListAPIView and RetrieveAPIView applies `queryset = Model.objects.filter(company=request.user.company)`. This is enforced at the view layer, not the ORM layer. For production, this should be a custom manager or row-level security policy in PostgreSQL — a single missed filter would expose one tenant's data to another. We document this as a known gap (see TRADEOFFS.md).

---

## What the Model Does Not Handle

- **Multiple reporting periods / locking periods**: The `is_locked` flag is per-record. A real system would have a `ReportingPeriod` table with a status that locks all records within it. We chose to omit this (see TRADEOFFS.md).
- **Emission factor versioning**: Factors are stored as a value + source string, not a FK to a `EmissionFactor` table. Reprocessing with a new year's factors requires a migration or management command.
- **Plant-to-asset mapping**: `source_plant_code` stores the raw SAP WERKS code. A production system would join this to an `Asset` table with location, asset type, and ownership metadata.
- **Market-based Scope 2**: We store location-based electricity emissions only. Market-based (using supplier EACs/RECs) requires contract data we don't ingest.
