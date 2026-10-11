# Odoo 19 checks behind the XML-RPC demo

**Checked on 11 October 2026.** The write method was inspected in the official Odoo 19 source and in the installed `odoo:19.0` Docker image before the live test.

- Odoo image digest: `odoo@sha256:dd9013e669caaa23d26765dc55814655eaeecca7cfc2c265dbabae913bce22fd`
- Installed `stock_quant.py` SHA-256: `6d894fea409598074a04d8ca805d7d4f974b5b34357e0ce915ec58d492a19362`
- Live Odoo server version: `19.0-20260926`

These identify the tested build. The moving `19.0` branch and Docker tag may change.

## Why I used inventory_quantity_auto_apply

The script resolves one existing `stock.quant` for an exact product and location. Through XML-RPC `execute_kw`, it calls the public `stock.quant.write` method, setting `inventory_quantity_auto_apply` to the **absolute target**. The context enables `inventory_mode` and restricts the selected company.

In Odoo 19, the inverse `_set_inventory_quantity` handles that field and invokes the standard inventory-adjustment logic. Odoo creates the stock movements. The script **never writes directly to `stock.quant.quantity`** and does not call private methods over RPC.

`write` returns a boolean that XML-RPC can serialize. I avoided using `action_apply_inventory` directly because its normal path may return `None`. The [XML-RPC controller](https://github.com/odoo/odoo/blob/19.0/addons/rpc/controllers/xmlrpc.py) serializes replies with `allow_none=False`, while the [model RPC service](https://github.com/odoo/odoo/blob/19.0/odoo/service/model.py) can commit before serialization. The practical risk is a client error after the stock change has already been committed. That is why the script does not blindly retry a failed response.

Even a successful `write` response is not enough: the script resolves the quant again and checks the **actual stock against the saved target**. Pending or outdated inventory counts are not treated as success.

## What the script checks

- `product.product.default_code` and `stock.location.complete_name` must match exactly. Zero or multiple matches are errors.
- The product must be active, storable, untracked and compatible with whole units. The location must be active, internal and in the selected company.
- The user must have `stock.group_stock_user` access; the local account is restricted to one company. The authenticated user's `has_group` call was checked against [res_users.py](https://github.com/odoo/odoo/blob/19.0/odoo/addons/base/models/res_users.py).
- The quant must already exist and be unique. Reservations, pending/outdated counts, lot/serial, package and owner dimensions are rejected.
- Before applying a count, the target and stock identity are stored in a local ledger. Changes or uncertain RPC outcomes require reconciliation; there is no automatic write retry.

The code is intentionally restricted to `http://localhost` or `http://127.0.0.1` and database `revolv_test`. That restriction prevents this assignment demo from writing to Odoo Online.

## Sources and evidence

- [Odoo 19 External RPC API](https://www.odoo.com/documentation/19.0/developer/reference/external_rpc_api.html): `version`, `authenticate`, `execute_kw` and the public ORM methods. Odoo Online's External API is unavailable on One App Free and Standard; Custom is required. XML-RPC is deprecated. The removal notice checked at the time of testing points to Odoo 22 / Online 21.1.
- [`stock_quant.py` in Odoo 19](https://github.com/odoo/odoo/blob/19.0/addons/stock/models/stock_quant.py): fields, the inventory inverse, conflict handling and stock-move application.
- [Odoo Docker entrypoint](https://github.com/odoo/docker/blob/master/19.0/entrypoint.sh): the local startup and database options.

The [live demo record](evidence/live_demo_evidence.txt) contains the server version, authenticated UID, product and location IDs, before/after quantities and movement counts. The first run went **10 → 15**; the same input with its ledger added no second movement. Four invalid rows were isolated from a valid row, and stock changed to 16 returned `CONFLICT` without a migration write.

Timeouts, lost RPC responses, crashes and failed readback are **automated simulations**, not live network failures. The One App Free import findings were observed manually in Odoo's web interface. Neither set of evidence proves safe operation during concurrent warehouse activity: an agreed migration window and production access review would still be required.
