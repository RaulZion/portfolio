# Odoo inventory migration - Revolv Space assignment

**Raul Osifo · October 2026**

The brief asked for a cost-free stock migration and a Python tool using XML-RPC. I kept them separate because **Odoo Online One App Free does not provide External API access**.

- **Task 1:** I tested a one-off migration using Odoo Online Free's built-in inventory import. It is a manual procedure, not a second Python tool.
- **Task 2:** Codex built a Python/XML-RPC script, which was run against a local Odoo Community 19 database. Its stock writes and readbacks are recorded in this repository.

Neither path has been deployed to a production warehouse.

## Task 1 - native import on Odoo Free

For each approved CSV change (`material_sku,quantity_change,location`), agree a cut-off, exclude arrivals already entered in Odoo, export current stock and calculate the **absolute counted quantity = On Hand + delta**. Test a small import, inspect Odoo's **Difference** column, apply only approved changes, then compare a fresh stock export with the expected results.

The manual tests uncovered two details worth keeping in the procedure:

- **Existing stock:** import the exported External ID and the new `inventory_quantity`.
- **First arrival without an existing stock record:** use Odoo's Inventory Adjustment template with Product, Location and Counted Quantity. Using this template on existing stock created a second pending inventory row.
- **Italian number format:** `15.0` was interpreted as `150`. This exercise uses integer text only.

No custom modules, Studio or API calls are needed. The calculation is still manual in this pilot; generating the two import files offline would be a later improvement, not a feature claimed here. See the [short warehouse guide](operations_guide_free_tier.md).

## Task 2 - Python and XML-RPC

[`migrate_inventory.py`](migrate_inventory.py) reads the same three CSV fields, checks each row independently, looks up the exact product and location, reads the current stock and saves a fixed target. It uses Odoo's inventory-adjustment mechanism, reads the stock back, and writes a per-row result to `sync_report.csv`.

The local test used **Odoo 19.0-20260926**, an existing untracked product `SADA-001` and location `WH/Stock`:

| Run | Stock | Result |
|---|---|---|
| Before | 10 | Baseline |
| First run, delta +5 | 15 | `SUCCESS`, verified by readback |
| Same input and ledger again | 15 | `ALREADY_APPLIED`; no additional stock move |
| Stock separately changed to 16 | 16 | `CONFLICT`; no migration write |

A mixed live test rejected four invalid rows while processing another valid row. The [live record](evidence/live_demo_evidence.txt) and [CSV reports](evidence/) show the results. The **51 automated tests** include simulated timeouts, lost responses and interrupted runs; those are not presented as live network failures.

### Reproduce locally

Use Python 3.14 and Odoo **Community 19** with Inventory installed, database `revolv_test` and a single-company test user. `setup_local.ps1` can create or reuse the Windows Docker lab without resetting existing stock or the ledger.

```powershell
py -3.14 -m unittest -q
$env:ODOO_URL = 'http://127.0.0.1:8069'
$env:ODOO_DB = 'revolv_test'
$env:ODOO_USER = 'admin'
py -3.14 migrate_inventory.py          # plan; no stock write
py -3.14 migrate_inventory.py --apply  # write after review
```

Supply `ODOO_PASSWORD` privately or enter it when prompted. The script accepts `--input`, `--ledger` and `--report`. It only connects to a loopback address and `revolv_test`, so it cannot be used to write to Odoo Online Free. **Keep the saved ledger:** rerunning this submitted batch should return `ALREADY_APPLIED`, not repeat the first write.

### Safety and limits

The ledger records the baseline, delta, absolute target, record identity and write state. An `ATTEMPTING` state is saved **before** the RPC. If the response is uncertain, the tool rechecks Odoo rather than blindly sending the delta again. In the report, `ERROR` means the row was skipped; `CONFLICT` or `REVIEW` means stop and reconcile.

The protection applies to **the same input and ledger**. A new ledger containing already-applied rows could apply the delta twice. Never discard a ledger to clear an error. Reconcile against a fresh export, then put **only confirmed unapplied rows** in a separately approved batch.

The demo covers whole units, one company and existing unreserved stock without lot, serial, package or owner tracking. It needs a controlled stock-change window. It is **not** a production exactly-once integration.

## Source and AI provenance

- [Actual Codex user prompt](actual_user_prompt.txt) - complete and unedited; no custom system prompt was supplied.
- [AI roles and review history](ai_provenance.md) - what ChatGPT, Codex and manual testing contributed.
- [Odoo 19 verification](odoo_verification.md) - source references and why `inventory_quantity_auto_apply` was used.
- [Automated tests](test_migrate_inventory.py) and [live evidence](evidence/live_demo_evidence.txt).
