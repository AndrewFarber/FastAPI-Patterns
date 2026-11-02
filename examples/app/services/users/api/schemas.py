from pydantic import BaseModel, Field


class UserIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    name: str
    status: str
