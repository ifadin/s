import base64
import json
import os

import requests

from epics.utils import raise_for_status


def load_config() -> dict:
    with open(os.path.join('glm', 'data.json')) as f:
        return json.load(f)


class Runner:
    glm_url = base64.b64decode('aHR0cHM6Ly9nbGVhbS5pby9lbnRlci82dnA4dg=='.encode()).decode()

    def __init__(self) -> None:
        self.sess = os.environ['GL_SESSION']
        self.csrf = os.environ['GL_CSRF']

    def request(self, op_id: int, data: dict):
        res = requests.post(f'{self.glm_url}/{op_id}', json=data, headers={
            'x-csrf-token': self.csrf,
            'cookie': f'_app_session={self.sess}'
        })
        raise_for_status(res)
        print(res.json())


cfg = load_config()
r = Runner()
for op_id, data in cfg.items():
    r.request(op_id, data)
