"""One-off, integer-only Odoo 19 LOCAL inventory migration. Standard library."""
import argparse
from collections import Counter
import csv
from decimal import Decimal
import getpass
import hashlib
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
import xmlrpc.client

INPUT = ['material_sku', 'quantity_change', 'location']
IDS = ['product_id', 'location_id', 'quant_id', 'company_id']
LEDGER = ['batch', 'binding', 'row_number', 'material_sku', 'location',
          *IDS, 'baseline', 'delta', 'target', 'state']
REPORT = ['row_number', 'material_sku', 'location', 'baseline', 'delta',
          'target', 'actual', 'status', 'message']
LIMIT = 1_000_000_000

class TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout):
        super().__init__()
        self.timeout = timeout
    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection
    def request(self, host, handler, request_body, verbose=False):
        # Transport.request normally retries a disconnected POST. Never retry writes.
        return self.single_request(host, handler, request_body, verbose)

def whole(value):
    number = Decimal(str(value))
    if not number.is_finite() or number != number.to_integral_value() or abs(number) > LIMIT:
        raise ValueError('Quantity must be a finite supported integer')
    return int(number)

def exact_one(records, label):
    if len(records) != 1:
        raise ValueError(label + ' is unknown or ambiguous')
    return records[0]

class Odoo:
    def __init__(self, url, database, username, password, timeout=10):
        origin = urlsplit(url)
        if (origin.scheme != 'http' or origin.hostname not in ('localhost', '127.0.0.1', '::1')
                or origin.path not in ('', '/') or origin.query or origin.fragment
                or origin.username or origin.password or database != 'revolv_test'):
            raise ValueError('Only loopback HTTP and database revolv_test are allowed')
        if not 0 < timeout <= 120:
            raise ValueError('Timeout must be between 0 and 120 seconds')
        self.db, self.password = database, password
        def proxy(endpoint):
            return xmlrpc.client.ServerProxy(url.rstrip('/') + endpoint,
                                            transport=TimeoutTransport(timeout))
        common = proxy('/xmlrpc/2/common')
        self.version = common.version()
        if self.version['server_version_info'][0] != 19:
            raise ValueError('This demonstration requires Odoo 19')
        self.uid = common.authenticate(database, username, password, {})
        if not self.uid:
            raise ValueError('Authentication failed')
        self.object = proxy('/xmlrpc/2/object')
        user = self.call('res.users', 'read', [[self.uid]], fields=['company_ids', 'company_id'])[0]
        if len(user['company_ids']) != 1:
            raise ValueError('Use a dedicated single-company test account')
        self.company = user['company_id'][0]
        self.context = {'allowed_company_ids': [self.company], 'active_test': False}
        if not self.call('res.users', 'has_group', [[self.uid], 'stock.group_stock_user']):
            raise ValueError('Inventory permissions are required')
        uuid = self.call('ir.config_parameter', 'get_param', ['database.uuid'])
        if not uuid:
            raise ValueError('Database identity unavailable')
        self.binding = hashlib.sha256((url.rstrip('/')+'|'+database+'|'+uuid).encode()).hexdigest()
    def call(self, model, method, args, **kwargs):
        kwargs.setdefault('context', getattr(self, 'context', {}))
        return self.object.execute_kw(self.db, self.uid, self.password, model, method, args, kwargs)
    def find(self, model, domain, fields):
        return self.call(model, 'search_read', [domain], fields=fields, limit=2)
    def resolve(self, sku, location):
        product = exact_one(self.find('product.product', [['default_code', '=', sku]],
                    ['is_storable', 'tracking', 'uom_id', 'company_id', 'active']), 'SKU')
        place = exact_one(self.find('stock.location', [['complete_name', '=', location]],
                    ['usage', 'company_id', 'active']), 'Location')
        if not product['active'] or not product['is_storable'] or product['tracking'] != 'none':
            raise ValueError('Product must be active, storable and untracked')
        if not place['active'] or place['usage'] != 'internal' or place['company_id'][0] != self.company:
            raise ValueError('Use an active internal location in the test company')
        if product['company_id'] and product['company_id'][0] != self.company:
            raise ValueError('Product belongs to a different company')
        uom = self.call('uom.uom', 'read', [[product['uom_id'][0]]], fields=['rounding'])[0]
        rounding = Decimal(str(uom['rounding']))
        if not rounding.is_finite() or rounding <= 0 or Decimal(1) % rounding:
            raise ValueError('Unit of measure must support whole units')
        quant = exact_one(self.find('stock.quant', [['product_id', '=', product['id']],
                    ['location_id', '=', place['id']]], ['quantity', 'reserved_quantity',
                    'inventory_quantity_set', 'is_outdated', 'lot_id', 'package_id', 'owner_id', 'company_id']), 'Stock quant')
        if (quant['reserved_quantity'] != 0 or quant['inventory_quantity_set'] or quant['is_outdated']
                or quant['lot_id'] or quant['package_id'] or quant['owner_id']
                or quant['company_id'][0] != self.company):
            raise ValueError('Reserved, pending, outdated or dimensional stock requires review')
        return dict(product_id=product['id'], location_id=place['id'], quant_id=quant['id'],
                    company_id=self.company, actual=whole(quant['quantity']))
    def write(self, quant_id, target):
        # Public write returns bool; the inverse performs Odoo's inventory adjustment.
        return self.call('stock.quant', 'write', [[quant_id], {'inventory_quantity_auto_apply': target}],
                         context={**self.context, 'inventory_mode': True})

