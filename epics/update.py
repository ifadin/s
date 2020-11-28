import base64
import json
import os
from copy import deepcopy
from itertools import chain
from time import time

import requests
import yaml
from tqdm import tqdm
from typing import Dict, Set

from csgo.util import get_batches
from epics.auth import EAuth
from epics.domain import Rating, Player, Team, TEAMS_PATH, PlayerItem, Collection, COLLECTIONS_PATH, load_collections, \
    TemplateItem, get_roster_path
from epics.pack import load_packs, PackService, save_packs, Pack
from epics.player import PlayerService
from epics.user import u_a, u_a_auth, u_b_auth, u_b


class Updater:
    collections_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NvbGxlY3Rpb25zLw=='.encode()).decode()

    def __init__(self, u_id: int, auth: EAuth = EAuth(os.environ['EP_REF_TOKEN'])) -> None:
        self.u_id = u_id
        self.auth = auth
        self.p_service = PlayerService(self.u_id, self.auth)

        self.summary_url = (
                base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NvbGxlY3Rpb25zL3VzZXJz'.encode()).decode()
                + f'/{self.u_id}/user-summary/?categoryId=1'
        )

    def request_collection_ids(self) -> Dict[int, str]:
        r = requests.get(self.summary_url, auth=self.auth)
        r.raise_for_status()
        return {c['collection']['id']: c['collection']['name'] for c in r.json()['data']
                if c['collection']['visible']
                and '2020' in c['collection']['properties']['seasons']
                and 1 in c['collection']['properties']['game_ids']
                and any(e in c['collection']['properties']['entity_types'] for e in ['card', 'sticker'])}

    @classmethod
    def get_collection_url(cls, collection_id: int, entity_type: str) -> str:
        return f'{cls.collections_url}{collection_id}/{entity_type}-templates?categoryId=1'

    def get_collection(self, collection_id: int, collection_name: str) -> Collection:
        col = self.request_collection(collection_id, 'card')
        st = self.request_collection(collection_id, 'sticker')
        items = {
            c['title']: (PlayerItem(template_id=c['id'], template_title=c['title'],
                                    ovr_rating=c['properties']['player_rating'],
                                    player_rating=c['playerStatsV2']['rating']['score'],
                                    player_id=c['player']['id'], handle=c['player']['handle'],
                                    country=c['player']['country'],
                                    role_id=c['player']['playerRoleId'], position=c['player']['position'],
                                    team_name=c['team']['shortName'], salary=c['properties']['salary'],
                                    rarity=c['rarity'], group_id=c['treatmentId'], entity_type='card')
                         if c['properties'].get('player_rating')
                         else TemplateItem(template_id=c['id'], template_title=c['title'],
                                           group_id=c['treatmentId'] if c.get('treatmentId') else c['id'],
                                           rarity=c['rarity'],
                                           entity_type='card' if c.get('treatmentId') else 'sticker'))
            for c in chain(col['data'], st['data'])
        }

        return Collection(id=collection_id, name=collection_name, items=items)

    def request_collection(self, collection_id: int, entity_type: str) -> dict:
        url = self.get_collection_url(collection_id, entity_type)
        r = requests.get(url, auth=self.auth)
        r.raise_for_status()
        return r.json()

    def update_collections(self, cache_threshold_seconds: int = 86400):
        collections = load_collections(COLLECTIONS_PATH)
        collection_ids = list(self.request_collection_ids().items())
        batch_size = 10
        print(f'{len(collection_ids)} collections to update (batch size {batch_size})')
        for col_batch in tqdm(get_batches(collection_ids, batch_size)):
            save_required = False
            for col_id, col_name in col_batch:
                if (col_name not in collections or not collections[col_name].updated_at or
                        (int(time()) - collections[col_name].updated_at > cache_threshold_seconds)):
                    c = self.get_collection(col_id, col_name)
                    collections[col_id] = c
                    save_required = True
            if save_required:
                save_collections(collections, COLLECTIONS_PATH)

    def update_roster(self):
        players = {i for col in tqdm(load_collections()) for i in self.p_service.get_card_ids(col)}
        return save_roster(players, get_roster_path(self.u_id))

    @classmethod
    def update_teams(cls):
        collections = load_collections(COLLECTIONS_PATH)
        teams = {}
        for col in list(collections.values()):
            for player_item in list(i for i in list(col.items.values()) if isinstance(i, PlayerItem)):
                team_name = player_item.team_name
                if team_name not in teams:
                    teams[team_name] = Team(name=team_name, players={})
                p = Player(id=player_item.player_id, name=player_item.handle, country=player_item.country,
                           position=player_item.position, role_id=player_item.role_id,
                           team_name=team_name, ratings=[])
                if p.name not in teams[team_name].players:
                    teams[team_name].players[p.name] = p
                else:
                    cls.check_mismatches(teams[team_name].players[p.name], p)

                r = Rating(rating=player_item.player_rating,
                           rarity=player_item.rarity,
                           salary=player_item.salary,
                           template_id=player_item.template_id,
                           template_title=player_item.template_title)
                teams[team_name].players[p.name].ratings.append(r)
        save_teams(teams, TEAMS_PATH)

    def update_packs(self, cache_invalidation_seconds: int = 86400, ignored: Set[int] = {2641, 2642, 2643, 2674}):
        collections = load_collections(COLLECTIONS_PATH)
        packs = load_packs()
        p_service = PackService(collections, packs, self.auth)
        r_packs = p_service.get_packs()

        for i, pack in tqdm(list(enumerate(p for p in r_packs if p.id not in ignored))):
            exp = pack.exp if pack.id not in packs else packs[pack.id].exp
            if pack.id not in packs or (not packs[pack.id].updated_at
                                        or (int(time()) - packs[pack.id].updated_at > cache_invalidation_seconds)):
                exp = p_service.get_exp(pack)

            packs[pack.id] = Pack(pack.id, pack.name, pack.chances, pack.count, exp, int(time()))
            if i % 5 == 0:
                save_packs(packs)

        save_packs(packs)

    @staticmethod
    def check_mismatches(player_l: Player, player_r: Player):
        player_l = deepcopy(player_l)
        player_r = deepcopy(player_r)
        if player_l.id != player_r.id or player_l.country != player_r.country \
                or player_l.position != player_r.position or player_l.role_id != player_r.role_id:
            player_l_dict = player_l._asdict()
            player_r_dict = player_r._asdict()
            player_l_dict.pop('ratings')
            player_r_dict.pop('ratings')
            print(f'WARN: mismatch between {player_l_dict} and {player_r_dict}')


