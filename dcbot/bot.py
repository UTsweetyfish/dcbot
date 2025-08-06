import asyncio
import logging
import os
import time
from asyncio.subprocess import Process

from nio import AsyncClient, Event, MatrixRoom, RoomMessageText

from dcbot.utils import already_processed, mark_processed, validate_topicname

logger = logging.getLogger(__name__)


class DCBot:
    client: AsyncClient

    REQUESTER_MAP = {
        "@avenger_285714:matrix.org": "Avenger-285714",
        "@billchenchina:deepin.org": "UTSweetyfish",
        "@blumia:matrix.org": "BLumia",
        "@chenchongbiao:deepin.org": "chenchongbiao",
        "@deepin-community:matrix.org": "Zeno-sole",
        "@golf66:deepin.org": "hudeng-go",
        "@longlong:deepin.org": "xzl01",
        "@telegram_1618120212:t2bot.io": "Gui-Yue",
        "@telegram_283338155:t2bot.io": "YukariChiba",
        "@telegram_310653493:t2bot.io": "RevySR",
        "@telegram_80332535:t2bot.io": "MingcongBai",
        "@yukari:ewe.moe": "YukariChiba",
        "@zengwei:matrix.org": "zengwei00",
        "@telegram_618469085:t2bot.io": "Cryolitia",
        "@cryolitia:matrix.org": "Cryolitia",
        "@qaqland:deepin.org": "qaqland",
    }

    def __init__(
        self,
        homeserver: str = "",
        user: str = "",
        device_id: str = "",
        access_token: str = "",
    ) -> None:
        self.client = AsyncClient(homeserver, user, device_id=device_id)
        self.client.access_token = access_token

    async def send_test_message(
        self,
        room_id: str = "!arcYMpuEJhIvmonMaG:matrix.org",
        body: str = "Hello world!",
    ):
        assert self.client
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": body,
            },
        )

    async def message_callback(self, room: MatrixRoom, event: Event) -> None:
        assert self.client
        assert isinstance(event, RoomMessageText)

        event_id = event.event_id

        if event.body[0] not in ["/", "!"]:
            logger.info(
                "Not a command, ignored. Event ID: %s, Sender: %s",
                event_id,
                event.sender,
            )
            return

        # deepin-sysdev-team
        if room.room_id != "!arcYMpuEJhIvmonMaG:matrix.org":
            logger.info(
                "Not in deepin-sysdev-team room, ignored. Event ID: %s, Sender: %s",
                event_id,
                event.sender,
            )
            return

        logger.info(
            "Message received in room %s (%s)\n%s (%s) | %s",
            room.display_name,
            room.room_id,
            room.user_name(event.sender),
            event.sender,
            event.body,
        )

        command = event.body.split()[0]
        command_prefix = command[0]
        command = command[1:]

        # (package, branch, github_project_name, requester)
        packages = []
        topic = ""

        if command not in {"update", "batchupdate"}:
            logger.info(
                "Unsupported command: !%s. Event ID: %s, Sender: %s",
                command,
                event_id,
                event.sender,
            )
            return

        if event.sender not in self.REQUESTER_MAP:
            logger.info("Unauthorized sender: %s", event.sender)
            await self.client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "Unauthorized.\nPlease add yourself to "
                    + "https://github.com/UTsweetyfish/dcbot/blob/main/dcbot/bot.py",
                    "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                },
            )
            return

        requester = self.REQUESTER_MAP[event.sender]

        # check if event is already processed
        if await already_processed(event_id):
            logger.info("Event %s already processed. Skipping.", event_id)
            return

        # check LAST-UPDATED
        MAX_RETRY_COUNT = 3
        for _ in range(MAX_RETRY_COUNT):
            if not os.path.exists("LAST-UPDATED"):
                # sleep and retry
                await asyncio.sleep(5)  # in seconds

        # All retries failed, LAST-UPDATED still not exist
        if not os.path.exists("LAST-UPDATED"):
            # LAST-UPDATED still does not present
            await self.client.room_send(
                room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "LAST-UPDATED not found.",
                    "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                },
            )
            return

        if int(open("LAST-UPDATED").read().strip()) < time.time() - 2 * 60 * 60:
            # LAST-UPDATED fails more than 1 hours ago
            # Is apt-get down?
            await self.client.room_send(
                room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "LAST-UPDATED fails more than 2 hours ago. Is apt-get down?",
                    "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                },
            )
            return

        # !update pkg
        # !batchupdate topic-xxx pkg1 pkg2 ...
        args = event.body.split()

        match command:
            case "update":
                # no branch
                # package
                # requester
                # do_update()
                # !update package
                if len(args) != 2:
                    logger.info("!update should only have one argument. Skipping.")
                    return
                topic = ""
                packages = [args[1]]
            case "batchupdate":
                # topic, [package, [package, [package, [package, ...]]]]
                # !batchupdate topic-xxx pkg1 pkg2
                if len(args) < 3:
                    logger.info(
                        "!batchupdate should have at least topic-xxx and pkg1. Skipping."
                    )
                    return
                topic = args[1]
                packages = args[2:]

        if topic:
            if not topic.startswith("topic-"):
                await self.client.room_send(
                    room.room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": "Topic name should prefix with topic-.",
                        "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                    },
                )
                return

            if not validate_topicname(topic):
                await self.client.room_send(
                    room.room_id,
                    message_type="m.room.message",
                    content={
                        "msgtype": "m.text",
                        "body": "Topic name invalid.",
                        "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                    },
                )
                return

        results: list[Process] = []
        for package in packages:
            logger.info("Updating %s", package)
            p = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "dcbot.update",
                package,
                topic,
                "",
                requester,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            results.append(p)

        success_count = 0

        for result in results:
            await result.wait()
            logger.info(result)
            logger.info(type(result))
            if result.returncode == 0:
                success_count += 1
            else:
                if result.stderr:
                    logger.error(await result.stderr.read())

        await mark_processed(event_id)

        if success_count == 0:
            await self.client.room_send(
                room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "All failed 😭😭😭",
                    "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                },
            )
        elif success_count < len(results):
            # 😶😶😶
            await self.client.room_send(
                room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": f"Done. {success_count}/{len(results)} succeeded 😶😶😶\n",
                    "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                },
            )
        elif success_count == len(results):
            await self.client.room_send(
                room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "Done. All succeeded 🎉🎉🎉",
                    "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                },
            )
        else:
            # unreachable
            assert False

        if command_prefix == "/":
            await self.client.room_send(
                room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": "/update or /batchupdate is deprecated, please use !update and !batchupdate",
                    "m.relates_to": {"m.in_reply_to": {"event_id": event_id}},
                },
            )

    async def run(self, timeout: int = 30000):
        self.client.add_event_callback(self.message_callback, RoomMessageText)
        await self.client.sync_forever(
            timeout=timeout,
            set_presence="online",
        )
