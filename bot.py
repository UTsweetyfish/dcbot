#!/usr/bin/env python3

import asyncio
import getpass
import json
import os
import subprocess
import sys
import time
from types import NoneType

import aiofiles

from nio import AsyncClient, LoginResponse
from nio import Event, MatrixRoom, RoomMessageText

CONFIG_FILE = "credentials.json"

REQUESTER_MAP = {
    '@billchenchina:deepin.org': 'UTSweetyfish',
    '@blumia:matrix.org': 'BLumia',
    '@chenchongbiao:deepin.org': 'chenchongbiao',
    '@deepin-community:matrix.org': 'Zeno-sole',
    '@golf66:deepin.org': 'hudeng-go',
    '@longlong:deepin.org': 'xzl01',
    '@yukari:ewe.moe': 'YukariChiba',
    '@telegram_283338155:t2bot.io': 'YukariChiba',
    '@telegram_310653493:t2bot.io': 'RevySR',
    '@avenger_285714:matrix.org': 'Avenger-285714',
}

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


async def message_callback(room: MatrixRoom, event: Event) -> None:
    assert client
    assert isinstance(event, RoomMessageText)
    # deepin-sysdev-team
    if room.room_id != '!arcYMpuEJhIvmonMaG:matrix.org':
        return
    if event.sender not in REQUESTER_MAP:
        print(event.sender)
        return
    requester = REQUESTER_MAP[event.sender]

    print(
        f"Message received in room {room.display_name} ({room.room_id})\n"
        f"{room.user_name(event.sender)} ({event.sender}) | {event.body}"
    )

    if event.body[0] != '/':
        print('Not a command, ignored.')

    command = event.body.split()[0]
    # (package, branch, github_project_name, requester)
    packages = []
    topic = ''

    if command in ['/update', '/batchupdate']:
        try:
            if int(open('LAST-UPDATED').read().strip()) < time.time() - 2 * 60 * 60:
                # LAST-UPDATED fails more than 1 hours ago
                # Is apt-get down?
                await client.room_send(
                    room.room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": "LAST-UPDATED fails more than 2 hours ago. Is apt-get down?",
                        "m.relates_to": {
                            "m.in_reply_to": {
                                "event_id": event.event_id
                            }
                        }
                    }
                )
                return
            else:
                pass
        except OSError:
            # LAST-UPDATED does not present
            await client.room_send(
                room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "LAST-UPDATED not found.",
                    "m.relates_to": {
                        "m.in_reply_to": {
                            "event_id": event.event_id
                        }
                    }
                }
            )
            return
    match command:
        case "/update":
            # no branch
            # package
            # requester
            # do_update()
            # /update package
            args = event.body.split()
            if len(args) != 2:
                # TODO:
                return
            topic = ''
            packages.append(args[1])
        case "/batchupdate":
            # topic, [package, [package, [package, [package, ...]]]]
            args = event.body.split()
            # /update topic-xxx pkg1 pkg2
            if len(args) < 3:
                # TODO:
                return
            topic = args[1]
            if not topic.startswith('topic-'):
                return
            packages += args[2:]
    if packages:
        for package in packages:
            print(f'Updating {package}')
            r = subprocess.run([
                'python', 'update.py', package, topic, '', requester
            ], capture_output=True, text=True)
            # stdout = r.stdout
            # stderr = r.stderr
        await client.room_send(
            room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": "Done.",
                "m.relates_to": {
                    "m.in_reply_to": {
                        "event_id": event.event_id
                    }
                }
            }
        )
async def main() -> None:
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
        client.add_event_callback(message_callback, RoomMessageText)
        await client.sync_forever(timeout=30000)  # milliseconds
    # Either way we're logged in here, too
    await client.close()


asyncio.run(main())
