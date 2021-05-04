import asyncio
import sys
from argparse import Namespace, ArgumentParser
from asyncio import gather

from tqdm import tqdm
from typing import List

from epics.craft import Crafter
from epics.domain import load_collections, get_collections_path, get_collections
from epics.game import Trainer
from epics.pack import PackService
from epics.player import PlayerService
from epics.price import PriceService
from epics.spin import SpinService
from epics.track import Tracker
from epics.trader import Trader
from epics.update import Updater
from epics.upgrade import save_inventory, InventoryItem, load_inventory
from epics.user import u_a, u_a_auth, u_b, u_b_auth
from epics.utils import fail_fast_handler


def get_args() -> Namespace:
    parser = ArgumentParser()
    subparser = parser.add_subparsers(dest='command')

    pack_open = subparser.add_parser('open')
    spin = subparser.add_parser('spin')
    track = subparser.add_parser('track')
    goal = subparser.add_parser('goal')
    update = subparser.add_parser('update')
    upgrade = subparser.add_parser('upgrade')
    inv = subparser.add_parser('inv')
    trade = subparser.add_parser('trade')

    pack_open.add_argument('amount', type=int)
    pack_open.add_argument('-p', '--pattern', type=str)
    pack_open.add_argument('--client', type=str, nargs='+', choices={'a', 'b'}, default=['a', 'b'])
    pack_open.add_argument('-y', '--year', type=str, nargs='+', default=['2021'])
    pack_open.add_argument('--trade', action='store_true')

    goal.add_argument('--client', type=str, nargs='+', choices={'a', 'b'}, default=['a', 'b'])

    track.add_argument('-y', '--year', type=str, nargs='+', default=['2021'])
    track.add_argument('-c', '--col', type=int, nargs='*')
    track.add_argument('--item-client', type=str, choices={'a', 'b'}, default='a')
    track.add_argument('--price-client', type=str, choices={'a', 'b'}, default='a')
    track.add_argument('-m', '--margin', type=float, default=0.9)
    track.add_argument('--pps', type=float, default=0.1)
    track.add_argument('-b', '--buy-threshold', type=int, default=10)
    track.add_argument('-i', '--interval', type=int, default=900)

    update.add_argument('-y', '--year', type=str, nargs='+', default=['2021'])
    update.add_argument('--cache', type=int, default=86400)

    upgrade.add_argument('-y', '--year', type=str, nargs='+', default=['2021'])
    upgrade.add_argument('-c', '--col', type=int, nargs='*')
    upgrade.add_argument('--pps', type=float, default=0.1)
    upgrade.add_argument('-b', '--buy-threshold', type=int, default=10)
    upgrade.add_argument('-l', '--level', type=str, nargs='*', choices={'a', 'r', 'v', 's', 'u', 'l'})

    inv.add_argument('-y', '--year', type=str, nargs='+', default=['2021'])
    inv.add_argument('-c', '--col', type=int, nargs='*')
    inv.add_argument('-l', '--level', type=str, nargs='*', choices={'a', 'r', 'v', 's', 'u', 'l'})
    inv.add_argument('--merge', action='store_true')

    trade.add_argument('-c', '--col', type=int, nargs='*')
    trade.add_argument('-y', '--year', type=str, nargs='+', default=['2021'])
    trade.add_argument('-l', '--offer-limit', type=int, default=5)

    return parser.parse_known_args()[0]


args = get_args()

l = asyncio.get_event_loop()
l.set_exception_handler(fail_fast_handler)

if args.command == 'spin':
    SpinService(u_a, u_a_auth).start(l)
    SpinService(u_b, u_b_auth).start(l)
    l.run_forever()

if args.command == 'items':
    if len(sys.argv) < 3:
        raise AssertionError('Missing item value argument')
    Tracker(u_a, u_a_auth).get_items(int(sys.argv[2]))
    l.run_forever()

if args.command == 'track':
    c = get_collections(args.year, args.col)
    u_id = u_b if args.item_client.lower() == 'b' else u_a
    u_auth = u_b_auth if args.item_client.lower() == 'b' else u_a_auth
    u_p_auth = u_b_auth if args.price_client.lower() == 'b' else u_a_auth
    price_service = PriceService(u_p_auth)
    t: Tracker = Tracker(u_id, u_auth, c,
                         price_service,
                         Trader(u_id, u_auth,
                                price_service,
                                PlayerService(u_a, u_a_auth),
                                PackService(None, None, u_a_auth)))
    t.start(l, args.margin, args.pps, args.buy_threshold, interval=args.interval)
    l.run_forever()

