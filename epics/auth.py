import base64

from requests import Request
from requests.auth import AuthBase

from epics.utils import get_http_session, with_retry


class EAuth(AuthBase):
    ref_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2F1dGgvcmVmcmVzaC1qd3Q='.encode()).decode()

    def __init__(self, r_token: str) -> None:
        self.token = None
        self.r_token = r_token
        self.session = get_http_session()

    def __call__(self, r: Request):
        r.headers['x-user-jwt'] = self.get_token()
        return r

    def get_token(self):
        if not self.token:
            self.refresh_token()
        return self.token

    def refresh_token(self):
        r = with_retry(self.session.post(self.ref_url, json={'device': 'web', 'refreshToken': self.r_token}),
                       self.session)
        r.raise_for_status()
        self.token = r.json()['data']['jwt']
