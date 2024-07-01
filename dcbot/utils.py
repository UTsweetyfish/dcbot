
def validate_topicname(topic_name: str) -> bool:
    if not topic_name.startswith('topic-'):
        return False

    deny_list = ",:"
    for c in deny_list:
        if c in topic_name:
            return False

    return True
