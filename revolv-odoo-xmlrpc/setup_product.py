"""Provision only the LOCAL demo product; never reset existing inventory."""
import getpass
import os
from pathlib import Path
from migrate_inventory import Odoo, exact_one

api = Odoo(os.getenv('ODOO_URL','http://127.0.0.1:8069'), os.getenv('ODOO_DB','revolv_test'),
           os.getenv('ODOO_USER','admin'), os.getenv('ODOO_PASSWORD') or getpass.getpass('Local Odoo password: '))
print('Odoo', api.version['server_version'], 'authenticated UID', api.uid)
location = exact_one(api.find('stock.location', [['complete_name','=','WH/Stock']],
                            ['usage','company_id']), 'WH/Stock')
products = api.find('product.product', [['default_code','=','SADA-001']], ['name'])
created = not products
pid = api.call('product.product','create',[{'name':'SADA Test Component A','default_code':'SADA-001',
                                          'is_storable':True,'tracking':'none'}]) if created else exact_one(products,'SKU')['id']
quants = api.find('stock.quant', [['product_id','=',pid],['location_id','=',location['id']]], ['quantity'])
if not quants and created and not Path('migration_ledger.csv').exists():
    api.call('stock.quant','create',[{'product_id':pid,'location_id':location['id'],
                                     'inventory_quantity_auto_apply':10}],
             context={**api.context,'inventory_mode':True})
state = api.resolve('SADA-001','WH/Stock')
print('Local fixture:', state)
if state['actual'] != 10:
    print('Existing inventory preserved; fixture was not reset.')
