# Revolv Space - Odoo inventory migration (assignment evidence)

**Author:** Raul Osifo  
**Scope:** one-off inventory reconciliation; no production deployment.

This project documents two different, tested approaches. They are **not interchangeable**.

## Task 1 - Odoo Online One App Free

This task is a **manual, native-import procedure**, not an additional Python application. The Free plan does not include Odoo's External API. For an approved one-off migration, compare each source CSV delta (`material_sku`, `quantity_change`, `location`) against a fresh Odoo product/stock export. Agree a cut-off and exclude arrivals already recorded in Odoo. Calculate an **absolute target = on-hand + delta** for each unambiguous SKU and location. Use the native import's **Test**, inspect Counted and Difference, obtain approval, **Apply**, then export inventory again to reconcile the result. Pause other stock changes during this operation.

The manual trials on Odoo Online showed two required import formats:

- **Existing stock row:** its exported External ID and integer `inventory_quantity` target.
- **First arrival with no stock row:** official Inventory Adjustment import template, Product / Location / Counted Quantity. Do not use this format to update existing stock: a trial created a second pending inventory row instead.

An Italian-localized import interpreted `15.0` as `150`; only **integer text** is used in this exercise. Lot/serial-tracked stock is out of scope. Future receipts belong to normal Odoo receipt workflows. See [`operations_guide_free_tier.md`](operations_guide_free_tier.md). These are human-performed Online UI tests, not XML-RPC tests.

## Task 2 - Python / XML-RPC on local Odoo Community 19

`migrate_inventory.py` is a locally verified XML-RPC prototype. It cannot connect to Odoo Online One App Free. The script intentionally accepts only `http://localhost` or `http://127.0.0.1` and database `revolv_test` so the assignment demo cannot accidentally write to a cloud database.

**Data path:** input CSV -> per-row validation -> exact product/location/quant resolution -> read baseline -> durable absolute target -> guarded inventory adjustment -> readback -> `sync_report.csv`.

Use an installed Odoo 19 Community test instance with Inventory, a single-company account, an existing untracked/unreserved product `SADA-001` at `WH/Stock` with 10 units, and Python 3.14 (standard library only). `setup_local.ps1` and `setup_product.py` are optional lab helpers. The saved report records the original live run; do **not** delete the operational ledger to reproduce it.

```powershell
py -3.14 -m unittest -q
$env:ODOO_URL='http://127.0.0.1:8069'
$env:ODOO_DB='revolv_test'
$env:ODOO_USER='admin'
py -3.14 migrate_inventory.py             # dry run
py -3.14 migrate_inventory.py --apply     # explicit stock write
py -3.14 migrate_inventory.py --apply     # same input + ledger; already applied
```

Set `ODOO_PASSWORD` privately or enter the locally prompted password. Optional flags: `--input`, `--ledger`, `--report`. Input headers must be exactly `material_sku,quantity_change,location`. Each row produces baseline, delta, target, verified actual, status and explanation in `sync_report.csv`. The default is a read-only stock **dry run**, although it saves a local planned ledger.

**Safety:** only existing, untracked, unreserved, unique stock quants and whole units; no negative target. No direct write to `stock.quant.quantity`. An atomic CSV ledger stores the fixed target, record identity, input hash and local database identity. The script records `ATTEMPTING` before RPC and never blindly retries an uncertain write. It verifies the resulting stock after a write. A loss of response, changed stock, pending inventory adjustment, or other uncertainty requires review. A separate migration window is mandatory: no distributed transaction or production *exactly-once* guarantee exists.

**Important correction procedure:** a changed input file is **not** compatible with the original ledger. Do not create a fresh ledger containing previously successful rows: that can apply the same delta again. Compare `sync_report.csv` with a fresh Odoo stock export; put **only confirmed unapplied rows** into a new, separately approved batch. A timed-out or uncertain row is not confirmed unapplied; reconcile it manually before considering a new batch. Never discard an existing ledger to bypass `REVIEW` or `CONFLICT`.

**Fatal errors:** invalid input header, malformed quoting/encoding, incompatible ledger, or disk/lock failure stop the batch before an unsafe write. The CLI now prints the specific safe diagnostic. Non-fatal invalid rows yield `ERROR` and do not stop other rows. Exit codes: 0=accepted/reconciled, 1=row errors/review/conflicts, 2=fatal. Error statuses are **not** proof that all other rows failed.

### Verification and provenance

- Agent-observed **local Odoo 19.0-20260926**: baseline 10, delta +5, `SUCCESS` actual 15; identical run `ALREADY_APPLIED` actual 15 with **zero additional stock moves**; four invalid rows rejected while a valid second row succeeded; changed stock 16 yielded `CONFLICT` with no migration write. See [`evidence/live_demo_evidence.txt`](evidence/live_demo_evidence.txt) and CSV reports.
- 51 automated tests pass in an independent Linux/Python rerun; timeout, response loss and process-interruption cases are **simulated**, not live network failures. Run: `python -m unittest -q`.
- `actual_user_prompt.txt` is the exact Codex **user** prompt. No custom user-authored system prompt was supplied; platform instructions are not reproduced. See `ai_provenance.md`.
- Version-specific behavior and documentation: `odoo_verification.md`. Odoo officially limits External API access to Custom plans; XML-RPC is deprecated and scheduled for removal in a later version.

**Do not interpret a local demonstration as a production deployment.** Access permissions, record rules, lot/serial handling, concurrent stock writes and migration data ownership would need separate review.
