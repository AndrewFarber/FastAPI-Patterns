import json

import boto3

from app.core.config.events import EventsSettings
from app.core.messaging import sns
from conftest import TEST_VALUES


def test_sns_sender_publishes_with_the_event_type_attribute(aws):
    sqs = boto3.client("sqs")
    queue_url = sqs.create_queue(QueueName="q")["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    boto3.client("sns").subscribe(
        TopicArn=aws, Protocol="sqs", Endpoint=queue_arn
    )

    sns.create_sns_sender(EventsSettings(topic_arn=aws)).send(
        "UserDeactivated", '{"x": 1}'
    )

    [message] = sqs.receive_message(QueueUrl=queue_url)["Messages"]
    envelope = json.loads(message["Body"])
    assert envelope["Message"] == '{"x": 1}'
    assert (
        envelope["MessageAttributes"]["event_type"]["Value"]
        == "UserDeactivated"
    )


def test_sns_client_has_short_timeouts(monkeypatch):
    created = []
    monkeypatch.setattr(
        sns.boto3, "client", lambda *args, **kwargs: created.append(kwargs)
    )
    sns.create_sns_sender(EventsSettings(**TEST_VALUES["events"]))
    [kwargs] = created
    assert kwargs["region_name"] == "us-east-1"
    assert (
        kwargs["config"].connect_timeout,
        kwargs["config"].read_timeout,
    ) == (1, 2)
