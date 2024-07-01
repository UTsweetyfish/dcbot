
def validate_topicname(topic_name: str) -> bool:
    if not topic_name.startswith('topic-'):
        return False

    deny_list = ",:"
    for c in deny_list:
        if c in topic_name:
            return False

    return True


from asyncio import Lock
import json

lock = Lock()

# def validate_event_id(event_id: str):
#     pass

# [event1, event2, event3]

async def already_processed(event_id: str):
    async with lock:
        done_events = []
        try:
            with open('done-events.json') as f:
                done_events: list[str] = json.load(f)
                if event_id in done_events:
                    return True
                return False
        except FileNotFoundError:
            print('Creating done-events.json...')
            with open('done-events.json', 'w') as f:
                json.dump([], f)


async def mark_processed(event_id: str):
    async with lock:
        done_events = []
        with open('done-events.json') as f:
            done_events: list[str] = json.load(f)
            if event_id in done_events:
                return True
        done_events.append(event_id)
        with open('done-events.json', 'w') as f:
            json.dump(done_events, f)