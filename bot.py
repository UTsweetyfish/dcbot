#!/usr/bin/env python3

import asyncio
import getpass
import json
import os
import sys

from types import NoneType

import aiofiles

from nio import AsyncClient, LoginResponse
from nio import Event, MatrixRoom, RoomMessageText

CONFIG_FILE = "credentials.json"



client: AsyncClient | NoneType = None

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



async def main() -> None:
    # TODO: OOP
    global client
    # If there are no previously-saved credentials, we'll use the password
    if not os.path.exists(CONFIG_FILE):
        print(
            "First time use. Did not find credential file. Asking for "
            "homeserver, user, and password to create credential file."
        )
        homeserver = "https://matrix.org"
        homeserver = input(f"Enter your homeserver URL: [{homeserver}] ")

        if not (homeserver.startswith("https://") or homeserver.startswith("http://")):
            homeserver = "https://" + homeserver

        user_id = "@dcbot:matrix.org"
        user_id = input(f"Enter your full user ID: [{user_id}] ")

        device_name = "matrix-nio"
        device_name = input(f"Choose a name for this device: [{device_name}] ")

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

    # Otherwise the config file exists, so we'll use the stored credentials
    else:
        # open the file in read-only mode
        print(f'Loading config file from {CONFIG_FILE}...')
        async with aiofiles.open(CONFIG_FILE, "r") as f:
            contents = await f.read()
        config = json.loads(contents)
        client = AsyncClient(config["homeserver"])

        client.access_token = config["access_token"]
        client.user_id = config["user_id"]
        client.device_id = config["device_id"]

        # Now we can send messages as the user
        # room_id = "#deepin-sig-sysdev-team"


        # print("Logged in using stored credentials. Sent a test message.")
        # print(await client.join(room_id))
        # print(await client.room_send(
        #     '!arcYMpuEJhIvmonMaG:matrix.org',
        #     message_type="m.room.message",
        #     content={
        #         "msgtype": "m.text",
        #         "body": "Hello world!",
        #         "m.relates_to": {
        #             "m.in_reply_to": {
        #                 "event_id": "$eventId0123456789ABCDEFabcdef0123456789AB"
        #             }
        #         }
        #     },
        # ))
        # client.add_event_callback(message_callback, RoomMessageText)
        # await client.sync_forever(timeout=30000)  # milliseconds
    # Either way we're logged in here, too
    # await client.close()


asyncio.run(main())
