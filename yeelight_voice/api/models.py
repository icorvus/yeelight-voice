from pydantic import BaseModel, Field


class BulbColor(BaseModel):
    r: int
    g: int
    b: int


class BulbStatus(BaseModel):
    id: str
    name: str
    ip: str
    power: str
    brightness: int
    color: BulbColor
    color_temp: int
    color_mode: int


class ChatResponse(BaseModel):
    transcript: str
    response: str
    bulbs: list[BulbStatus]


class DiscoverResponse(BaseModel):
    bulbs: list[str]
    count: int


class HistoryItem(BaseModel):
    transcript: str
    response: str


class ResetResponse(BaseModel):
    ok: bool


class TextRequest(BaseModel):
    text: str = Field(max_length=1000)
