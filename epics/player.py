import base64
import json
from itertools import chain
from operator import attrgetter
from time import sleep

import requests
from tqdm import tqdm
from typing import Set, Dict, List, NamedTuple

from epics.auth import EAuth
from epics.domain import load_collections, TemplateItem, PlayerItem, get_roster_path, Collection


class Card(NamedTuple):
    id: int
    template_id: int
    key: str
    score: float
    entity_type: str
    available: bool = False


class PlayerService:

    def __init__(self, u_id: int, auth: EAuth, collections: Dict[int, Collection] = None) -> None:
        self.u_id = u_id
        self.auth = auth
        self.collections = load_collections() if collections is None else collections

        self.card_ids_url = (
                base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NvbGxlY3Rpb25zL3VzZXJz'.encode()).decode()
                + f'/{self.u_id}'
        )

    def get_owned_url(self, entity_type: str, collection_id: int) -> str:
        return f'{self.card_ids_url}/{entity_type}ids?categoryId=1&collectionId={collection_id}'

    def get_cards(self, template_id: int, entity_type: str = 'card') -> Dict[int, Card]:
        r = requests.get(f'{self.card_ids_url}/{entity_type}-templates/{template_id}/{entity_type}s?categoryId=1',
                         auth=self.auth)

        if r.status_code == 429:
            print(f'429: sleeping...')
            sleep(3)
            return self.get_cards(template_id, entity_type)

        r.raise_for_status()
        return {d['id']: Card(d['id'], template_id, d['mintBatch'] + str(d['mintNumber']), d['rating'], entity_type,
                              d['status'] == 'available')
                for d in r.json()['data']}

    def get_card_ids(self, collection_id: int, entity_type: str = 'card') -> Dict[str, Set[int]]:
        r = requests.get(self.get_owned_url(entity_type, collection_id), auth=self.auth)

        if r.status_code == 429:
            print(f'429: sleeping...')
            sleep(3)
            return self.get_card_ids(collection_id, entity_type)

        r.raise_for_status()
        return {(entity_type + '-' + str(d[f'{entity_type}TemplateId'])): set(d[f'{entity_type}Ids'])
                for d in r.json()['data']}

    def get_missing(self, blacklist_names: Set[str] = None, whitelist_ids=None) -> Dict[int, Set[TemplateItem]]:
        if whitelist_ids is None:
            whitelist_ids = {}
        if blacklist_names is None:
            blacklist_names = set()

        missing: Dict[int, Set[TemplateItem]] = {}
        for c in tqdm(self.collections.values()):
            if c.id in whitelist_ids or all((not c.name.lower().startswith(ignored) for ignored in blacklist_names)):
                owned = set(self.get_card_ids(c.id).keys()) | set(self.get_card_ids(c.id, 'sticker').keys())
                for i in c.items.values():
                    if i.key not in owned:
                        missing[c.id] = missing.get(c.id, set()) | {
                            TemplateItem(i.template_id, i.template_title, i.group_id, i.entity_type)
                        }

        return missing

    def get_owned(self, blacklist_names: Set[str] = None, whitelist_ids=None) -> Set[TemplateItem]:
        items = set({i.template_id: i for col in self.collections
                     for i in self.collections[col].items.values()}.values())
        missing = set(i.template_id for i in chain.from_iterable(
            self.get_missing(blacklist_names, whitelist_ids).values()
        ))
        return {i for i in items if i.template_id not in missing}

    def get_owned_roster(self) -> Dict[int, PlayerItem]:
        roster = self.load_roster()
        return {
            i.template_id: i for col in list(self.collections.values())
            for i in list(col.items.values())
            if isinstance(i, PlayerItem) and i.template_id in roster
        }

    def load_roster(self) -> List[int]:
        with open(get_roster_path(self.u_id)) as f:
            return json.load(f)

    def get_top_inventory(self, levels: Set[str] = None) -> Dict[int, Card]:
        inv = {}
        targets = {i for c in self.collections.values() for i in c.items.values()
                   if not levels or any(i.rarity.lower().startswith(l) for l in levels)}
        for i in tqdm(targets, desc='Items'):
            i: TemplateItem = i
            cards = self.get_cards(i.template_id, i.entity_type).values()
            if cards:
                c = max(iter(cards), key=attrgetter('score'))
                inv[i.key] = c
        return inv