if args.command == 'goal':
    futures = []
    c = load_collections()
    a = Trainer(u_a, u_a_auth, Trader(u_a, u_a_auth,
                                      PriceService(u_a_auth),
                                      PlayerService(u_a, u_a_auth, c),
                                      PackService(c, None, u_a_auth),
                                      PlayerService(u_b, u_b_auth, c)))

    b = Trainer(u_b, u_b_auth, Trader(u_b, u_b_auth,
                                      PriceService(u_b_auth),
                                      PlayerService(u_b, u_b_auth, c),
                                      PackService(c, None, u_b_auth)))
    if 'a' in args.client:
        futures.append(a.run(b))
    if 'b' in args.client:
        futures.append(b.run(a))

    l.run_until_complete(gather(*futures))

    for tr in [b, a]:
        tr.complete_pack_goal()

if args.command == 'open':
    c = load_collections()
    traders: List[Trader] = []
    if 'b' in args.client:
        trader_b = Trader(u_b, u_b_auth,
                          PriceService(u_b_auth),
                          PlayerService(u_b, u_b_auth, c),
                          PackService(c, None, u_b_auth))
        items = trader_b.open_and_manage(args.amount, args.year, args.pattern.lower() if args.pattern else None,
                                         trade=args.trade)
    if 'a' in args.client:
        trader_a = Trader(u_a, u_a_auth,
                          PriceService(u_a_auth),
                          PlayerService(u_a, u_a_auth, c),
                          PackService(c, None, u_a_auth),
                          PlayerService(u_b, u_b_auth, c))
        trader_a.open_and_manage(args.amount, args.year, args.pattern.lower() if args.pattern else None,
                                 trade=args.trade, extra=items)

if args.command == 'trade':
    c = get_collections(args.year, args.col)
    tr = Trader(u_a, u_a_auth,
                PriceService(u_a_auth),
                PlayerService(u_a, u_a_auth, c),
                PackService(None, None, u_a_auth),
                PlayerService(u_b, u_b_auth, c))
    tr.trade(offer_limit=args.offer_limit)

if args.command == 'craft':
    item_types = {'d', 'g', 's', 'p', 't1'}
    t = sys.argv[2] if len(sys.argv) > 2 else None
    a = int(sys.argv[3]) if len(sys.argv) > 3 else None
    c_a, c_b = Crafter(u_a, u_a_auth), Crafter(u_b, u_b_auth)

    if t:
        c_a.craft(t, a)
        c_b.craft(t, a)
    else:
        c_a.craft('g')
        c_b.craft('g')
        c_a.craft('d')
        c_b.craft('d')
        c_a.craft('t1')
        c_b.craft('t1')

if args.command == 'update':
    for y in args.year:
        Updater(u_a, u_a_auth, y).update_collections(args.cache)

if args.command == 'upgrade':
    c = get_collections(args.year, args.col)
    p = PriceService(u_a_auth)
    Tracker(u_a, u_a_auth, c, p, Trader(u_a, u_a_auth, p,
                                        PlayerService(u_a, u_a_auth),
                                        PackService(None, None, u_a_auth))).upgrade(args.pps, args.buy_threshold,
                                                                                    args.level)

if args.command == 'sell':
    if len(sys.argv) < 3:
        raise AssertionError('Missing pps argument')

    pps_margin = float(sys.argv[2])
    Tracker(u_a, u_a_auth, load_collections(get_collections_path('2020'))).sell(pps_margin)

if args.command == 'inv':
    c = get_collections(args.year, args.col)
    p = PlayerService(u_a, u_a_auth, c)
    inv = load_inventory() if args.merge else {}

    items = p.get_owned()
    cards = p.get_top_inventory(items, args.level)
    for index, c in enumerate(tqdm(cards, desc='Items', total=len(items))):
        item = InventoryItem(c.template_id, c.entity_type, c.key, c.score)
        inv[item.key] = item
        if index % (len(items) // 10) == 0:
            save_inventory(inv.values())
    save_inventory(inv.values())

l.close()
