import base64
import json
from operator import attrgetter

import requests
from tqdm import tqdm
from typing import Set, Dict, List, NamedTuple, Iterator

from epics.auth import EAuth
from epics.domain import load_collections, TemplateItem, PlayerItem, get_roster_path, Collection
from epics.utils import with_retry, get_http_session


class Card(NamedTuple):
    id: int
    template_id: int
    batch: str
    number: int
    score: float
    entity_type: str
    available: bool = False
    title: str = None

    @property
    def key(self) -> str:
        return f'{self.batch}{self.number}'

    @property
    def entity_key(self) -> str:
        return f'{self.entity_type}-{self.template_id}'


class PlayerService:

    def __init__(self, u_id: int, auth: EAuth, collections: Dict[int, Collection] = None) -> None:
        self.u_id = u_id
        self.auth = auth
        self.collections = load_collections() if collections is None else collections
        self.session = get_http_session()

        self.card_ids_url = (
                base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NvbGxlY3Rpb25zL3VzZXJz'.encode()).decode()
                + f'/{self.u_id}'
        )

    def get_owned_url(self, entity_type: str, collection_id: int) -> str:
        return f'{self.card_ids_url}/{entity_type}ids?categoryId=1&collectionId={collection_id}'

    def get_cards(self, template_id: int, entity_type: str = 'card') -> Dict[int, Card]:
        r = with_retry(
            requests.get(f'{self.card_ids_url}/{entity_type}-templates/{template_id}/{entity_type}s?categoryId=1',
                         auth=self.auth), self.session)

        return {d['id']: Card(d['id'], template_id, d['mintBatch'], d['mintNumber'], d['rating'], entity_type,
                              d['status'] != 'market', d.get(f'{entity_type}Template', {}).get('title'))
                for d in r.json()['data']}

    def get_card_ids(self, collection_id: int, entity_type: str = 'card') -> Dict[str, Set[int]]:
        r = with_retry(requests.get(self.get_owned_url(entity_type, collection_id), auth=self.auth), self.session)

        return {(entity_type + '-' + str(d[f'{entity_type}TemplateId'])): set(d[f'{entity_type}Ids'])
                for d in r.json()['data']}

    def get_missing(self) -> Dict[int, TemplateItem]:
        missing = {}
        for c in tqdm(self.collections.values()):
            owned = set(self.get_card_ids(c.id).keys()) | set(self.get_card_ids(c.id, 'sticker').keys())
            for i in c.items.values():
                if i.key not in owned:
                    missing[i.template_id] = i

        return missing

    def get_owned(self) -> Set[TemplateItem]:
        items = set({i.template_id: i for col in self.collections
                     for i in self.collections[col].items.values()}.values())
        missing = self.get_missing()
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

    def get_top_inventory(self, items: Set[TemplateItem], levels: Set[str] = None) -> Iterator[Card]:
        targets = {i for i in items
                   if not levels or any(i.rarity.lower().startswith(l) for l in levels)}
        for i in targets:
            i: TemplateItem = i
            cards = self.get_cards(i.template_id, i.entity_type).values()
            if cards:
                c = max(iter(cards), key=attrgetter('score'))
                yield c
