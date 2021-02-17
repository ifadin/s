import os
from itertools import chain

import yaml
from enum import Enum
from typing import NamedTuple, List, Dict, Union, Set


class Rating(NamedTuple):
    rating: int
    rarity: str
    salary: int
    template_id: int
    template_title: str


class Player(NamedTuple):
    id: int
    name: str
    country: str
    position: str
    role_id: int
    team_name: str
    ratings: List[Rating]


class Team(NamedTuple):
    name: str
    players: Dict[str, Player]


def get_player_ratings(teams: Dict[str, Team]) -> Dict[str, List[Rating]]:
    return {p.name: p.ratings for t in list(teams.values()) for p in list(t.players.values())}


TEAMS_PATH = os.path.join('epics', 'data', 'teams.yaml')


def load_teams(file_path: str = TEAMS_PATH) -> Dict[str, Team]:
    with open(file_path) as f:
        res = yaml.load(f, Loader=yaml.SafeLoader)
        return {t_name: Team(name=t_name, players={
            p_name: Player(id=p['id'], name=p_name, country=p['country'], position=p['position'],
                           role_id=p['role_id'], team_name=t_name,
                           ratings=[Rating(rating=r['rating'], salary=r['salary'], template_title=r_title,
                                           template_id=r['template_id'], rarity=r['rarity'])
                                    for r_title, r in p['ratings'].items()]
                           ) for p_name, p in t['players'].items()
        }) for t_name, t in res['teams'].items()}


class Rarity(Enum):
    A = 1
    R = 2
    V = 3
    S = 4
    U = 5
    L = 6


class TemplateItem(NamedTuple):
    template_id: int
    template_title: str
    group_id: int
    entity_type: str
    rarity: str = None

    @property
    def key(self) -> str:
        return f'{self.entity_type}-{self.template_id}'

    @property
    def group_key(self) -> str:
        return f'{self.entity_type}-{self.group_id}'


class PlayerItem(NamedTuple):
    country: str
    handle: str
    player_id: int
    player_rating: int
    ovr_rating: int
    position: str
    rarity: str
    role_id: int
    salary: int
    team_name: str
    template_id: int
    template_title: str
    group_id: int
    entity_type: str

    @property
    def key(self) -> str:
        return f'{self.entity_type}-{self.template_id}'

    @property
    def group_key(self) -> str:
        return f'{self.entity_type}-{self.group_id}'


CollectionItem = Union[PlayerItem, TemplateItem]


class Collection(NamedTuple):
    id: int
    name: str
    items: Dict[str, CollectionItem]
    updated_at: int = None


def get_collections_path(s_id: str) -> str:
    return os.path.join('epics', 'data', f'{s_id}_collections.yaml')


def get_roster_path(u_id: int) -> str:
    return os.path.join('epics', 'data', f'roster_{u_id}.json')


def load_collections(file_path: str = get_collections_path('2020')) -> Dict[int, Collection]:
    with open(file_path) as f:
        res = yaml.load(f, Loader=yaml.SafeLoader)
        if not res:
            return {}

        return {col_id: Collection(id=col_id, name=col['name'], updated_at=col.get('updated_at'),
                                   items={
                                       item_id: (PlayerItem(template_id=item_id, **item)
                                                 if 'player_id' in item
                                                 else TemplateItem(template_id=item_id, **item))
                                       for item_id, item in col.get('items', {}).items()})
                for col_id, col in res.get('collections', {}).items()}


def get_collections(s_ids: Set[int], col_ids: Set[int] = None) -> Dict[int, Collection]:
    return {
        k: v for k, v
        in chain(*[load_collections(get_collections_path(str(s))).items() for s in s_ids])
        if not col_ids or k in col_ids
    }
