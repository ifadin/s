import sys

from csgo.collection import load_collections
from csgo.contract import get_best_contracts, to_contract_item
from csgo.inventory import LFInventoryManager, DMInventoryManager
from csgo.price import BSPriceManager, LFPriceManager, DMPriceManager
from csgo.type.model import Model

model = Model.from_str(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else Model.LF
if not model:
    raise AssertionError(f'Could not determine model from string value \'{sys.argv[1]}\'')
else:
    print(f'Loading model {model.name}')
withdrawable_in = int(sys.argv[2]) if len(sys.argv) > 2 else None
collections = load_collections()

if model == Model.BS:
    price_manager = BSPriceManager().load()
    buy_adjustment = 1
    commission = 0.1
    items = {}
if model == Model.LF:
    price_manager = LFPriceManager().load_sales()
    buy_adjustment = 1.05
    commission = 0.05
    items = set([to_contract_item(i, collections) for i in LFInventoryManager().get_inventory()])
if model == Model.DM:
    price_manager = DMPriceManager().load()
    buy_adjustment = 1
    commission = 0.05
    items = set([to_contract_item(i, collections) for i in DMInventoryManager().get_inventory()])

print(f'Loaded {len(items)} items')
print('Calculating contracts')

get_best_contracts(items, price_manager, collections, buy_adjustment, commission,
                   strict=True, withdrawable_in=withdrawable_in)
