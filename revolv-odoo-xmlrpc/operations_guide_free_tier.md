# Operations guide - one-off Odoo Online Free stock alignment

This procedure uses Odoo's **built-in inventory import**, not the local XML-RPC demo.

1. Obtain the approved changes CSV with SKU, quantity change and full location. Export today's Odoo product and stock lists. Agree a cut-off with Procurement and exclude arrivals already recorded in Odoo.
2. For each SKU/location, check that there is exactly one product and the location is correct. Calculate **Counted = current On Hand + approved change**. Record the baseline, target and approval. Use whole-number text only.
3. For an **existing inventory record**, use its exported **External ID** with the target `inventory_quantity`. For a **first arrival**, use Odoo's Inventory Adjustment template with Product, Location and Counted Quantity. Do not reuse the first-arrival format for an existing record.
4. Import a pilot of **3-5 rows**. Click **Test**, then inspect Product, Location, Counted and **Difference**. Stop if a row is duplicated, the count is unexpected, or a product needs lot/serial data.
5. During the agreed stock-change pause, apply only approved rows. Export inventory again and compare every final On Hand value with its approved target. Keep the original CSV, imports, approvals and before/after exports.

If a row is rejected, read Odoo's import message and check the exact SKU/location against the original export. For example, `SADA-BRG-0O2` may contain the letter **O** instead of the digit **0**. Correct and re-test that row only, after checking that no previous adjustment was applied. Never blindly apply the same change twice. Use normal receipts for future deliveries.
