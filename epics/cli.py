import asyncio
import sys
from asyncio import gather

from epics.craft import Crafter
from epics.domain import load_collections, get_collections_path
from epics.game import Trainer
from epics.player import PlayerService
from epics.spin import SpinService
from epics.track import Tracker
from epics.update import Updater
from epics.upgrade import save_inventory, InventoryItem
from epics.user import u_a, u_a_auth, u_b, u_b_auth
from epics.utils import fail_fast_handler

options = {'spin', 'track', 'goal', 'items', 'craft', 'update', 'upgrade', 'sell', 'inv'}

if len(sys.argv) < 2 or sys.argv[1] not in options:
    raise AssertionError(f'Specify one of {options}')

l = asyncio.get_event_loop()
l.set_exception_handler(fail_fast_handler)

if sys.argv[1] == 'spin':
    SpinService(u_a, u_a_auth).start(l)
    SpinService(u_b, u_b_auth).start(l)
    l.run_forever()

if sys.argv[1] == 'items':
    if len(sys.argv) < 3:
        raise AssertionError('Missing item value argument')
    Tracker(u_a, u_a_auth).get_items(int(sys.argv[2]))
    l.run_forever()

if sys.argv[1] == 'track':
    if len(sys.argv) < 4:
        raise AssertionError('Missing margin values argument')

    price_margin, score_margin = float(sys.argv[2]), float(sys.argv[3])
    buy_threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 60
    s_id = sys.argv[5] if len(sys.argv) > 5 else '2020'
    b_track = sys.argv[6] if len(sys.argv) > 6 else ''
    t: Tracker = (Tracker(u_a, u_a_auth, load_collections(get_collections_path(s_id)))
                  if not b_track.lower() == 'b'
                  else Tracker(u_b, u_b_auth, load_collections(get_collections_path(s_id))))
    t.start(l, price_margin, score_margin,
            buy_threshold)
    l.run_forever()

if sys.argv[1] == 'goal':
    a = Trainer(u_a, u_a_auth)
    b = Trainer(u_b, u_b_auth)
    l.run_until_complete(gather(a.run(b), b.run(a)))

if sys.argv[1] == 'craft':
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

if sys.argv[1] == 'update':
    if len(sys.argv) < 3:
        raise AssertionError('Missing s_id argument')
    if len(sys.argv) < 4:
        raise AssertionError('Missing cache_refresh argument')

    Updater(u_a, u_a_auth, sys.argv[2]).update_collections(int(sys.argv[3]))

if sys.argv[1] == 'upgrade':
    s_id = sys.argv[2] if len(sys.argv) > 2 else '2020'
    pps = float(sys.argv[3]) if len(sys.argv) > 3 else 0.45
    buy_threshold = int(sys.argv[4]) if len(sys.argv) > 4 else 20
    Tracker(u_a, u_a_auth, load_collections(get_collections_path(s_id))).upgrade(pps, buy_threshold)

if sys.argv[1] == 'sell':
    if len(sys.argv) < 3:
        raise AssertionError('Missing pps argument')

    pps_margin = float(sys.argv[2])
    Tracker(u_a, u_a_auth, load_collections(get_collections_path('2020'))).sell(pps_margin)

if sys.argv[1] == 'inv':
    s_id = sys.argv[2] if len(sys.argv) > 2 else '2020'
    cards = PlayerService(u_a, u_a_auth, load_collections(get_collections_path(s_id))).get_top_inventory(
        {'abun', 'rare', 'very'})
    save_inventory({InventoryItem(c.template_id, c.entity_type, c.key, c.score) for c in cards.values()})

l.close()
