#!/usr/bin/env python3

import asyncio
import atexit
import getpass
import json
import os
import sys

import aiofiles
from nio import AsyncClient, LoginResponse

from .bot import DCBot

CONFIG_FILE = "credentials.json"


# Check out main() below to see how it's done.


def write_details_to_disk(resp: LoginResponse, homeserver) -> None:
    """Writes the required login details to disk so we can log in later without
    using a password.

    Arguments:
        resp {LoginResponse} -- the successful client login response.
        homeserver -- URL of homeserver, e.g. "https://matrix.org"
    """
    # open the config file in write-mode
    with open(CONFIG_FILE, "w") as f:
        # write the login details to disk
        json.dump(
            {
                "homeserver": homeserver,  # e.g. "https://matrix.org"
                "user_id": resp.user_id,  # e.g. "@user:example.org"
                "device_id": resp.device_id,  # device ID, 10 uppercase letters
                "access_token": resp.access_token,  # cryptogr. access token
            },
            f,
        )


async def login():
    print(
        "First time use. Did not find credential file. Asking for "
        "homeserver, user, and password to create credential file."
    )
    homeserver = "https://matrix.org"
    _homeserver = input(f"Enter your homeserver URL: [{homeserver}] ").strip()

    if _homeserver:
        homeserver = _homeserver

    if not (homeserver.startswith("https://") or homeserver.startswith("http://")):
        homeserver = "https://" + homeserver

    user_id = "@dcbot:matrix.org"
    _user_id = input(f"Enter your full user ID: [{user_id}] ").strip()

    if _user_id:
        user_id = _user_id

    device_name = "matrix-nio"
    _device_name = input(f"Choose a name for this device: [{device_name}] ").strip()

    if _device_name:
        device_name = _device_name

    client = AsyncClient(homeserver, user_id)

    pw = getpass.getpass()

    resp = await client.login(pw, device_name=device_name)

    # check that we logged in successfully
    if isinstance(resp, LoginResponse):
        write_details_to_disk(resp, homeserver)
    else:
        print(f'homeserver = "{homeserver}"; user = "{user_id}"')
        print(f"Failed to log in: {resp}")
        sys.exit(1)

    print(
        "Logged in using a password. Credentials were stored.",
        "Try running the script again to login with credentials.",
    )


async def main() -> None:
    # If there are no previously-saved credentials, we'll use the password
    if not os.path.exists(CONFIG_FILE):
        await login()

    # Otherwise the config file exists, so we'll use the stored credentials
    else:
        # open the file in read-only mode
        print(f"Loading config file from {CONFIG_FILE}...")
        async with aiofiles.open(CONFIG_FILE, "r") as f:
            contents = await f.read()
        config = json.loads(contents)

        bot = DCBot(
            homeserver=config["homeserver"],
            user=config["user_id"],
            device_id=config["device_id"],
            access_token=config["access_token"],
        )

        atexit.register(lambda: asyncio.run(bot.client.close()))

        await bot.run()

    # Either way we're logged in here, too
    await bot.client.close()


if __name__ == "__main__":
    asyncio.run(main())
