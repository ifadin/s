import base64
from asyncio import AbstractEventLoop
from operator import itemgetter, attrgetter
from random import sample

from tqdm import tqdm
from typing import Dict, Set, List, Union, Iterable, Optional

from epics.auth import EAuth
from epics.domain import Rating, load_teams, get_player_ratings, TemplateItem, Collection
from epics.player import PlayerService
from epics.price import PriceService, MarketOffer
from epics.upgrade import load_inventory, save_inventory, InventoryItem


class Tracker:
    item_url = base64.b64decode('aHR0cHM6Ly9hcHAuZXBpY3MuZ2cvY3Nnby9tYXJrZXRwbGFjZQ=='.encode()).decode()

    def __init__(self, u_id: int, auth: EAuth, collections: Dict[int, Collection], p_auth: EAuth = None) -> None:
        self.auth = auth
        self.collections = collections

        self.p_service = PlayerService(u_id, self.auth, self.collections)
        self.price_service = PriceService(auth=(p_auth if p_auth else self.auth))

    @classmethod
    def get_mplace_url(cls, item_type: str, item_id: int) -> str:
        return f'{cls.item_url}/{item_type}/{item_id}'

    @staticmethod
    def get_track_ids(players: Dict[str, List[Rating]], targets: Union[int, Dict[str, int]]) -> Dict[str, Set[Rating]]:
        if isinstance(targets, int):
            return {p: {r for r in ratings if r.rating >= targets} for p, ratings in players.items()}

        return {t: {r for r in players[t] if r.rating >= rating} for t, rating in targets.items()}

    def get_items(self, targets: Union[Dict[str, int], int]):
        teams = load_teams()
        ratings = get_player_ratings(teams)
        ids = self.get_track_ids(ratings, targets)

        results = []
        for ratings in tqdm(ids.values()):
            for r in ratings:
                t = self.price_service.get_trend(r.template_id, 'card')
                if t is not None:
                    min_offer, avg_sales, close_offers, next_offer = t
                    rev = avg_sales - min_offer if not next_offer else min(avg_sales - min_offer,
                                                                           next_offer - min_offer)
                    results.append((r, rev, rev / min_offer, min_offer, close_offers))

        for r, rev, margin, min_offer, close_offers in sorted(results, key=itemgetter(2)):
            if margin > 0 and (30 <= min_offer):
                url = self.get_mplace_url('card', r.template_id)
                print(f'{url} {r.rating} ' + (f'[{min_offer}] ' if min_offer <= 5 else '') +
                      f'{r.template_title} {min_offer} ({int(rev)}/{int(margin * 100)}%) {close_offers}')

    def get_market_target(self, item: TemplateItem,
                          price_margin: float, pps_threshold: float, max_price: int) -> Optional[MarketOffer]:
        offers = self.price_service.get_offers(item, exhaustive=True)
        if offers:
            pps_offer = max((o for o in offers if o.offer_value < max_price and o.pps and o.pps <= pps_threshold),
                            key=attrgetter('offer_score'), default=None)
            if pps_offer:
                return pps_offer
            else:
                min_price_offer = min((o for o in offers if o.offer_value < max_price),
                                      key=attrgetter('offer_value'), default=None)
                if min_price_offer and min_price_offer.margin and min_price_offer.margin >= price_margin:
                    return min_price_offer

    def sell(self, pps_threshold: float):
        owned_items = self.p_service.get_owned()
        for i in tqdm(owned_items):
            o = min(self.price_service.get_offers(i), key=attrgetter('offer_value'), default=None)
            if o and o.pps > pps_threshold:
                p = int(o.offer_value * 1.2)
                for c in self.p_service.get_cards(i.template_id, i.entity_type).values():
                    if c.available:
                        print(f'Selling {i.template_title} {c.key} for {p}')
                        self.price_service.sell_item(c.id, p, i.entity_type)

    def upgrade(self, pps_threshold: float = 0.5, buy_threshold: int = 20, levels: Set[str] = None):
        def has_low_key(i: InventoryItem) -> bool:
            if not i:
                return False

            return i.mint[0] == 'A' and int(i.mint[1:]) < 100

        def get_min_price(offers: Iterable[MarketOffer], default: int) -> int:
            o = set(offers)
            if not o:
                return default
            return min(o, key=attrgetter('offer_value')).offer_value - 1

        def get_adjusted_price(p: int) -> int:
            p = 9 if p == 10 or p == 11 else p
            p = p if p < 10 else int(p * 0.85)
            return p

        def get_pps(o: MarketOffer, sell_price: int) -> float:
            return (o.offer_value - (sell_price if sell_price > 1 else 0)) / (o.offer_score - i.score) / 10.0

        collection = {i.key: i for col in self.collections.values() for i in col.items.values()
                      if not levels or any(i.rarity.lower().startswith(l) for l in levels)}
        inventory = load_inventory()
        targets = [(collection[i.key], i) for i in inventory.values() if i.key in collection and not has_low_key(i)]
        for t, i in tqdm(sample(targets, len(targets))):
            t: TemplateItem = t
            i: InventoryItem = i
            offers = self.price_service.get_offers(t, exhaustive=True)
            if offers:
                upgrades = {
                    o for o in offers
                    if o.offer_score > i.score and get_pps(o, get_adjusted_price(
                        get_min_price((of for of in offers if of.offer_id != o.offer_id),
                                      o.offer_value))) <= pps_threshold
                }
                if upgrades:
                    o = max(upgrades, key=attrgetter('offer_score'))
                    margin = (o.offer_score - i.score) * 10.0
                    sell_price = get_min_price((of for of in offers if of.offer_id != o.offer_id), o.offer_value)
                    sell_price = 9 if sell_price == 10 or sell_price == 11 else sell_price
                    pps = get_pps(o, get_adjusted_price(sell_price))
                    details = f'{t.template_title} {i.score}->{o.offer_score} (+{margin:.2f}) P:{o.offer_value} ({pps:.2f}pps)'
                    if o.offer_value <= buy_threshold:
                        cards = self.p_service.get_cards(t.template_id, t.entity_type)
                        upgraded = self.price_service.buy_item(o.offer_id, o.offer_value)
                        if upgraded:
                            print(f'Upgraded {details}')

                            inventory[i.key] = InventoryItem(i.template_id, i.entity_type, o.offer_mint, o.offer_score)
                            save_inventory(inventory.values())
                            if sell_price > 1:
                                for cc in cards.values():
                                    if cc.available:
                                        self.price_service.sell_item(cc.id, sell_price, cc.entity_type)
                    else:
                        url = self.get_mplace_url(t.entity_type, t.template_id)
                        print(f'{url}/{o.offer_id} {details}')

    def track_items(self, items: Set[TemplateItem], price_margin: float, pps_threshold: float,
                    max_price: int, buy_threshold: int):
        for i in items:
            t = self.get_market_target(i, price_margin, pps_threshold, max_price)
            if t:
                item_details = f'{t.item.template_title} for {t.offer_value} ' \
                               f'(s:{int(t.offer_score * 10)}/{t.pps:.3f} ' \
                               f'avg:{int(t.avg_sales) if t.avg_sales else None} ' \
                               f'm:{int(t.margin * 100) if t.margin else None}%)'
                if t.offer_value <= buy_threshold:
                    self.price_service.buy_item(t.offer_id, t.offer_value)
                    print(f'Bought {item_details}')
                    if t.pps > pps_threshold and t.avg_sales and t.avg_sales > 50:
                        s_price = int(t.avg_sales)
                        self.price_service.sell_item(t.card_id, s_price, t.item.entity_type)
                        print(f'Put for {s_price}')
                else:
                    url = self.get_mplace_url(t.item.entity_type, t.item.template_id)
                    print(f'{url} {item_details}')

    def track(self, price_margin: float, pps: float, max_price: int, buy_threshold: int):
        m = self.p_service.get_missing()
        self.track_items(tqdm(set(m.values())), price_margin, pps, max_price, buy_threshold)

    def schedule_track(self, l: AbstractEventLoop,
                       price_margin: float, pps: float,
                       max_price: int, buy_threshold: int, interval: int):
        try:
            self.track(price_margin, pps, max_price, buy_threshold)
        except Exception as e:
            print(e)
            print(f'Rescheduling due to error')
            return l.call_later(5, self.schedule_track, l, price_margin, pps, max_price, buy_threshold, interval)

        print(f'Next in {interval} seconds')
        return l.call_later(interval, self.schedule_track, l, price_margin, pps, max_price, buy_threshold, interval)

    def start(self, l: AbstractEventLoop, price_margin: float, pps: float, buy_threshold: int,
              max_price: int = 5000, interval: int = 900):

        l.call_later(3500, self.auth.refresh_token)
        l.call_soon(self.schedule_track, l, price_margin, pps, max_price, buy_threshold, interval)
