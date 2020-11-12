import os

import yaml
from typing import NamedTuple, List, Dict, Union


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


class TemplateItem(NamedTuple):
    template_id: int
    template_title: str


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


CollectionItem = Union[PlayerItem, TemplateItem]


class Collection(NamedTuple):
    id: int
    name: str
    items: Dict[str, CollectionItem]
    updated_at: int = None


COLLECTIONS_PATH = os.path.join('epics', 'data', 'collections.yaml')


def get_roster_path(u_id: int) -> str:
    return os.path.join('epics', 'data', f'roster_{u_id}.json')


def load_collections(file_path: str = COLLECTIONS_PATH) -> Dict[int, Collection]:
    with open(file_path) as f:
        res = yaml.load(f, Loader=yaml.SafeLoader)
        return {col_id: Collection(id=col['id'], name=col['name'], updated_at=col.get('updated_at'), items={
            item_title: (PlayerItem(**item, template_title=item_title)
                         if 'player_id' in item
                         else TemplateItem(**item, template_title=item_title))
            for item_title, item in col.get('items', {}).items()
        }) for col_id, col in res.get('collections', {}).items()}
