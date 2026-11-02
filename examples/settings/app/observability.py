import logging
import os

from app.config.app import AppSettings


class DeploymentFilter(logging.Filter):
    """Adds the release and the Lambda function version to every log record."""

    def __init__(self, app: AppSettings) -> None:
        super().__init__()
        self.version = app.version            # the release, from the image ("1.4.2")
        # The published Lambda version ("7"), set by Lambda: immutable, unlike a "canary" label.
        # A flag change without a new release is a new version too. None when not on Lambda.
        self.function_version = os.environ.get("AWS_LAMBDA_FUNCTION_VERSION")

    def filter(self, record: logging.LogRecord) -> bool:
        record.version = self.version
        record.function_version = self.function_version
        return True
