from pydantic import BaseModel
from typing import Dict, List

class User(BaseModel):
    place: int
    points: int
    userUid: str

class EventLocation(BaseModel):
    latitude: float
    longitude: float

class Points(BaseModel):
    people: List[str]
    points: int

class GroupModel(BaseModel):
    uid: str
    title: str
    imageUid: str
    members: Dict[str, str]
    messages: List[str]

class Request(BaseModel):
    receiverUid: str
    senderUid: str
