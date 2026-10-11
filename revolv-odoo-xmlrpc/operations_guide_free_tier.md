# Warehouse guide - one-off import on Odoo Free

Use Odoo's built-in Inventory import, **not** the separate XML-RPC demo. Agree on a cut-off and a short pause in warehouse stock changes. Exclude arrivals already recorded in Odoo.

1. **Export and match.** Export current products and stock. Check every approved CSV SKU and full location against Odoo. If a match is missing or duplicated, skip that row.
2. **Calculate the count.** Add the approved change to the current On Hand quantity. Record the baseline and expected final count. Use integer text (`15`, not `15.0`); an Italian-language import read the latter as 150.
3. **Choose the file.** For an existing stock record, import its exported External ID and the new counted quantity (`inventory_quantity`). For a first arrival without a stock record, use the Inventory Adjustment template with Product, Location and Counted Quantity. Do not use that template to update an existing row.
4. **Run a pilot.** Use **Test** on 3-5 rows. Check Product, Location, Counted and **Difference**. Do not click **Apply** if anything looks wrong or a product needs lot/serial details.
5. **Apply and compare.** During the agreed pause, apply only approved counts. Export stock again and compare the result with each target. Keep the source CSV, approvals, imports and before/after exports.

If a row fails, check its SKU and location in the original export. For example, `SADA-BRG-0O2` may contain the letter **O** instead of a zero. Correct and retest that row **only after confirming the earlier adjustment was not applied**.

Use normal Odoo receipts for future deliveries.
