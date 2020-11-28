import asyncio
import sys
from asyncio import gather

from epics.craft import Crafter
from epics.game import Trainer
from epics.spin import SpinService
from epics.track import Tracker
from epics.user import u_a, u_a_auth, u_b, u_b_auth
from epics.utils import fail_fast_handler

options = {'spin', 'track', 'goal', 'items', 'craft', 'upgrade'}

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
    Tracker(u_a, u_a_auth).start(l, price_margin, score_margin, buy_threshold)
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

if sys.argv[1] == 'upgrade':
    Tracker(u_a, u_a_auth).upgrade()

l.close()
