import base64
from asyncio import AbstractEventLoop
from itertools import chain
from operator import itemgetter, attrgetter

from tqdm import tqdm
from typing import Dict, Set, List, Union

from epics.auth import EAuth
from epics.domain import Rating, load_teams, get_player_ratings, TemplateItem, Collection, load_collections
from epics.player import PlayerService
from epics.price import PriceService, MarketTarget


class Tracker:
    item_url = base64.b64decode('aHR0cHM6Ly9hcHAuZXBpY3MuZ2cvY3Nnby9tYXJrZXRwbGFjZQ=='.encode()).decode()

    def __init__(self, u_id: int, auth: EAuth) -> None:
        self.auth = auth
        self.p_service = PlayerService(u_id, auth=self.auth)
        self.price_service = PriceService(auth=self.auth)

        self._collections = None

    @property
    def collections(self) -> Dict[int, Collection]:
        if self._collections:
            return self._collections
        self._collections = load_collections()
        return self._collections

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

    def get_market_targets(self, items_ids: Set[TemplateItem],
                           price_margin: float, score_margin: float, max_price: int) -> Dict[int, MarketTarget]:
        targets = {}
        for i in items_ids:
            s = self.price_service.get_sales(i.template_id, i.entity_type)
            if s.offers:
                min_offer_id, min_offer, score = s.offers[0]
                if min_offer <= max_price:
                    m = MarketTarget(min_offer_id, min_offer, score, i, s.avg_sales)
                    if m.margin and m.margin >= price_margin:
                        targets[min_offer_id] = m
                    else:
                        max_score_offer_id, max_score_offer, max_score = sorted(s.offers, key=lambda o: o[1] / o[2])[0]
                        if max_score_offer <= max_price:
                            m = MarketTarget(max_score_offer_id, max_score_offer, max_score, i, s.avg_sales)
                            if m.score_margin and m.score_margin <= score_margin:
                                targets[max_score_offer_id] = m
        return targets

    def upgrade(self, pps_threshold: float = 0.325, buy_threshold: int = 9):
        targets = set({i.template_id: i for col in self.collections
                       for i in self.collections[col].items.values()
                       if i.rarity.lower()[0:4] in {'abun', 'rare'}}.values())

        for t in tqdm(targets):
            cards = self.p_service.get_cards(t.template_id, t.entity_type)
            if not cards:
                continue

            c = max(cards.values(), key=attrgetter('score'))
            if c.key[0] == 'A' and int(c.key[1:]) < (2000 if t.rarity.lower().startswith('abun') else 300):
                continue

            s = self.price_service.get_sales(t.template_id, t.entity_type, exhaustive=True)
            if s.offers:
                min_price = s.offers[0][1] - 1
                o = min((o for o in s.offers if o[2] > c.score), default=None,
                        key=lambda o: (o[1] - (min_price if o[1] > 3 else 0)) / (o[2] - c.score) * 10.0)
                if o:
                    o_id, o_price, o_score = o
                    margin = (o_score - c.score) * 10.0
                    pps = (o_price - (min_price if o_price > 3 else 0)) / margin
                    if 0 < pps <= pps_threshold:
                        details = f'{t.template_title} {c.score}->{o_score} (+{margin:.2f}) P:{o_price} ({pps:.2f}pps)'
                        if o_price <= buy_threshold:
                            self.price_service.buy_item(o_id, o_price)
                            print(f'Upgraded {details}')
                            if min_price >= 3:
                                for cc in cards.values():
                                    self.price_service.sell_item(cc.id, min_price, cc.entity_type)
                        else:
                            url = self.get_mplace_url(t.entity_type, t.template_id)
                            print(f'{url}/{o_id} {details}')

    def track_items(self, items_ids: Set[TemplateItem], price_margin: float, score_margin: float,
                    max_price: int, buy_threshold: int):
        targets = self.get_market_targets(items_ids, price_margin, score_margin, max_price)
        for t in targets.values():
            item_details = f'{t.item.template_title} for {t.offer_value} ' \
                           f'(s:{int(t.offer_score * 10)}/{t.score_margin:.3f} ' \
                           f'avg:{int(t.avg_sales)} m:{int(t.margin * 100) if t.margin else None}%)'
            if t.offer_value <= buy_threshold:
                self.price_service.buy_item(t.offer_id, t.offer_value)
                print(f'Bought {item_details}')
            else:
                url = self.get_mplace_url(t.item.entity_type, t.item.template_id)
                print(f'{url} {item_details}')

    def track(self, price_margin: float, score_margin: float,
              max_price: int, buy_threshold: int):
        m = self.p_service.get_missing(blacklist_names={
            'purp', 'silv', 'gold', 'diam', 'lege', 'master', 'entr',
            'cs', 'onboa', 'rifl', 'shar', 'snip', 'sup'
        }, whitelist_ids={4357})
        for item in tqdm(list(chain.from_iterable(m.values()))):
            self.track_items({item}, price_margin, score_margin, max_price, buy_threshold)

    def schedule_track(self, l: AbstractEventLoop,
                       price_margin: float, score_margin: float,
                       max_price: int, buy_threshold: int):
        min_15 = 900
        try:
            self.track(price_margin, score_margin, max_price, buy_threshold)
        except Exception as e:
            print(e)
            print(f'Rescheduling due to error')
            return l.call_later(5, self.schedule_track, l, price_margin, score_margin, max_price, buy_threshold)

        print(f'Next in {min_15} seconds')
        return l.call_later(min_15, self.schedule_track, l, price_margin, score_margin, max_price, buy_threshold)

    def start(self, l: AbstractEventLoop, price_margin: float, score_margin: float, buy_threshold: int,
              max_price: int = 5000):

        l.call_later(3500, self.auth.refresh_token)
        l.call_soon(self.schedule_track, l, price_margin, score_margin, max_price, buy_threshold)