def save_csv(path, fields, rows):
    path = Path(path)
    with tempfile.NamedTemporaryFile('w', newline='', encoding='utf-8', dir=path.parent,
                                     prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
        temporary = stream.name
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def read_input(path):
    raw = Path(path).read_bytes()
    batch = hashlib.sha256(raw).hexdigest()
    rows = []
    try:
        reader = csv.reader(raw.decode('utf-8-sig').splitlines(keepends=True), strict=True)
        if next(reader, None) != INPUT:
            raise ValueError('CSV header must be material_sku,quantity_change,location')
        for cells in reader:
            row = dict(zip(INPUT, cells))
            row['row_number'] = reader.line_num
            row['malformed'] = len(cells) != 3
            rows.append(row)
    except (UnicodeError, csv.Error) as error:
        raise ValueError('Unreadable CSV syntax; no rows were processed') from error
    counts = Counter((r.get('material_sku'), r.get('location')) for r in rows)
    for row in rows:
        row['duplicate'] = counts[(row.get('material_sku'), row.get('location'))] > 1
    return batch, rows

def load_ledger(path, batch, binding):
    plans = {}
    if not Path(path).exists():
        return plans
    with Path(path).open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != LEDGER:
            raise ValueError('Ledger header is invalid; preserve it for manual review')
        for plan in reader:
            if set(plan) != set(LEDGER) or any(v is None for v in plan.values()):
                raise ValueError('Ledger row is corrupt')
            if plan['batch'] != batch or plan['binding'] != binding:
                raise ValueError('Ledger belongs to another input or database')
            for key in ['row_number', *IDS, 'baseline', 'delta', 'target']:
                plan[key] = whole(plan[key])
            if (plan['row_number'] in plans or plan['state'] not in ('PLANNED', 'ATTEMPTING', 'DONE')
                    or plan['target'] < 0 or plan['target'] != plan['baseline'] + plan['delta']):
                raise ValueError('Ledger plan is invalid; do not reset it')
            plans[plan['row_number']] = plan
    return plans

def migrate(path, ledger, odoo, apply=False):
    ledger = Path(ledger)
    batch, rows = read_input(path)  # Parse the entire file before the first write.
    lock = ledger.with_suffix(ledger.suffix + '.lock')
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        plans = load_ledger(ledger, batch, odoo.binding)
        reports = []
        def persist():
            save_csv(ledger, LEDGER, list(plans.values()))
        for row in rows:
            report = dict.fromkeys(REPORT, '')
            report.update({k: row.get(k, '') for k in ('row_number', 'material_sku', 'location')})
            plan = plans.get(row['row_number'])
            if plan:
                report.update({k: plan[k] for k in ('baseline', 'delta', 'target')})
            report.update(status='ERROR', message='')
            try:
                if row['malformed'] or row['duplicate']:
                    raise ValueError('Malformed row or duplicate SKU/location pair')
                for key in ('material_sku', 'location'):
                    text = row[key]
                    if not text or text != text.strip() or any(ord(c) < 32 for c in text):
                        raise ValueError('SKU and location must be exact, nonblank text')
                if not re.fullmatch(r'[+-]?[0-9]+', row['quantity_change']):
                    raise ValueError('Delta must be integer text, such as 5 or -3')
                delta = whole(row['quantity_change'])
                report['delta'] = delta
                current = odoo.resolve(row['material_sku'], row['location'])
                report['actual'] = current['actual']
                if plan is None:
                    target = whole(Decimal(current['actual']) + Decimal(delta))
                    if current['actual'] < 0 or target < 0:
                        raise ValueError('Baseline and target stock must be nonnegative')
                    plan = {k: current[k] for k in IDS}
                    plan.update(batch=batch, binding=odoo.binding, row_number=row['row_number'],
                                material_sku=row['material_sku'], location=row['location'],
                                baseline=current['actual'], delta=delta, target=target, state='PLANNED')
                    plans[row['row_number']] = plan
                report.update({k: plan[k] for k in ('baseline', 'delta', 'target')})
                if (any(plan[k] != current[k] for k in IDS) or plan['delta'] != delta
                        or plan['material_sku'] != row['material_sku'] or plan['location'] != row['location']):
                    report.update(status='CONFLICT', message='Recorded product/location/quant identity changed')
                elif current['actual'] == plan['target']:
                    report.update(status='SUCCESS' if plan['delta'] == 0 and plan['state']=='PLANNED'
                                  else 'ALREADY_APPLIED', message='Target verified; no stock write')
                    plan['state'] = 'DONE'
                elif current['actual'] != plan['baseline'] or plan['state'] == 'DONE':
                    report.update(status='CONFLICT', message='Stock changed outside this migration; no write')
                elif plan['state'] == 'ATTEMPTING':
                    report.update(status='REVIEW', message='Prior write outcome uncertain; no automatic retry')
                else:
                    report.update(status='DRY_RUN', message='Plan saved; stock unchanged')
            except Exception as error:
                report.update(status='REVIEW' if plan and plan['state'] != 'PLANNED' else 'ERROR',
                              message=str(error) if isinstance(error, ValueError) else
                              'Read/validation failed ('+type(error).__name__+'); no write attempted')
            persist()  # A disk failure is fatal: never write without a durable plan.
            if report['status'] == 'DRY_RUN' and apply:
                plan['state'] = 'ATTEMPTING'
                persist()  # Persist uncertainty BEFORE the RPC, including crash windows.
                issue = ''
                report['actual'] = ''  # Unknown until the post-write read succeeds.
                try:
                    odoo.write(plan['quant_id'], plan['target'])
                except Exception as error:
                    issue = 'RPC response failed ('+type(error).__name__+'). '
                try:
                    actual = odoo.resolve(row['material_sku'], row['location'])
                    report['actual'] = actual['actual']
                    if any(actual[k] != plan[k] for k in IDS) or actual['actual'] != plan['target']:
                        raise ValueError('Final stock does not match the recorded target')
                    plan['state'] = 'DONE'
                    report.update(status='SUCCESS', message=issue+'Target verified by fresh read')
                except Exception as error:
                    report.update(status='REVIEW', message=issue+'Final state requires manual reconciliation ('+
                                  type(error).__name__+'); no automatic retry')
                persist()
            reports.append(report)
        return reports
    finally:
        os.close(descriptor)
        lock.unlink()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('migration_input.csv'))
    parser.add_argument('--ledger', type=Path, default=Path('migration_ledger.csv'))
    parser.add_argument('--report', type=Path, default=Path('sync_report.csv'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        if len({args.input.resolve(), args.ledger.resolve(), args.report.resolve()}) != 3:
            raise ValueError('Input, ledger and report must be different files')
        read_input(args.input)
        api = Odoo(os.getenv('ODOO_URL', 'http://127.0.0.1:8069'), os.getenv('ODOO_DB', 'revolv_test'),
                   os.getenv('ODOO_USER', 'admin'), os.getenv('ODOO_PASSWORD') or getpass.getpass('Local Odoo password: '),
                   float(os.getenv('ODOO_TIMEOUT', '10')))
        print('Odoo', api.version['server_version'], 'authenticated UID', api.uid)
        reports = migrate(args.input, args.ledger, api, args.apply)
        save_csv(args.report, REPORT, reports)
        for row in reports:
            print(row['row_number'], row['material_sku'], row['status'], 'actual='+str(row['actual']))
        return 1 if any(r['status'] in ('ERROR', 'REVIEW', 'CONFLICT') for r in reports) else 0
    except Exception as error:
        # Explain local input/ledger mistakes, without echoing RPC data or credentials.
        if isinstance(error, (ValueError, OSError)):
            detail = str(error)
        elif isinstance(error, xmlrpc.client.Fault):
            detail = 'Odoo RPC fault code ' + str(error.faultCode)
        else:
            detail = 'Check local configuration and logs'
        print('Stopped safely (' + type(error).__name__ + '): ' + detail
              + '. Preserve the ledger; do not blindly retry.')
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
