import asyncio
import base64
import os
import sys

from epics.auth import EAuth
from epics.craft import Crafter
from epics.game import Fighter
from epics.spin import SpinService
from epics.track import Tracker
from epics.utils import fail_fast_handler

options = {'spin', 'track', 'fight', 'items', 'craft'}

if len(sys.argv) < 2 or sys.argv[1] not in options:
    raise AssertionError(f'Specify one of {options}')

u_a = base64.b64decode('NDA1NDM2'.encode()).decode()
u_a_auth = EAuth(os.environ['EP_REF_TOKEN'])
u_b = base64.b64decode('NDIwNzYx'.encode()).decode()
u_b_auth = EAuth(os.environ['EP_REF_TOKEN_B'])

l = asyncio.get_event_loop()
l.set_exception_handler(fail_fast_handler)

if sys.argv[1] == 'spin':
    SpinService(u_a, u_a_auth).start(l)
    SpinService(u_b, u_b_auth).start(l)

if sys.argv[1] == 'items':
    if len(sys.argv) < 3:
        raise AssertionError('Missing item value argument')
    Tracker().get_items(int(sys.argv[2]))

if sys.argv[1] == 'track':
    if len(sys.argv) < 4:
        raise AssertionError('Missing margin values argument')

    price_margin, score_margin = float(sys.argv[2]), float(sys.argv[3])
    buy_threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 60
    Tracker().start(price_margin, score_margin, buy_threshold)

if sys.argv[1] == 'fight':
    Fighter(u_a, u_a_auth).start(l)
    Fighter(u_b, u_b_auth).start(l)

if sys.argv[1] == 'craft':
    if len(sys.argv) < 3:
        raise AssertionError('Missing item type argument')
    item_types = {'d', 'g', 's', 'p'}
    t = sys.argv[2]
    if t not in item_types:
        raise AssertionError(f'Supported item types are {item_types}')
    a = int(sys.argv[3]) if len(sys.argv) > 3 else None
    Crafter().craft(t, a)

l.run_forever()
l.close()
