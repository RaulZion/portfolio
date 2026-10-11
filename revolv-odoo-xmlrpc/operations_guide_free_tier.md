# Warehouse guide - one-off stock update on Odoo Free

Use Odoo's built-in Inventory import. This is a **manual** procedure; the XML-RPC script in this repository is a separate local test.

Before starting, agree on the stock cut-off and a short period when no one will change the affected stock. Use only approved arrivals that are not already recorded in Odoo.

1. **Check the records.** Export Odoo's products and current stock. Match each CSV SKU and full location exactly. If a match is missing or duplicated, stop that row.
2. **Calculate the count.** Add the approved change to the current On Hand quantity. Write down the starting stock and the expected final count. Use whole numbers such as `15`, not `15.0`; the latter was read as 150 in an Italian-language import test.
3. **Choose the import format.** For existing stock, use its exported External ID and the new counted quantity (`inventory_quantity`). For a first arrival without a stock record, use Odoo's Inventory Adjustment template with Product, Location and Counted Quantity. Do not use the first-arrival template for an existing row.
4. **Test a few rows first.** Import a pilot of 3-5 rows using **Test**. Check Product, Location, Counted and especially **Difference** before clicking **Apply**. Do not apply unexpected counts or duplicate rows.
5. **Finish and check.** Apply only approved changes during the agreed pause. Export inventory again and compare the final stock with each expected count. Save the source CSV, import files, approval and before/after exports.

If Odoo rejects a line, check its SKU and location in the original export. For example, `SADA-BRG-0O2` may contain a letter **O** where a zero belongs. Correct and retest only the affected row **after confirming the earlier adjustment was not applied**. Never apply the same change twice.

Use normal Odoo receipts for future deliveries.
