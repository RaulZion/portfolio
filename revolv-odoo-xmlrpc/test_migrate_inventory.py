import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import migrate_inventory as m

class FakeOdoo:
    binding = 'local-test'
    def __init__(self):
        self.quantity = 10
        self.writes = 0
        self.failure = None
        self.read_failure = None
        self.pending = False
        self.changed_id = False
    def resolve(self, sku, location):
        if self.read_failure:
            raise self.read_failure
        if sku != 'SADA-001':
            raise ValueError('SKU is unknown')
        if location != 'WH/Stock':
            raise ValueError('Location is unknown')
        if self.pending:
            raise ValueError('Pending inventory adjustment')
        return dict(product_id=1, location_id=2,
                    quant_id=4 if self.changed_id else 3, company_id=1,
                    actual=self.quantity)
    def write(self, quant_id, target):
        self.writes += 1
        if self.failure == 'committed':
            self.quantity = target
            raise TimeoutError('simulated lost response')
        if self.failure == 'uncommitted':
            raise TimeoutError('simulated no response')
        if self.failure == 'drift':
            self.quantity = target + 1
            raise TimeoutError('simulated drift')
        if self.failure == 'mismatch':
            self.quantity = target + 1
        elif self.failure == 'readback':
            self.quantity = target
            self.read_failure = TimeoutError('readback unavailable')
        elif self.failure == 'pending':
            self.quantity = target
            self.pending = True
        elif self.failure == 'rpc':
            raise m.xmlrpc.client.Fault(1, 'simulated server error')
        else:
            self.quantity = target

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'input.csv'
        self.ledger = Path(self.tmp.name)/'ledger.csv'
        self.api = FakeOdoo()
        self.input('SADA-001,5,WH/Stock')
    def input(self, *rows):
        self.path.write_text('material_sku,quantity_change,location\n'+'\n'.join(rows)+'\n', encoding='utf-8')
    def go(self, apply=True):
        return m.migrate(self.path, self.ledger, self.api, apply)
    def test_positive_delta_and_rerun(self):
        first = self.go()[0]
        self.assertEqual((first['baseline'],first['delta'],first['target'],first['actual'],first['status']), (10,5,15,15,'SUCCESS'))
        self.assertEqual(self.go()[0]['status'], 'ALREADY_APPLIED')
        self.assertEqual((self.api.quantity,self.api.writes), (15,1))
    def test_negative_delta(self):
        self.input('SADA-001,-3,WH/Stock')
        self.assertEqual(self.go()[0]['actual'], 7)
    def test_bad_integer(self):
        for text in ('abc','5.0','NaN','Infinity','','1e3','1,5','2147483648'):
            with self.subTest(text=text):
                self.input('SADA-001,"'+text+'",WH/Stock')
                self.assertEqual(self.go()[0]['status'], 'ERROR')
        self.assertEqual(self.api.writes,0)
    def test_missing_sku(self):
        self.input(',5,WH/Stock')
        self.assertEqual(self.go()[0]['status'], 'ERROR')
    def test_blank_location(self):
        self.input('SADA-001,5,')
        self.assertEqual(self.go()[0]['status'], 'ERROR')
    def test_unknown_sku(self):
        self.input('UNKNOWN,5,WH/Stock')
        self.assertEqual(self.go()[0]['status'], 'ERROR')
    def test_unknown_location(self):
        self.input('SADA-001,5,UNKNOWN')
        self.assertEqual(self.go()[0]['status'], 'ERROR')
    def test_malformed_row_isolated(self):
        self.input('BAD,5,WH/Stock,EXTRA','SADA-001,5,WH/Stock')
        self.assertEqual([r['status'] for r in self.go()], ['ERROR','SUCCESS'])
        self.assertEqual(self.api.writes,1)
    def test_duplicate_rows_rejected_before_writes(self):
        self.input('SADA-001,5,WH/Stock','SADA-001,-1,WH/Stock')
        self.assertEqual([r['status'] for r in self.go()], ['ERROR','ERROR'])
        self.assertEqual(self.api.writes,0)
    def test_negative_target(self):
        self.input('SADA-001,-11,WH/Stock')
        self.assertEqual(self.go()[0]['status'], 'ERROR')
        self.assertEqual(self.api.writes,0)
    def test_zero_delta(self):
        self.input('SADA-001,0,WH/Stock')
        self.assertEqual(self.go()[0]['actual'],10)
        self.assertEqual(self.api.writes,0)
    def test_dry_run_no_write(self):
        self.assertEqual(self.go(False)[0]['status'], 'DRY_RUN')
        self.assertEqual(self.api.writes,0)
        self.assertEqual(self.go()[0]['actual'],15)
    def test_external_drift(self):
        self.go()
        self.api.quantity = 16
        self.assertEqual(self.go()[0]['status'], 'CONFLICT')
        self.assertEqual(self.api.writes,1)
    def test_completed_stock_returning_to_baseline_not_reapplied(self):
        self.go()
        self.api.quantity = 10
        self.assertEqual(self.go()[0]['status'], 'CONFLICT')
        self.assertEqual(self.api.writes,1)
    def test_timeout_committed_and_rerun(self):
        self.api.failure = 'committed'
        self.assertEqual(self.go()[0]['status'], 'SUCCESS')
        self.assertEqual(self.go()[0]['status'], 'ALREADY_APPLIED')
        self.assertEqual(self.api.writes,1)
    def test_timeout_uncommitted_never_retried(self):
        self.api.failure = 'uncommitted'
        self.assertEqual(self.go()[0]['status'], 'REVIEW')
        self.assertEqual(self.go()[0]['status'], 'REVIEW')
        self.assertEqual(self.api.writes,1)
    def test_timeout_unexpected_quantity(self):
        self.api.failure = 'drift'
        self.assertEqual(self.go()[0]['status'], 'REVIEW')
        self.assertEqual(self.go()[0]['status'], 'CONFLICT')
        self.assertEqual(self.api.writes,1)
    def test_verification_mismatch(self):
        self.api.failure = 'mismatch'
        self.assertEqual(self.go()[0]['status'], 'REVIEW')
    def test_read_timeout(self):
        self.api.read_failure = TimeoutError()
        self.assertEqual(self.go()[0]['status'],'ERROR')
        self.assertEqual(self.api.writes,0)
    def test_readback_timeout(self):
        self.api.failure = 'readback'
        result = self.go()[0]
        self.assertEqual(result['status'],'REVIEW')
        self.assertEqual(result['actual'],'')
        self.api.read_failure = None
        self.assertEqual(self.go()[0]['status'],'ALREADY_APPLIED')
        self.assertEqual(self.api.writes,1)
    def test_failed_rerun_preserves_recorded_plan_in_report(self):
        self.go()
        self.api.read_failure = TimeoutError()
        result = self.go()[0]
        self.assertEqual((result['baseline'],result['delta'],result['target'],result['actual'],result['status']),
                         (10,5,15,'','REVIEW'))
    def test_pending_after_write(self):
        self.api.failure = 'pending'
        self.assertEqual(self.go()[0]['status'],'REVIEW')
        self.assertEqual(self.go()[0]['status'],'REVIEW')
        self.assertEqual(self.api.writes,1)
    def test_rpc_error(self):
        self.api.failure = 'rpc'
        self.assertEqual(self.go()[0]['status'],'REVIEW')
        self.assertEqual(self.api.writes,1)
    def test_unexpected_row_exception_isolated(self):
        self.input('BROKEN,5,WH/Stock','SADA-001,5,WH/Stock')
        original = self.api.resolve
        def resolve(sku,location):
            if sku == 'BROKEN':
                raise RuntimeError('Unexpected error')
            return original(sku,location)
        self.api.resolve = resolve
        self.assertEqual([r['status'] for r in self.go()],['ERROR','SUCCESS'])
    def test_invalid_header_fatal(self):
        self.path.write_text('sku,delta,location\nSADA-001,5,WH/Stock\n')
        with self.assertRaises(ValueError):
            self.go()
        self.assertEqual(self.api.writes,0)
    def test_unclosed_quote_fatal_before_writes(self):
        self.input('SADA-001,5,WH/Stock','"broken')
        with self.assertRaises(ValueError):
            self.go()
        self.assertEqual(self.api.writes,0)
    def test_changed_batch_fatal(self):
        self.go()
        self.input('SADA-001,6,WH/Stock')
        with self.assertRaises(ValueError):
            self.go()
        self.assertEqual(self.api.writes,1)
    def test_changed_destination_fatal(self):
        self.go(False)
        self.api.binding = 'other-db'
        with self.assertRaises(ValueError):
            self.go()
    def test_quant_id_change_conflict(self):
        self.go(False)
        self.api.changed_id = True
        self.assertEqual(self.go()[0]['status'],'CONFLICT')
        self.assertEqual(self.api.writes,0)
    def test_save_failure_stops_before_write(self):
        with patch.object(m,'save_csv',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.go()
        self.assertEqual(self.api.writes,0)
    def test_crash_after_plan_allows_resume(self):
        self.go(False)
        self.assertEqual(self.go()[0]['status'],'SUCCESS')
    def test_crash_during_write_resume_no_repeat(self):
        def crash(qid,target):
            self.api.writes += 1
            self.api.quantity = target
            raise KeyboardInterrupt()
        self.api.write = crash
        with self.assertRaises(KeyboardInterrupt):
            self.go()
        self.assertEqual(self.go()[0]['status'],'ALREADY_APPLIED')
        self.assertEqual(self.api.writes,1)
    def test_lock_prevents_parallel_run(self):
        self.ledger.with_suffix('.csv.lock').write_text('busy')
        with self.assertRaises(FileExistsError):
            self.go()
        self.assertEqual(self.api.writes,0)

class AdapterTests(unittest.TestCase):
    def adapter(self, change=None):
        api = m.Odoo.__new__(m.Odoo)
        api.company = 1
        api.context = {"allowed_company_ids": [1]}
        data = {
            'product.product': [dict(id=1,is_storable=True,tracking='none',uom_id=[1,'Units'],company_id=False,active=True)],
            'stock.location': [dict(id=2,usage='internal',company_id=[1,'Test'],active=True)],
            'uom.uom': [dict(id=1,rounding=1)],
            'stock.quant': [dict(id=3,quantity=10,reserved_quantity=0,inventory_quantity_set=False,is_outdated=False,lot_id=False,package_id=False,owner_id=False,company_id=[1,'Test'])],
        }
        if change:
            change(data)
        api.call = lambda model,method,args,**kw: data[model]
        return api
    def reject(self, change):
        with self.assertRaises(ValueError):
            self.adapter(change).resolve('SADA-001','WH/Stock')
    def test_ambiguous_sku(self):
        self.reject(lambda d:d['product.product'].append(d['product.product'][0]))
    def test_ambiguous_location(self):
        self.reject(lambda d:d['stock.location'].append(d['stock.location'][0]))
    def test_tracked_product(self):
        self.reject(lambda d:d['product.product'][0].update(tracking='serial'))
    def test_nonstorable_product(self):
        self.reject(lambda d:d['product.product'][0].update(is_storable=False))
    def test_missing_quant(self):
        self.reject(lambda d:d.update({'stock.quant':[]}))
    def test_multiple_quants(self):
        self.reject(lambda d:d['stock.quant'].append(d['stock.quant'][0]))
    def test_reserved_stock(self):
        self.reject(lambda d:d['stock.quant'][0].update(reserved_quantity=1))
    def test_pending_adjustment(self):
        self.reject(lambda d:d['stock.quant'][0].update(inventory_quantity_set=True))
    def test_outdated_adjustment(self):
        self.reject(lambda d:d['stock.quant'][0].update(is_outdated=True))
    def test_noninteger_stock(self):
        self.reject(lambda d:d['stock.quant'][0].update(quantity=10.5))
    def test_package_or_owner(self):
        self.reject(lambda d:d['stock.quant'][0].update(owner_id=[8,'Owner']))
    def test_cross_company(self):
        self.reject(lambda d:d['stock.location'][0].update(company_id=[2,'Other']))
    def test_incompatible_uom(self):
        self.reject(lambda d:d['uom.uom'][0].update(rounding=3))
    def test_noninternal_location(self):
        self.reject(lambda d:d['stock.location'][0].update(usage='supplier'))
    def test_write_uses_inventory_inverse_only(self):
        api = self.adapter()
        calls=[]
        api.call=lambda *a,**kw:calls.append((a,kw)) or True
        api.write(3,15)
        self.assertEqual(calls[0][0],('stock.quant','write',[[3],{'inventory_quantity_auto_apply':15}]))
    def test_remote_url_and_wrong_database_rejected_before_network(self):
        for url,db in [('https://example.com','revolv_test'),('http://127.0.0.1:8069','production'),('http://localhost:8069/?x=1','revolv_test')]:
            with self.subTest(url=url,db=db), self.assertRaises(ValueError):
                m.Odoo(url,db,'admin','unused')
    def test_auth_group_check_requires_user_record_ids(self):
        from types import SimpleNamespace
        common = SimpleNamespace(version=lambda: {'server_version_info':[19], 'server_version':'19.0'},
                                 authenticate=lambda *a:2)
        def execute(db, uid, password, model, method, args, kwargs):
            if method == 'read':
                return [{'company_ids':[1], 'company_id':[1,'Test']}]
            if method == 'has_group':
                if args != [[2],'stock.group_stock_user']:
                    raise TypeError('Missing user record ids')
                return True
            return 'database-uuid'
        obj = SimpleNamespace(execute_kw=execute)
        with patch.object(m.xmlrpc.client,'ServerProxy',side_effect=[common,obj]):
            self.assertEqual(m.Odoo('http://127.0.0.1:8069','revolv_test','admin','test').uid,2)
    def test_transport_does_not_retry_post(self):
        t = m.TimeoutTransport(3)
        with patch.object(t,'single_request',side_effect=TimeoutError()) as call:
            with self.assertRaises(TimeoutError):
                t.request('localhost','/xmlrpc/2/object',b'body')
            self.assertEqual(call.call_count,1)

if __name__ == '__main__':
    unittest.main()
