import base64
import json
import os

import requests
from tqdm import tqdm
from typing import Set, Dict, List

from epics.auth import EAuth
from epics.domain import load_collections, TemplateItem, PlayerItem, ROSTER_PATH


class PlayerService:
    card_ids_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NvbGxlY3Rpb25zL3VzZXJzLzQwNTQzNi9jYXJkaWRz'
                                    'P2NhdGVnb3J5SWQ9MSZjb2xsZWN0aW9uSWQ9'.encode()).decode()

    def __init__(self, auth: EAuth = EAuth(os.environ['EP_REF_TOKEN'])) -> None:
        self.auth = auth

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

    @classmethod
    def get_owned(cls) -> Dict[int, PlayerItem]:
        roster = cls.load_roster()
        return {
            i.template_id: i for col in list(load_collections().values())
            for i in list(col.items.values())
            if isinstance(i, PlayerItem) and i.template_id in roster
        }

    @staticmethod
    def load_roster() -> List[int]:
        with open(ROSTER_PATH) as f:
            return json.load(f)
