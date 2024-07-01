
import asyncio
import time

from nio import (
    AsyncClient,
    Event,
    MatrixRoom,
    RoomMessageText,
)

class DCBot:

    client: AsyncClient

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


    def __init__(self,
                 homeserver: str = '',
                 user: str = '',
                 device_id: str = '',
                 access_token: str = '',
                 ) -> None:
        self.client = AsyncClient(
            homeserver,
            user,
            device_id=device_id
        )
        self.client.access_token = access_token


    async def send_test_message(
            self,
            room_id: str = '!arcYMpuEJhIvmonMaG:matrix.org',
            body: str = 'Hello world!',
    ):
        assert self.client
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": "Hello world!",
                # "m.relates_to": {
                #     "m.in_reply_to": {
                #         "event_id": "$eventId0123456789ABCDEFabcdef0123456789AB",
                #     }
                # },
            },
        )


    async def message_callback(self, room: MatrixRoom, event: Event) -> None:
        assert self.client
        assert isinstance(event, RoomMessageText)
        # deepin-sysdev-team
        if room.room_id != '!arcYMpuEJhIvmonMaG:matrix.org':
            return
        if event.sender not in self.REQUESTER_MAP:
            print(event.sender)
            return
        requester = self.REQUESTER_MAP[event.sender]

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
                    await self.client.room_send(
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
                await self.client.room_send(
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

            results = []
            for package in packages:
                print(f'Updating {package}')
                p = asyncio.create_subprocess_exec(
                    'python', '-m', 'dcbot.update', package, topic, '', requester,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                results.append(p)

            results = await asyncio.gather(*results)

            await self.client.room_send(
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


    async def run(self, timeout: int = 30000):
        self.client.add_event_callback(self.message_callback, RoomMessageText)
        await self.client.sync_forever(
            timeout=timeout,
            set_presence="online",
        )