import os
import pickle
import time
from configparser import ConfigParser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
import requests

_curdir = os.path.dirname(__file__)


def load_config():
    config = ConfigParser()
    config.read(f"{_curdir}/config.ini")
    return config["DEFAULT"]
    # private_key = config['DEFAULT']['PrivateKey']
    # if not isabs(private_key):
    #     private_key = f'{_curdir}/{private_key}'


def genjwt():
    cfg = load_config()

    with open(f'{_curdir}/{cfg["PrivateKey"]}') as f:
        key = f.read()
    payload = {
        "iat": int(time.time()) - 10,
        "exp": int(time.time()) + 10 * 60,
        "iss": 799664,
        "alg": "RS256",
    }
    token = jwt.encode(payload, key, "RS256")

    return token


def _installation_token():
    INSTALLATION_ID = 46258761
    r = requests.post(
        f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens",
        headers={"Authorization": f"Bearer {genjwt()}"},
        timeout=5,
    )
    r.raise_for_status()
    j = r.json()
    return j


def installation_token() -> str:
    try:
        o = pickle.load(open(f"{_curdir}/cache.pkl", "rb"))
    # Not using UnpicklingError here due to pickle.load may raise other exceptions.
    # from _pickle.UnpicklingError:
    #     Note that other exceptions may also be raised during unpickling, including
    #     (but not necessarily limited to) AttributeError, EOFError, ImportError,
    #     and IndexError.
    except Exception:
        o = None

    if o:
        exp = datetime.fromisoformat(o["expires_at"])
        if (
            datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
            + timedelta(minutes=30)
            > exp
        ):
            o = None

    if o:
        print("Using cached token...")
    else:
        print("Requesting api.github.com for installation token...")
        o = _installation_token()
        pickle.dump(o, open(f"{_curdir}/cache.pkl", "wb"))

    return o["token"]


def test():
    token = genjwt()
    r = requests.get(
        "https://api.github.com/app",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    r.raise_for_status()
    print(f"TOKEN valid: {token}")
    print(r.text)
    print(f"Installation token: {installation_token()}")
    # r = requests.get('https://api.github.com/app/installations', headers={
    #    'Authorization': f'Bearer {token}'
    # })
    # print(r.text)
    # print(f'git clone https://x-access-token:{token}@github.com/deepin-community/bash.git')


def main():
    test()


if __name__ == "__main__":
    main()
