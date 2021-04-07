import base64
import os
from operator import attrgetter
from statistics import mean
from time import sleep

import requests
import yaml
from typing import Dict, Set, NamedTuple, Iterator, List, Iterable

from epics.auth import EAuth
from epics.domain import Collection, TemplateItem
from epics.player import Card
from epics.price import PriceService
from epics.utils import with_retry, get_http_session

PACKS_PATH = os.path.join('epics', 'data', 'packs.yaml')


class Chance(NamedTuple):
    tier: str
    chance: float
    group_ids: Set[str]


class MarketPack(NamedTuple):
    id: int
    price: int


class Pack(NamedTuple):
    id: int
    name: str
    chances: List[Chance]
    count: int
    exp: float = None
    updated_at: int = None


class PackItem(NamedTuple):
    id: int
    name: str
    seasons: List[str]


def load_packs(file_path: str = PACKS_PATH) -> Dict[int, Pack]:
    with open(file_path) as f:
        res = yaml.load(f, Loader=yaml.SafeLoader)
        return {
            p_id: Pack(p_id, p['name'], [
                Chance(c['tier'], float(c['chance']), set(c['group_ids'])) for c in p['chances']
            ], int(p['count']), p['exp'], int(p['updated_at']))
            for p_id, p in res.get('packs', {}).items()
        }


def save_packs(packs: Dict[int, Pack], file_path: str = PACKS_PATH):
    with open(file_path, 'w') as f:
        yaml.dump({'packs': {
            p_id: dict(p._asdict(), chances=[dict(c._asdict(), group_ids=list(c.group_ids)) for c in p.chances])
            for p_id, p in packs.items()
        }}, f, default_flow_style=False)


class PackService:
    packs_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3BhY2tzP2NhdGVnb3J5SWQ9MSZ'
                                 'zZWFzb249'.encode()).decode()
    market_packs_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL21hcmtldC90ZW1wbGF0ZXM/cHJpY2U9YXNjJnR5'
                                        'cGU9cGFjayZjYXRlZ29yeUlkPTEmc2Vhc29uPQ=='.encode()).decode()
    market_item_url = base64.b64decode('aHR0cHM6Ly9hcHAuZXBpY3MuZ2cvY3Nnby9tYXJrZXRwbGFjZS9wYWNrLw=='.encode()).decode()
    user_packs_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3BhY2tzL3VzZXI/Y2F0ZWdvcnlJZD0x'.encode()).decode()
    open_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3BhY2tzL29wZW4yP2NhdGVnb3J5SWQ9MQ=='.encode()).decode()

    def __init__(self, collections: Dict[int, Collection], packs: Dict[int, Pack], auth: EAuth) -> None:
        self.collections = collections
        self.packs = packs
        self.auth = auth
        self.p_service = PriceService(self.auth)
        self.session = get_http_session()

        self._group_item_map = self.calculate_group_item_map(self.collections) if self.collections else None

    def get_packs(self, s_id: int = 2020) -> Iterator[Pack]:
        next_page = True
        page_num = 1
        while next_page:
            data = self.request_packs(s_id, page_num).get('data', [])
            next_page = len(data) == 100
            page_num += 1
            for p in data:
                chances: Dict[str, Chance] = {}
                for c in p['treatmentsChance']:
                    group_id = c['treatmentId'].replace('treatment', 'card')
                    k = (c['tier'], c['chance'])
                    chances[k] = Chance(
                        c['tier'],
                        c['chance'],
                        (chances[k].group_ids if k in chances else set()) | {group_id}
                    )

                yield Pack(p['id'], p['name'], self.normalize_chances(list(chances.values())), p['entityCount'])

    def request_packs(self, s_id: int, page_num: int) -> dict:
        r = requests.get(f'{self.packs_url}{s_id}&page={page_num}', auth=self.auth)

        if r.status_code == 429:
            sleep(3)
            return self.request_packs(s_id, page_num)

        r.raise_for_status()
        return r.json()

    def get_user_packs(self) -> Iterable[PackItem]:
        page = 1
        while page is not None:
            res = self.request_user_packs(page).get('data', {})
            page = page + 1 if res.get('total', 0) > page * 500 else None
            for p in res.get('packs', []):
                yield PackItem(p['id'], p['packTemplate']['name'], p['packTemplate']['properties']['seasons'])

    def request_user_packs(self, page_num: int = 1) -> dict:
        return with_retry(requests.get(f'{self.user_packs_url}&page={page_num}', auth=self.auth), self.session).json()

    def open_pack(self, pack_id: int) -> Set[Card]:
        res = with_retry(requests.post(f'{self.open_url}', json={'packId': pack_id}, auth=self.auth),
                         self.session).json()

        return {Card(o['id'], o['cardTemplate']['id'], o['mintBatch'], o['mintNumber'], o['rating'], o['type'],
                     title=o['cardTemplate'].get('title'))
                for o in (res.get('data', {}).get('cards', []) + res.get('data', {}).get('stickers', []))}

    @staticmethod
    def normalize_chances(chances: List[Chance]) -> List[Chance]:
        if not chances:
            return chances

        chances = sorted(chances, key=attrgetter('chance'))
        eps = 0.001
        diff = 100 - sum(c.chance for c in chances) + eps
        while diff >= chances[0].chance:
            filler = next((c for c in reversed(chances) if c.chance <= diff))
            chances.append(filler)
            chances = sorted(chances, key=attrgetter('chance'))
            diff = 100 - sum(c.chance for c in chances) + eps

        return chances

    def get_market_packs(self, s_id: int = 2020) -> Iterator[MarketPack]:
        next_page = True
        page_num = 1
        while next_page:
            data = self.request_market_packs(s_id, page_num).get('data', [])
            next_page = len(data['templates']) == 40
            page_num += 1
            for p in data['templates']:
                yield MarketPack(p['entityTemplateId'], p['lowestPrice'])

    def request_market_packs(self, s_id: int, page_num: int) -> dict:
        r = requests.get(f'{self.market_packs_url}{s_id}&page={page_num}', auth=self.auth)

        if r.status_code == 429:
            sleep(3)
            return self.request_market_packs(s_id, page_num)

        r.raise_for_status()
        return r.json()

    def get_group_items(self, group_id: str) -> Set[TemplateItem]:
        return self._group_item_map.get(group_id, set())

    def get_exp(self, p: Pack) -> float:
        exp = 0
        for c in p.chances:
            sales = []
            for g in c.group_ids:
                for i in self.get_group_items(g):
                    s = self.p_service.get_offers(i.template_id, i.entity_type).avg_sales
                    if s:
                        sales.append(s)
            exp += c.chance / 100.0 * (mean(sales) if sales else 0)
        return exp * p.count

    @staticmethod
    def calculate_group_item_map(collections: Dict[int, Collection]) -> Dict[str, Set[TemplateItem]]:
        mp: Dict[str, Set[TemplateItem]] = {}
        for c in collections:
            for i in collections[c].items.values():
                mp[i.group_key] = mp.get(i.group_key, set()) | {i}

        return mp

    @classmethod
    def get_item_url(cls, p_id: int) -> str:
        return f'{cls.market_item_url}{p_id}'
