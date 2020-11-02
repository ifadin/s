import sys

from epics.craft import Crafter
from epics.game import Fighter
from epics.spin import SpinService
from epics.track import Tracker

options = {'spin', 'track', 'fight', 'items', 'craft'}

if len(sys.argv) < 2 or sys.argv[1] not in options:
    raise AssertionError(f'Specify one of {options}')

if sys.argv[1] == 'spin':
    SpinService().start()

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
    if len(sys.argv) < 3:
        raise AssertionError('Missing mode argument')
    Fighter().start(mode=int(sys.argv[2]))

if sys.argv[1] == 'craft':
    if len(sys.argv) < 3:
        raise AssertionError('Missing item type argument')
    item_types = {'d', 'g', 's', 'p'}
    t = sys.argv[2]
    if t not in item_types:
        raise AssertionError(f'Supported item types are {item_types}')
    a = int(sys.argv[3]) if len(sys.argv) > 3 else None
    Crafter().craft(t, a)
