from typing import Any

import boto3

from app.core.aws.values import CLIENT_CONFIG
from app.core.config.events import EventsSettings


class SnsSender:
    def __init__(self, topic_arn: str, client: Any) -> None:
        self._topic_arn = topic_arn
        self._client = client

    def send(self, event_type: str, body: str) -> None:
        self._client.publish(
            TopicArn=self._topic_arn,
            Message=body,
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": event_type}
            },
        )


def build_sns_sender(events: EventsSettings) -> SnsSender:
    return SnsSender(
        events.topic_arn,
        boto3.client("sns", region_name=events.region, config=CLIENT_CONFIG),
    )
