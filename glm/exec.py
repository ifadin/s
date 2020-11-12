import json
import os

import requests

from epics.utils import raise_for_status


def load_config() -> dict:
    with open(os.path.join('glm', 'data.json')) as f:
        return json.load(f)


class Runner:

    def __init__(self) -> None:
        self.sess = os.environ['GL_SESSION']
        self.csrf = os.environ['GL_CSRF']

    def request(self, op_id: int,  data: dict):
        res = requests.post(f'https://gleam.io/enter/6vp8v/{op_id}', json=data, headers={
            'x-csrf-token': self.csrf,
            'cookie': f'_app_session={self.sess}'
        })
        raise_for_status(res)
        print(res.json())


cfg = load_config()
r = Runner()
for op_id, data in cfg.items():
    r.request(op_id, data)
