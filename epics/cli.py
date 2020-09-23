import sys

from epics.game import Fighter
from epics.spin import SpinService
from epics.track import Tracker

options = {'spin', 'track', 'fight', 'items'}

if len(sys.argv) < 2 or sys.argv[1] not in options:
    raise AssertionError(f'Specify one of {options}')

if sys.argv[1] == 'spin':
    SpinService().start()
if sys.argv[1] == 'items':
    if len(sys.argv) < 3:
        raise AssertionError('Missing item value argument')
    Tracker().get_items(int(sys.argv[2]))
if sys.argv[1] == 'track':
    Tracker().start()
if sys.argv[1] == 'fight':
    if len(sys.argv) < 3:
        raise AssertionError('Missing mode argument')
    Fighter().start(mode=int(sys.argv[2]))
