# Revolv Space - Odoo inventory migration

Raul Osifo · AI Operations Intern technical assignment · October 2026

The assignment asked for a cost-free migration on Odoo Online and a Python integration using XML-RPC. Those requirements need different environments: **One App Free does not offer the External API**. I tested the native import on Odoo Online Free and the Python integration on a local Odoo Community 19 database. Neither test is presented as a production rollout.

| | Task 1: Free-tier migration | Task 2: XML-RPC integration |
|---|---|---|
| Environment | Odoo Online One App Free | Odoo Community 19 in Docker |
| Approach | Standard inventory export/import | Python CLI calling XML-RPC |
| Verified | Manual stock adjustments and import behavior | Live write, readback, safe same-batch rerun |
| Not included | An automatic CSV-to-import generator | Connection or writes to Odoo Online Free |

## Task 1 - the approach that works on Free

A one-off migration can use the tools already available in Inventory:

1. Agree a cut-off with Procurement and exclude arrivals already recorded in Odoo.
2. Export products and current stock. For each approved CSV change, check the exact SKU and location, then calculate **Counted = On Hand + quantity_change**.
3. Prepare the appropriate import file, using integer quantities:
   - **Existing stock:** Odoo's exported External ID and the absolute `inventory_quantity`.
   - **First arrival without a stock row:** Odoo's Inventory Adjustment template (Product, Location, Counted Quantity).
4. Use Odoo's **Test** function. Check the resulting **Difference** before approving **Apply**.
5. Re-export the stock and compare it with the approved targets. Keep the source file and the before/after exports.

These were manual UI tests, not output from a second Python script. Two details changed the design: in the Italian locale, `15.0` was interpreted as `150`; and using the first-arrival template on an existing stock record created another pending inventory row. The two import formats must stay separate.

This path avoids custom modules, Odoo Studio and external API access. It does still require human checks. A sensible next step would be to generate the two import files offline; that generator is **not** part of this submission. The short warehouse procedure is in [operations_guide_free_tier.md](operations_guide_free_tier.md).

## Task 2 - the Python/XML-RPC demonstration

The script takes `material_sku,quantity_change,location`. It checks each row, finds one exact product, location and stock record, reads the current quantity, and saves an **absolute target** before attempting a stock write. It then reads the quantity again and writes a row-level result to `sync_report.csv`.

**Live result on Odoo 19.0-20260926:** `SADA-001` at `WH/Stock` went from **10 to 15** using delta **+5**. Re-running the same input with the same ledger returned `ALREADY_APPLIED`: stock stayed at 15 and no new stock movement was created. In a mixed batch, four bad rows were reported without stopping a separate valid row. When stock was deliberately changed to 16, the script returned `CONFLICT` without writing.

The write uses Odoo's `stock.quant.write` with `inventory_quantity_auto_apply` in inventory mode. I checked this against the [Odoo 19 source](odoo_verification.md) and the installed Docker image. The script does not write directly to the `quantity` field.

### Running the local demo

Requirements: Python 3.14, an Odoo **Community 19** test database called `revolv_test`, Inventory installed and a single-company test user. The test fixture is an existing, untracked and unreserved stock record. On Windows, `setup_local.ps1` can create or reuse the Docker lab; it preserves existing stock and ledgers.

Run these commands from this folder:

```powershell
py -3.14 -m unittest -q
$env:ODOO_URL = 'http://127.0.0.1:8069'
$env:ODOO_DB = 'revolv_test'
$env:ODOO_USER = 'admin'
py -3.14 migrate_inventory.py          # stock dry run; saves a local plan
py -3.14 migrate_inventory.py --apply  # write only after review
```

The CLI prompts for the local password unless `ODOO_PASSWORD` is set privately. Optional flags are `--input`, `--ledger` and `--report`. **Do not reset the supplied ledger to try to reproduce the original first run.** The default rerun correctly reports `ALREADY_APPLIED`.

The report distinguishes `SUCCESS` (stock verified), `ALREADY_APPLIED` (no new write), `ERROR` (row skipped) and `CONFLICT` / `REVIEW` (stop and reconcile). Failed rows do not automatically cancel unrelated valid rows.

### What prevents a second delta?

For the **same input and ledger**, the script stores the baseline, delta, fixed target, stock identity and write state. It records `ATTEMPTING` before making the RPC call. If a response is lost, it checks Odoo again instead of sending another +5. An uncertain outcome is left for review.

**This is not a global exactly-once guarantee.** If someone starts a new ledger containing changes that have already been applied, the delta can be applied again. Never replace a ledger to clear an error. Compare the report with a fresh stock export; create a separately approved batch containing **only rows confirmed not applied**. A timeout or uncertain result is not proof that a row was skipped.

This local prototype deliberately allows only loopback HTTP and database `revolv_test`. It covers whole units, one company, existing plain quants, and no reservations or lot/serial tracking. It requires a controlled stock-change window. Production access controls, concurrency and first-arrival API handling remain out of scope.

## Code, prompts and evidence

- [`migrate_inventory.py`](migrate_inventory.py) - standard-library CLI.
- [`test_migrate_inventory.py`](test_migrate_inventory.py) - 51 automated tests; timeout, lost-response and interruption cases are simulated.
- [`evidence/live_demo_evidence.txt`](evidence/live_demo_evidence.txt) - recorded live version, stock quantities and movement counts; the matching CSV reports are in [evidence/](evidence/).
- [`actual_user_prompt.txt`](actual_user_prompt.txt) - unedited prompt given to Codex. No custom system prompt was supplied; see [AI provenance](ai_provenance.md).
- [`odoo_verification.md`](odoo_verification.md) - official Odoo source references and the reason for the chosen write method.

The Online Free import tests were performed manually. The local XML-RPC writes were run by Codex against the test database and saved in the evidence files. Neither set of results establishes that this script is ready for use against a live warehouse.
