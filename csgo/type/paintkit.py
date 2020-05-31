from typing import NamedTuple


class PaintKit(NamedTuple):
    id: int
    tag: str
    min_float: float
    max_float: float
    name: str = None
    key: str = None
    desc: str = None
    flavor: str = None
