import asyncio
import sys
from argparse import Namespace, ArgumentParser
from asyncio import gather

from epics.craft import Crafter
from epics.domain import load_collections, get_collections_path, get_collections
from epics.game import Trainer
from epics.player import PlayerService
from epics.spin import SpinService
from epics.track import Tracker
from epics.update import Updater
from epics.upgrade import save_inventory, InventoryItem, load_inventory
from epics.user import u_a, u_a_auth, u_b, u_b_auth
from epics.utils import fail_fast_handler


def get_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument('command', metavar='COMMAND', type=str,
                        choices={'spin', 'track', 'goal', 'items', 'craft', 'update', 'upgrade', 'sell', 'inv'})
    parser.add_argument('-y', '--year', type=int, nargs='+', default=[2020])
    parser.add_argument('-c', '--col', type=int, nargs='*')
    parser.add_argument('--cache', type=int, default=86400)
    parser.add_argument('-m', '--margin', type=float, default=0.9)
    parser.add_argument('--pps', type=float, default=0.1)
    parser.add_argument('-b', '--buy-threshold', type=int, default=10)
    parser.add_argument('--client', type=str, choices={'a', 'b'}, default='a')
    parser.add_argument('-l', '--level', type=str, nargs='*', choices={'a', 'r', 'v', 's', 'u', 'l'})
    parser.add_argument('--merge', action='store_true')

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
    t: Tracker = (Tracker(u_a, u_a_auth, c) if not args.client.lower() == 'b' else Tracker(u_b, u_b_auth, c))
    t.start(l, args.margin, args.pps, args.buy_threshold)
    l.run_forever()

if args.command == 'goal':
    a = Trainer(u_a, u_a_auth)
    b = Trainer(u_b, u_b_auth)
    l.run_until_complete(gather(a.run(b), b.run(a)))

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
    Tracker(u_a, u_a_auth, c).upgrade(args.pps, args.buy_threshold, args.level)

if args.command == 'sell':
    if len(sys.argv) < 3:
        raise AssertionError('Missing pps argument')

    pps_margin = float(sys.argv[2])
    Tracker(u_a, u_a_auth, load_collections(get_collections_path('2020'))).sell(pps_margin)

if args.command == 'inv':
    c = get_collections(args.year, args.col)
    cards = PlayerService(u_a, u_a_auth, c).get_top_inventory(args.level)

    inv = load_inventory() if args.merge else {}
    for c in cards.values():
        item = InventoryItem(c.template_id, c.entity_type, c.key, c.score)
        inv[item.key] = item
    save_inventory(inv.values())

l.close()
