# Tradeoffs

Three things I deliberately did not build, and why.

---

## 1. Async file processing (Celery + Redis)

**What I built instead:** Synchronous file parsing in the request-response cycle. Upload a file → parser runs → records are saved → response returns with counts.

**What I gave up:** For large files (a quarterly SAP extract might have 50,000 rows), the upload request will time out at most hosting providers (30–60 seconds). The user gets no progress feedback during processing.

**Why I made this tradeoff:**

The correct architecture is: file upload saves the file and creates a `DataIngestion` record in status `QUEUED`, then a Celery worker picks it up asynchronously, and the frontend polls or subscribes via WebSocket for status updates.

But Celery requires Redis or RabbitMQ as a broker. That's a second managed service on Render/Railway, adds $7–15/month to the deployment cost, requires worker dyno configuration, and adds ~200 lines of task queue scaffolding. For files up to a few thousand rows (which is realistic for a quarterly upload from a mid-sized client), synchronous processing under 10 seconds is fine.

**What breaks in production:** Any file over ~5,000 rows. The fix is well-understood — add Celery, change the upload view to enqueue a task instead of running inline, add a polling endpoint. The `DataIngestion.status` field already has `QUEUED` and `PROCESSING` states specifically to support this transition.

---

## 2. PDF utility bill parsing

**What I built instead:** CSV-only ingestion for utility data (Green Button format).

**What I gave up:** The realistic scenario for many facilities teams is that they receive utility bills as PDFs — either scanned paper bills or portal-generated PDFs. A PDF parser would let them upload the bill directly rather than first downloading a CSV from the portal.

**Why I made this tradeoff:**

PDF parsing for utility bills is genuinely hard. The layout of a bill from MSEDCL (Maharashtra) looks nothing like one from BESCOM (Bangalore) or PG&E (US). Each utility has a different layout, different line items (base rate, fuel adjustment charge, regulatory surcharge, etc.), and different formatting for meter readings. A robust parser requires:

1. A layout-detection layer (which utility is this?)
2. A table extractor (Camelot, pdfplumber, or Adobe Extract API)
3. Per-utility field mapping rules
4. OCR for scanned bills (Tesseract or a commercial service)

That's a substantial sub-project with its own model (a `UtilityBillTemplate` table mapping utility names to extraction rules). Tools like Sensible.io or Textract + custom templates exist for exactly this. The right call is to integrate one of those rather than building a fragile regex-based extractor in-house.

For this prototype, CSV upload covers the use case that most utility portals support today. In year two of a real product, PDF parsing would be the natural next investment.

---

## 3. Reporting period management and audit-ready export

**What I built instead:** A per-record `is_locked` boolean and an analyst approval workflow.

**What I gave up:** A proper `ReportingPeriod` model (e.g., "FY 2024, Jan–Dec, locked on 2025-03-31") that: groups records by period, enforces that all records in a period are approved before locking, generates a structured export (CSV or JSON) suitable for submission to an auditor or ESG framework (GRI, BRSR, CDP).

**Why I made this tradeoff:**

The assignment asks for an ingestion and review prototype, not a reporting platform. The audit export format depends entirely on which framework the client reports to — GRI 305, BRSR Core, CDP Climate, ISO 14064 — and each has different templates, materiality thresholds, and disclosure requirements. Building a generic export that works for all of them is a separate product decision.

What I built supports the concept: records have `is_locked`, the analyst review workflow moves records to `APPROVED`, and the `AuditLog` table provides a complete change history that an auditor can inspect. The locking mechanism and audit trail are correct — the output format is what's missing.

**What breaks without it:** An analyst approving records one by one with no concept of "we're done with Q1" — there's no way to declare a period complete, freeze it, and generate the submission artifact. This is the next most important feature after the prototype.

---

## Summary table

| Not built | Correct long-term solution | Why deferred |
|---|---|---|
| Async file processing | Celery + Redis, task queue | Adds deployment complexity; fine for file sizes in prototype |
| PDF utility bill parsing | Sensible.io or pdfplumber + per-utility templates | High variance across utilities; entire sub-project |
| Reporting periods + audit export | `ReportingPeriod` model + framework-specific templates | Output format is client/framework-specific; separate product decision |
