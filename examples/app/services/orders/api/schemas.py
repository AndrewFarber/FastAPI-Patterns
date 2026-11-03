from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    user_id: int
    item: str = Field(min_length=1, max_length=200)


class OrderRead(BaseModel):
    id: int
    user_id: int
    item: str
    status: str
