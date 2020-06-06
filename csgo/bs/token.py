import os

import pyotp


class TokenProvider:

    def __init__(self) -> None:
        self.totp = pyotp.TOTP(os.environ['BS_CODE'])

    def get_token(self) -> str:
        return self.totp.now()

    @staticmethod
    def get_api_key() -> str:
        return os.environ['BS_KEY']
