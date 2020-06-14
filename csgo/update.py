from csgo.bs.updater import BSUpdater
from csgo.collection import load_collections
from csgo.dm.updater import DMUpdater


def update_bs_prices():
    collections = load_collections()
    updater = BSUpdater(collections)
    updater.update_prices()


def update_bs_sales():
    collections = load_collections()
    updater = BSUpdater(collections)
    updater.update_sales()


def update_dm_prices():
    collections = load_collections()
    updater = DMUpdater(collections)
    updater.update_prices()


def update_dm_sales():
    collections = load_collections()
    updater = DMUpdater(collections)
    updater.update_sales()