def save_collections(collections: Dict[int, Collection], file_path: str):
    with open(file_path, 'w') as f:
        data = {'collections': {}}
        for col_id, col in collections.items():
            items = {}
            for i in col.items.values():
                i_obj = dict(i._asdict())
                i_obj.pop('template_title')
                items[i.template_title] = i_obj
            data['collections'][col_id] = {
                'name': col.name,
                'updated_at': int(time()),
                'items': items
            }
        yaml.dump(data, f, default_flow_style=False)


def save_roster(players: Set[int], file_path: str):
    with open(file_path, 'w') as f:
        json.dump(list(players), f)


def save_teams(teams: Dict[str, Team], file_path: str):
    with open(file_path, 'w') as f:
        data = {'teams': {}}
        for team_name, team in teams.items():
            players = {}
            for p in team.players.values():
                p_obj = dict(p._asdict())
                p_obj.pop('name')
                p_obj.pop('team_name')
                p_obj['ratings'] = {}
                for r in p.ratings:
                    r_obj = dict(r._asdict())
                    r_obj.pop('template_title')
                    p_obj['ratings'][r.template_title] = r_obj
                players[p.name] = p_obj
            data['teams'][team_name] = {'players': players}

        yaml.dump(data, f, default_flow_style=False)


updater_a = Updater(u_a, u_a_auth)
updater_b = Updater(u_b, u_b_auth)
