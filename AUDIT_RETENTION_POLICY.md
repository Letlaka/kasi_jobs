Audit Retention Policy
======================

- **Purpose:** Document the retention and export practices for `ApplicationAction` audit records (accept/reject/audit events).
- **Recommended retention timeframe:** 5 years from the event `created_at` timestamp (recommend legal review; adjust to jurisdictional/regulatory requirements such as POPIA).
- **Archival strategy:**
  - Periodically (e.g., monthly) run a management command to export and compress `ApplicationAction` rows older than the retention window into an immutable archive store (S3 or an internal secure blob store).
  - Store exported files with a manifest and checksum, and then delete rows from the primary database after successful archival and verification.
  - Keep at least one additional offline backup copy (on separate storage) for compliance.
- **Purge strategy:**
  - After successful archival and retention period expiry (if policy requires deletion), remove archived records from primary DB and optionally from archive store according to legal hold rules.
  - Keep a short-lived tombstone/manifest entry in the database or logs that an archive operation occurred (avoid retaining original personal data in application DB).
- **Subject-access / export (POPIA) handling:**
  - Provide an authenticated/admin export endpoint or management command that accepts an `application_id` and returns all `ApplicationAction` rows for that application as JSON or CSV.
  - Authenticate and authorize calls to the export tool; require elevated privileges and audit the export itself.
  - Validate requester identity and retention/exemption rules before releasing personal data.
- **Operational notes:**
  - Archive exports should be encrypted at rest and in transit.
  - Access to archive storage should be limited to approved roles; logs should capture who retrieved or deleted archives.
  - Retention windows must be approved by legal/compliance teams; this document is a recommended default.

Implementation guidance
-----------------------

- A management command `export_application_audit` is provided to export per-application audit rows to JSON/CSV for subject-access requests or operational needs. Use it as a building block for a guarded admin endpoint.
- A separate management command or scheduled job should implement archival and purge based on the retention window.
