import base64
from operator import attrgetter

import requests
from tqdm import tqdm
from typing import List, Dict, Optional, Set, Collection, NamedTuple

from epics.auth import EAuth
from epics.domain import TemplateItem
from epics.pack import PackService
from epics.player import PlayerService, Card
from epics.price import PriceService
from epics.upgrade import load_inventory, InventoryItem, save_inventory
from epics.user import u_a
from epics.utils import with_retry, get_http_session


class PResult(NamedTuple):
    pack_id: int
    pack_name: str
    cards: Set[Card]


class Trader:
    offer_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3RyYWRlL2NyZWF0ZS1vZmZlcj9jYXRlZ29yeUlkPTE='.encode()).decode()

    accept_offer_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3RyYWRlL2FjY2VwdC1vZmZlcj9jYXRlZ29yeUlkPTE='.encode()).decode()

    def __init__(self, u_id: int, auth: EAuth,
                 price_service: PriceService,
                 player_service: PlayerService,
                 pack_service: PackService,
                 player_service_b: PlayerService = None) -> None:
        self.u_id = u_id
        self.auth = auth

        self.price_service = price_service
        self.player_service = player_service
        self.pack_service = pack_service
        self.player_service_b = player_service_b
        self.tradable = self.player_service_b is not None

        self.session = get_http_session()
        self._inventory = None

    @property
    def inventory(self) -> Dict[int, InventoryItem]:
        self._inventory = self._inventory if self._inventory else load_inventory()
        return self._inventory

    def sell_items(self, items: Collection[TemplateItem]) -> Dict[Card, int]:
        bonus = {'a': 2, 'b': 1}
        sold = {}
        for i in items:
            i: TemplateItem = i
            cards: List[Card] = list(
                c for c in self.player_service.get_cards(i.template_id, i.entity_type).values() if c.available)
            if cards and len(cards) > 1:
                offers = self.price_service.get_offers(i)
                if offers:
                    min_price_offer = min(offers, key=attrgetter('offer_value'))
                    m_price = min_price_offer.offer_value
                    sell_price = ((int(min_price_offer.avg_sales) + m_price) // 2
                                  if min_price_offer.avg_sales and int(min_price_offer.avg_sales) > m_price
                                  else m_price)
                    for c in sorted(cards, key=attrgetter('score'), reverse=True)[1:]:
                        b_bonus = bonus.get(c.batch.lower(), 0)
                        n_bonus = 1 if 500 <= c.number < 1000 else (2 if c.number < 500 else 0)
                        price = ((sell_price - 1) if sell_price > 1 else sell_price) + b_bonus
                        if c.batch.lower() == 'a':
                            price += n_bonus
                        if price > 1:
                            price = 9 if price == 10 or price == 11 else price
                            self.price_service.sell_item(c.id, price, c.entity_type)
                            sold[c] = price

        return sold

    def open_and_manage(self, amount: int, s_ids: List[str] = None, pattern: str = None,
                        trade: bool = False, extra: Set[Card] = set()) -> Set[Card]:
        items: Set[Card] = set()
        for p in self.open_packs(amount, s_ids, pattern):
            print(f'[{self.u_id}] Opened {p.pack_name}:')
            for c in p.cards:
                items.add(c)
                print(f'    - {c.title}({c.template_id}) {c.key}')
        if self.u_id == u_a:
            self.update_inventory(items)
        if trade and items:
            self.trade(items | extra)
        sold = self.sell_items({TemplateItem(c.template_id, c.title, None, c.entity_type) for c in items})
        self.print_sold(sold)
        return items

    def open_packs(self, amount: int, s_ids: List[str] = None, pattern: str = None) -> Collection[PResult]:
        if not amount:
            return []

        packs = sorted((p for p in self.pack_service.get_user_packs()
                        if (not s_ids or any(s in p.seasons for s in s_ids)) and (
                                not pattern or pattern in p.name.lower())), key=attrgetter('id'))

        if not packs:
            print(f'[{self.u_id}] No packs found for {s_ids} and {pattern}')
            return []

        return [PResult(p.id, p.name, self.pack_service.open_pack(p.id)) for p in packs[0:amount]]

    def trade(self, items: Set[Card] = None, offer_limit: int = 5):
        if not self.tradable:
            return

        item_ids = {i.template_id for i in items} if items else {}
        if item_ids:
            print(f'Trading {item_ids}')

        candidates, candidates_b = set(), set()
        for i in tqdm(sorted({
            it for c in self.player_service.collections.values() for it in c.items.values()
            if not item_ids or it.template_id in item_ids},
                key=attrgetter('template_id'))):
            i: TemplateItem = i
            cards = sorted((
                c for c in self.player_service.get_cards(i.template_id, i.entity_type).values() if c.available),
                key=attrgetter('score'), reverse=True)
            cards_b = sorted((
                c for c in self.player_service_b.get_cards(i.template_id, i.entity_type).values() if c.available),
                key=attrgetter('score'), reverse=True)

            if not cards and cards_b:
                candidates_b.add(cards_b[0])

            if not cards_b and len(cards) > 1:
                candidates.add(cards[1])

            if cards and cards_b and cards_b[0].score > cards[0].score:
                candidates_b.add(cards_b[0])

            if len(candidates) + len(candidates_b) > offer_limit:
                self.trade_items(candidates, candidates_b)
                candidates, candidates_b = set(), set()
        self.trade_items(candidates, candidates_b)

    def trade_items(self, out_items: Collection[Card], in_items: Collection[Card]):
        if not out_items and not in_items:
            return

        f_item_a, f_item_b = None, None
        if not out_items:
            f_item_a = self.get_fallback_item(self.player_service)
            if not f_item_a:
                raise AssertionError('Could not get a fallback item A')
            out_items.add(f_item_a)
        if not in_items:
            f_item_b = self.get_fallback_item(self.player_service_b)
            if not f_item_b:
                raise AssertionError('Could not get a fallback item B')
            in_items.add(f_item_b)
        items = out_items | in_items
        trade_id = self.send_offer(items)
        if not trade_id:
            raise AssertionError('Could not send an offer')
        print(f'Traded:')

        for i in out_items:
            print(f'    {i.title}({i.template_id}) {i.batch}{i.number}   -> ')
        for i in in_items:
            print(f'    <- {i.title}({i.template_id}) {i.batch}{i.number}')

        self.accept_offer(trade_id)
        self.update_inventory(in_items - {f_item_b})
        sold = self.sell_items({TemplateItem(i.template_id, i.title, None, i.entity_type) for i in in_items})
        self.print_sold(sold)

    @staticmethod
    def get_fallback_item(s: PlayerService, fallback_id: int = 2969) -> Optional[Card]:
        for key, items in s.get_card_ids(fallback_id).items():
            if len(items) > 1:
                cards = {c for c in s.get_cards(key.split('-')[1]).values() if c.available}
                if cards and len(cards) > 1:
                    return sorted(cards, key=attrgetter('score'))[0]

        return None

    def send_offer(self, cards: Set[Card]) -> Optional[int]:
        if not cards:
            return None
        r = with_retry(requests.post(self.offer_url, auth=self.player_service.auth,
                                     json={'user2Id': self.player_service_b.u_id,
                                           'user1Balance': 0, 'user2Balance': 0,
                                           'entities': [{'id': c.id, 'type': c.entity_type} for c in cards]}),
                       self.session)

        if r.ok and r.json()['success']:
            return r.json()['data'].get('tradeId')

        return None

    def accept_offer(self, offer_id: int) -> bool:
        r = with_retry(requests.patch(self.accept_offer_url, auth=self.player_service_b.auth,
                                      json={'tradeId': offer_id}), self.session)

        return r.ok and r.json().get('success')

    def update_inventory(self, items: Set[Card]):
        for i in items:
            inv = InventoryItem(i.template_id, i.entity_type, i.key, i.score)
            if inv.key not in self.inventory or self.inventory[inv.key].score < inv.score:
                self.inventory[inv.key] = inv
        if items:
            save_inventory(set(self.inventory.values()))

    @staticmethod
    def print_sold(items: Dict[Card, int]):
        for c, price in list(items.items()):
            print(f'    - put {c.title} {c.key} for {price}')
