import base64
import os

import requests
from requests import Request
from requests.auth import AuthBase


class EAuth(AuthBase):
    ref_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2F1dGgvcmVmcmVzaC1qd3Q='.encode()).decode()

    def __init__(self) -> None:
        self.token = None
        self.r_token = os.environ['EP_REF_TOKEN']

    def __call__(self, r: Request):
        r.headers['x-user-jwt'] = self.get_token()
        return r

    def get_token(self):
        if not self.token:
            self.refresh_token()
        return self.token

    def refresh_token(self):
        r = requests.post(self.ref_url, json={'device': 'web', 'refreshToken': self.r_token})
        r.raise_for_status()
        self.token = r.json()['data']['jwt']
