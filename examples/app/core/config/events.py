from pydantic import BaseModel, ConfigDict, Field


class EventsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    topic_arn: str = Field(pattern=r"^arn:aws:sns:[a-z0-9-]+:\d{12}:[\w-]+$")
    sweep_batch_size: int = Field(default=100, gt=0)

    @property
    def region(self) -> str:
        return self.topic_arn.split(":")[3]
