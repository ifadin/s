import base64
import json
import os

import requests
from tqdm import tqdm
from typing import Set, Dict, List

from epics.auth import EAuth
from epics.domain import load_collections, TemplateItem, PlayerItem, get_roster_path


class PlayerService:

    def __init__(self, u_id: int, auth: EAuth) -> None:
        self.u_id = u_id
        self.auth = auth

        self.card_ids_url = (
                base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NvbGxlY3Rpb25zL3VzZXJz'.encode()).decode()
                + f'/{self.u_id}/cardids?categoryId=1&collectionId='
        )

    def get_card_ids(self, collection_id: int) -> Dict[int, Set[int]]:
        r = requests.get(f'{self.card_ids_url}{collection_id}', auth=self.auth)
        r.raise_for_status()
        return {d['cardTemplateId']: set(d['cardIds']) for d in r.json()['data']}

    def get_missing(self, blacklist_names: Set[str] = None, whitelist_ids=None) -> Dict[int, Set[TemplateItem]]:
        if whitelist_ids is None:
            whitelist_ids = {}
        if blacklist_names is None:
            blacklist_names = set()

        missing: Dict[int, Set[TemplateItem]] = {}
        for c in tqdm(load_collections().values()):
            if c.id in whitelist_ids or all((not c.name.lower().startswith(ignored) for ignored in blacklist_names)):
                owned = self.get_card_ids(c.id).keys()
                for i in c.items.values():
                    if i.template_id not in owned:
                        missing[c.id] = missing.get(c.id, set()) | {TemplateItem(i.template_id, i.template_title)}

        return missing

    def get_owned(self) -> Dict[int, PlayerItem]:
        roster = self.load_roster()
        return {
            i.template_id: i for col in list(load_collections().values())
            for i in list(col.items.values())
            if isinstance(i, PlayerItem) and i.template_id in roster
        }

    def load_roster(self) -> List[int]:
        with open(get_roster_path(self.u_id)) as f:
            return json.load(f)
