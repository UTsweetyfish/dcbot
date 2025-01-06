from os import getenv
from typing import Awaitable

from redis import Redis


def validate_topicname(topic_name: str) -> bool:
    if not topic_name.startswith("topic-"):
        return False

    deny_list = ",:"
    for c in deny_list:
        if c in topic_name:
            return False

    return True


# def validate_event_id(event_id: str):
#     pass

# [event1, event2, event3]


def _redis_connection():
    r = Redis(
        host=getenv("REDIS_HOST", "localhost"),
        port=int(getenv("REDIS_PORT", "6379")),
        username=getenv("REDIS_USERNAME", default="default"),
        password=getenv("REDIS_PASSWORD", default=None),
        db=int(getenv("REDIS_DB", "0")),
        connection_pool=None,
        encoding="utf-8",
        decode_responses=True,
        health_check_interval=0,
        client_name=None,
    )
    return r


redis_connection = _redis_connection()


async def already_processed(event_id: str):
    processed_events = redis_connection.lrange("processed_events", 0, 100)
    if isinstance(processed_events, Awaitable):
        processed_events = await processed_events
    return event_id in processed_events


async def mark_processed(event_id: str):
    redis_connection.lpush("processed_events", event_id)
    redis_connection.ltrim("processed_events", 0, 100 - 1)
