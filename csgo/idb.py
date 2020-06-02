import json
from typing import Dict

import yaml

from csgo.type.idb import IDBPaintKit, IDBCollection, IDBRarity, IDBSkin, IDBWeapon


def load_idb_collections() -> Dict[int, IDBCollection]:
    with open('csgo/idb/collections.json') as f:
        return {c['id']: IDBCollection(c['id'], c['name'], c['tag']) for c in json.loads(f.read())}


def load_idb_paintkits() -> Dict[int, IDBPaintKit]:
    with open('csgo/idb/paintkits.json') as f:
        return {p['id']: IDBPaintKit(p['id'], p['tag'], p['minFloat'], p['maxFloat']) for p in json.loads(f.read())}


def load_idb_rarities() -> Dict[int, IDBRarity]:
    with open('csgo/idb/rarities.json') as f:
        return {r['id']: IDBRarity(r['id'], r['name'], r['tag']) for r in json.loads(f.read())}


def load_idb_skins() -> Dict[int, IDBSkin]:
    with open('csgo/idb/skins.json') as f:
        return {s['id']: IDBSkin(s['id'], s['weaponId'], s['rarityId'], s['collectionId'], s['paintkitId'])
                for s in json.loads(f.read())}


def load_idb_weapons() -> Dict[int, IDBWeapon]:
    with open('csgo/idb/weapons.json') as f:
        return {w['id']: IDBWeapon(w['id'], w['name'], w['tag']) for w in json.loads(f.read())}


def update_from_idb():
    idb_collections = load_idb_collections()
    paintkits = load_idb_paintkits()
    rarities = load_idb_rarities()
    skins = load_idb_skins()
    weapons = load_idb_weapons()
    collections = {}

    for skin in skins.values():
        collection = idb_collections[skin.collection_id]
        collection_name = collection.tag
        if collection_name not in collections:
            collections[collection_name] = {'items': {}}

        weapon = weapons[skin.weapon_id]
        paintkit = paintkits[skin.paintkit_id]
        rarity = rarities[skin.rarity_id]
        item_name = f'{weapon.tag} | {paintkit.tag}'
        collections[collection_name]['items'][item_name] = {
            'rarity': rarity.id - 1,
            'min_float': paintkit.min_float,
            'max_float': paintkit.max_float
        }

    with open('csgo/collections.yaml', 'w') as f:
        yaml.dump({'collections': collections}, f, default_flow_style=False)
