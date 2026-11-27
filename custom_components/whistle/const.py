DOMAIN = "whistle"
SCHEMA = 1

TOPIC_STATUS = "whistle/+/status"
TOPIC_DETECTION = "whistle/+/detection"

# Verdicts a node sends that are not whistles anyone should act on.
IGNORED_TYPES = {"rejected"}

CONF_COLLECT_S = "collect_s"
CONF_MATCH_S = "match_s"
CONF_CONFIDENT_DB = "confident_db"
CONF_MAX_AGE_S = "max_age_s"
DEFAULTS = {
    CONF_COLLECT_S: 1.5,  # each node's verdict waits on its own server round trip
    CONF_MATCH_S: 0.4,
    CONF_CONFIDENT_DB: 3.0,
    CONF_MAX_AGE_S: 6.0,
}


def node_of(topic: str) -> str:
    return topic.split("/")[1]


def device_identifier(node: str) -> tuple[str, str]:
    """The identifier the node's own MQTT discovery gives its HA device."""
    return ("mqtt", f"whistle_{node}")
