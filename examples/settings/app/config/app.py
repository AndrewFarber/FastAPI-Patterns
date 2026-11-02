from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "orders-api"
    is_prd: bool = False
    debug: bool = False

    # Build metadata: baked into the image by CI, None when running locally
    version: str | None = None
    git_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{7,40}$")
    build_time: AwareDatetime | None = None   # "2026-11-02T10:00:00Z"; a time without a zone is rejected
