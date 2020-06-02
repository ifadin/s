from typing import NamedTuple


class IDBCollection(NamedTuple):
    id: int
    name: str
    tag: str
    case: bool = None
    released: str = None
    souvenir: bool = None
    stattrak: bool = None


class IDBPaintKit(NamedTuple):
    id: int
    tag: str
    min_float: float
    max_float: float
    desc: str = None
    flavor: str = None
    key: str = None
    name: str = None


class IDBRarity(NamedTuple):
    id: int
    name: str
    tag: str
    color: str = None


class IDBSkin(NamedTuple):
    id: int
    weapon_id: int
    rarity_id: int
    collection_id: int
    paintkit_id: int
    image: dict = None


class IDBWeapon(NamedTuple):
    id: int
    name: str
    tag: str
    type: str = None
    desc: str = None
