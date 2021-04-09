from operator import attrgetter

from typing import List, Dict

from epics.auth import EAuth
from epics.domain import TemplateItem
from epics.pack import PackService
from epics.player import PlayerService, Card
from epics.price import PriceService


class Trader:

    def __init__(self, u_id: int, auth: EAuth, price_service: PriceService, player_service: PlayerService,
                 pack_service: PackService) -> None:
        self.u_id = u_id
        self.auth = auth

        self.price_service = price_service
        self.player_service = player_service
        self.pack_service = pack_service

    def sell_items(self, items: List[TemplateItem]) -> Dict[Card, int]:
        bonus = {'a': 3, 'b': 2, 'c': 1}
        sold = {}
        for i in items:
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

    def open_packs(self, amount: int, s_ids: List[str] = None, pattern: str = None):
        if not amount:
            return

        packs = sorted((p for p in self.pack_service.get_user_packs()
                        if (not s_ids or any(s in p.seasons for s in s_ids)) and (
                                not pattern or pattern in p.name.lower())), key=attrgetter('id'))

        if not packs:
            print(f'[{self.u_id}] No packs found for {s_ids} and {pattern}')
            return

        for p in packs[0:amount]:
            cards = self.pack_service.open_pack(p.id)
            print(f'[{self.u_id}] Opened {p.name}:')
            for c in cards:
                print(f'    - {c.title} {c.key}')
            sold = self.sell_items([TemplateItem(c.template_id, c.title, None, c.entity_type) for c in cards])
            for c, price in list(sold.items()):
                print(f'[{self.u_id}] Put {c.title} {c.key} for {price}')
