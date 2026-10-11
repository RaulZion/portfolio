"""Reproduce a FIRST demo only on a fresh local fixture; never reset its ledger."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from migrate_inventory import Odoo

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if Path('migration_ledger.csv').exists():
    raise SystemExit('Demo already has a ledger. Preserve evidence and use migrate_inventory.py for safe reruns.')
if not os.getenv('ODOO_PASSWORD'):
    os.environ['ODOO_PASSWORD'] = json.loads(Path('.local_credentials.json').read_text(encoding='utf-8-sig'))['password']
api = Odoo(os.getenv('ODOO_URL','http://127.0.0.1:8069'), os.getenv('ODOO_DB','revolv_test'),
           os.getenv('ODOO_USER','admin'), os.environ['ODOO_PASSWORD'])
evidence = Path('live_demo_evidence.txt')
evidence.write_text('')
def log(label, value):
    line = label + ': ' + (json.dumps(value, sort_keys=True) if not isinstance(value,str) else value)
    print(line, flush=True)
    with evidence.open('a',encoding='utf-8') as stream:
        stream.write(line+'\n')
def report(name):
    with Path(name).open(newline='',encoding='utf-8') as stream:
        return list(csv.DictReader(stream))
def cli(name, *extra, expected=0):
    command = [sys.executable,'migrate_inventory.py','--report',name,*extra]
    result = subprocess.run(command, capture_output=True, text=True)
    log('LIVE CLI '+name, {'exit':result.returncode,'stdout':result.stdout.strip()})
    if result.returncode != expected:
        raise RuntimeError('Unexpected CLI result: '+name)
    rows = report(name)
    log('LIVE REPORT '+name, rows)
    return rows
state = api.resolve('SADA-001','WH/Stock')
if state['actual'] != 10:
    raise SystemExit('Fresh first-run fixture must be 10; existing inventory is never reset.')
pid,qid = state['product_id'],state['quant_id']
def moves():
    return api.call('stock.move','search_count',[[['product_id','=',pid],['state','=','done']]])
log('UTC',datetime.now(timezone.utc).isoformat())
log('Python',sys.version)
log('TARGET','http://127.0.0.1:8069 / revolv_test / LOCAL Community only')
log('ODOO VERSION',api.version)
log('AUTH UID',api.uid)
log('INVENTORY MODULE',api.call('ir.module.module','search_read',[[['name','=','stock']]],fields=['name','state','latest_version']))
log('PRODUCT',api.call('product.product','read',[[pid]],fields=['name','default_code','is_storable','tracking','uom_id']))
log('LOCATION',api.call('stock.location','read',[[state['location_id']]],fields=['complete_name','usage','company_id']))
log('PRE',state)
log('PRE DONE MOVE COUNT',moves())
fields = api.call('stock.quant','fields_get',[],allfields=['quantity','inventory_quantity','inventory_quantity_auto_apply','inventory_quantity_set','is_outdated'],attributes=['type','readonly'])
log('LIVE VERIFIED QUANT FIELDS',fields)
dry = cli('dry_run_report.csv')
assert dry[0]['status']=='DRY_RUN' and dry[0]['actual']=='10'
assert api.resolve('SADA-001','WH/Stock')['actual']==10
before = moves()
log('DRY RUN DONE MOVE COUNT',before)
first = cli('first_run_report.csv','--apply')
assert first[0]['status']=='SUCCESS' and first[0]['baseline']=='10' and first[0]['delta']=='5'
assert first[0]['target']=='15' and first[0]['actual']=='15'
after_first = moves()
assert after_first == before+1
ledger_hash = hashlib.sha256(Path('migration_ledger.csv').read_bytes()).hexdigest()
log('FIRST RUN DONE MOVE COUNT',after_first)
second = cli('rerun_report.csv','--apply')
assert second[0]['status']=='ALREADY_APPLIED' and second[0]['actual']=='15'
after_second = moves()
assert after_second == after_first
log('RERUN DONE MOVE COUNT',after_second)
log('RERUN ADDED MOVES',after_second-after_first)
log('LEDGER UNCHANGED ON RERUN',ledger_hash == hashlib.sha256(Path('migration_ledger.csv').read_bytes()).hexdigest())

# Extra independent fixture demonstrates valid-row continuation in a mixed live batch.
other = api.find('product.product',[['default_code','=','SADA-002']],['name'])
if other:
    raise RuntimeError('Isolation fixture already exists; preserve it')
other_pid = api.call('product.product','create',[{'name':'SADA Isolation Test Component','default_code':'SADA-002','is_storable':True,'tracking':'none'}])
api.call('stock.quant','create',[{'product_id':other_pid,'location_id':state['location_id'],'inventory_quantity_auto_apply':8}],context={**api.context,'inventory_mode':True})
Path('negative_input.csv').write_text('material_sku,quantity_change,location\nSADA-001,abc,WH/Stock\nUNKNOWN,5,WH/Stock\nSADA-001,5,UNKNOWN\nBROKEN,5,WH/Stock,EXTRA\nSADA-002,2,WH/Stock\n',encoding='utf-8')
negative = cli('negative_report.csv','--input','negative_input.csv','--ledger','negative_ledger.csv','--apply',expected=1)
assert [r['status'] for r in negative]==['ERROR','ERROR','ERROR','ERROR','SUCCESS']
assert negative[-1]['actual']=='10'
assert api.resolve('SADA-001','WH/Stock')['actual']==15
log('LIVE NEGATIVE CASES','Bad integer, unknown SKU, unknown location, wrong column count rejected; independent valid row 8+2=10 succeeded.')

# Controlled external-state change is an actual separate local adjustment.
api.write(qid,16)
assert api.resolve('SADA-001','WH/Stock')['actual']==16
conflict_before = moves()
conflict = cli('conflict_report.csv','--apply',expected=1)
assert conflict[0]['status']=='CONFLICT' and conflict[0]['actual']=='16'
assert moves()==conflict_before and api.resolve('SADA-001','WH/Stock')['actual']==16
log('LIVE CONFLICT ADDED MOVES',moves()-conflict_before)
log('LIVE CONFLICT','Separate local adjustment set 16; migration refused to overwrite it.')
api.write(qid,15)
log('TEST CLEANUP','Separate local adjustment restored 15; these two test adjustments are not migration writes.')
final = cli('final_rerun_report.csv','--apply')
assert final[0]['status']=='ALREADY_APPLIED' and final[0]['actual']=='15'
log('FINAL',api.resolve('SADA-001','WH/Stock'))
log('FINAL DONE MOVE COUNT',moves())
result = subprocess.run([sys.executable,'-m','unittest','-v'],capture_output=True,text=True)
Path('automated_test_results.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
log('AUTOMATED TEST / SIMULATED FAILURE',{'exit':result.returncode,'summary':result.stderr.strip().splitlines()[-4:]})
assert result.returncode==0
log('SIMULATED ONLY','Timeout before/after commit, lost RPC response, unavailable readback, pending adjustment, verification mismatch, hard interruption; unit tests, not live network faults.')
log('BROWSER ACTIONS REMAINING','None')
log('COMPLETE','All assertions passed. Task 1 Online stock was not contacted.')
