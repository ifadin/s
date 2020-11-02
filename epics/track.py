import asyncio
import base64
import statistics
from asyncio import AbstractEventLoop
from itertools import chain
from operator import itemgetter
from time import sleep

import requests
from tqdm import tqdm
from typing import Dict, Set, List, Optional, Union, Tuple, NamedTuple

from epics.auth import EAuth
from epics.domain import Rating, load_teams, get_player_ratings, TemplateItem
from epics.player import PlayerService
from epics.utils import fail_fast_handler


class MarketItem(NamedTuple):
    template_id: int
    avg_sales: float
    offers: List[Tuple[int, int, int]]


class MarketTarget(NamedTuple):
    offer_id: int
    offer_value: int
    offer_score: int
    item: TemplateItem
    avg_sales: float

    @property
    def margin(self) -> Optional[float]:
        if not self.avg_sales or not self.offer_value:
            return None

        return (self.avg_sales - self.offer_value) / self.avg_sales

    @property
    def score_margin(self) -> Optional[float]:
        if not self.offer_value or not self.offer_score:
            return None

        return self.offer_value / self.offer_score / 10


class Tracker:
    buy_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL21hcmtldC9idXk/Y2F0ZWdvcnlJZD0x'.encode()).decode()
    sales_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL21hcmtldC9idXk/Y2F0ZWdvcnlJZD0xJn'
                                 'BhZ2U9MSZzb3J0PXByaWNlJnR5cGU9Y2FyZCZ0ZW1wbGF0ZUlkPQ=='.encode()).decode()
    item_url = base64.b64decode('aHR0cHM6Ly9hcHAuZXBpY3MuZ2cvY3Nnby9tYXJrZXRwbGFjZS9jYXJkLw=='.encode()).decode()

    def __init__(self) -> None:
        self.auth = EAuth()

    @staticmethod
    def get_track_ids(players: Dict[str, List[Rating]], targets: Union[int, Dict[str, int]]) -> Dict[str, Set[Rating]]:
        if isinstance(targets, int):
            return {p: {r for r in ratings if r.rating >= targets} for p, ratings in players.items()}

        return {t: {r for r in players[t] if r.rating >= rating} for t, rating in targets.items()}

    def request_sales(self, target_id: int) -> dict:
        r = requests.get(self.sales_url + str(target_id), auth=self.auth)

        if r.status_code == 429:
            sleep(3)
            return self.request_sales(target_id)

        r.raise_for_status()
        return r.json()

    @staticmethod
    def trim_mean(tlist: list, ignore_min: int, ignore_max: int) -> Optional[float]:
        if not tlist:
            return None

        return (statistics.mean(tlist)
                if (ignore_min + ignore_max) >= len(tlist)
                else statistics.mean(sorted(tlist)[ignore_min:][:-ignore_max]))

    def get_sales(self, item_id: int) -> MarketItem:
        s = self.request_sales(item_id)
        offers = next(iter(s['data']['market']), [{}])
        sample_size = 12
        avg_sales = self.trim_mean([
            e['price'] for e in s['data'].get('recentSales', [])[0:sample_size]
        ], 2, 2)

        return MarketItem(item_id, avg_sales, [
            (o['marketId'], o['price'], o['card']['rating'])
            for o in offers if o.get('marketId') and o.get('price')
        ])

    def get_trend(self, target_id: int) -> Optional[Tuple[float, float, float, Optional[float]]]:
        s = self.request_sales(target_id)
        offers = next(iter(s['data']['market']), [{}])
        min_offer = offers[0].get('price')
        if not min_offer:
            return None
        next_offer = offers[1].get('price') if len(offers) > 1 else None
        close_offers = sum((1 for o in offers[1:] if o.get('price') and o['price'] < min_offer * 1.15))

        sample_size = 12
        avg_sales = self.trim_mean([
            e['price'] for e in s['data'].get('recentSales', [])[0:sample_size]
        ], 2, 2)
        if not avg_sales:
            return None

        return min_offer, avg_sales, close_offers, next_offer

    def get_items(self, targets: Union[Dict[str, int], int]):
        teams = load_teams()
        ratings = get_player_ratings(teams)
        ids = self.get_track_ids(ratings, targets)

        results = []
        for ratings in tqdm(ids.values()):
            for r in ratings:
                t = self.get_trend(r.template_id)
                if t is not None:
                    min_offer, avg_sales, close_offers, next_offer = t
                    rev = avg_sales - min_offer if not next_offer else min(avg_sales - min_offer,
                                                                           next_offer - min_offer)
                    results.append((r, rev, rev / min_offer, min_offer, close_offers))

        for r, rev, margin, min_offer, close_offers in sorted(results, key=itemgetter(2)):
            if margin > 0 and (30 <= min_offer):
                print(f'{self.item_url}{r.template_id} {r.rating} ' + (f'[{min_offer}] ' if min_offer <= 5 else '') +
                      f'{r.template_title} {min_offer} ({int(rev)}/{int(margin * 100)}%) {close_offers}')

    def get_market_targets(self, items_ids: Set[TemplateItem],
                           price_margin: float, score_margin: float, max_price: int) -> Dict[int, MarketTarget]:
        targets = {}
        for i in items_ids:
            s = self.get_sales(i.template_id)
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

    def buy_item(self, offer_id: int, offer_value: int) -> bool:
        r = requests.post(self.buy_url, auth=self.auth, json={'marketId': offer_id, 'price': offer_value})
        r.raise_for_status()
        return r.json()['success']

    def track_items(self, items_ids: Set[TemplateItem], price_margin: float, score_margin: float,
                    max_price: int, buy_threshold: int):
        targets = self.get_market_targets(items_ids, price_margin, score_margin, max_price)
        for t in targets.values():
            item_details = f'{t.item.template_title} for {t.offer_value} ' \
                           f'(s:{int(t.offer_score * 10)}/{t.score_margin:.3f} ' \
                           f'avg:{int(t.avg_sales)} m:{int(t.margin * 100) if t.margin else None}%)'
            if t.offer_value <= buy_threshold:
                self.buy_item(t.offer_id, t.offer_value)
                print(f'Bought {item_details}')
            else:
                url = f'{self.item_url}{t.item.template_id}'
                print(f'{url} {item_details}')

    def track(self, p: PlayerService, price_margin: float, score_margin: float,
              max_price: int, buy_threshold: int):
        for item in tqdm(list(chain.from_iterable(p.get_missing(blacklist_names={
            'purp', 'silv', 'gold', 'diam', 'lege', 'master', 'entr',
            'cs', 'onboa', 'rifl', 'shar', 'snip', 'sup'
        }, whitelist_ids={4357}).values()))):
            self.track_items({item}, price_margin, score_margin, max_price, buy_threshold)

    def schedule_track(self, p: PlayerService, l: AbstractEventLoop,
                       price_margin: float, score_margin: float,
                       max_price: int, buy_threshold: int):
        min_15 = 900
        try:
            self.track(p, price_margin, score_margin, max_price, buy_threshold)
        except Exception as e:
            print(e)
            print(f'Rescheduling due to error')
            return l.call_later(5, self.schedule_track, p, l, price_margin, score_margin, max_price, buy_threshold)

        print(f'Next in {min_15} seconds')
        return l.call_later(min_15, self.schedule_track, p, l, price_margin, score_margin, max_price, buy_threshold)

    def start(self, price_margin: float, score_margin: float, buy_threshold: int, max_price: int = 5000):
        p = PlayerService(auth=self.auth)
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(fail_fast_handler)

        loop.call_later(3500, self.auth.refresh_token)
        loop.call_soon(self.schedule_track, p, loop, price_margin, score_margin, max_price, buy_threshold)

        loop.run_forever()
        loop.close()
