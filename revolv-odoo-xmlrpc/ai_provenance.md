# How I used AI

I used ChatGPT to work through the constraints before asking Codex to write the integration. The important decision was to keep **Odoo Online Free** and the **XML-RPC demonstration** separate: the Free plan does not provide External API access.

I then gave Codex a structured user prompt covering the local test environment, CSV fields, exact SKU/location checks, stock-adjustment method, error handling, timeout safety, persistent ledger, live write and readback, and negative tests.

[`actual_user_prompt.txt`](actual_user_prompt.txt) is that **complete, unedited user prompt**. I did not supply a separate custom system prompt. Any hidden instructions provided by the platform are not reproduced or presented as mine.

Codex implemented the local Python tool and ran the recorded tests against Odoo Community 19. I performed the Online Free import trials through Odoo's interface. ChatGPT was also used to review and edit the submission documentation. After the live demonstration, a review led to clearer fatal-error messages; the stock-writing logic itself was not changed.

The [live evidence](evidence/live_demo_evidence.txt) and automated tests are kept separate. Simulated timeouts are not described as failures observed on a live network.
