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

class NewMessageChat(BaseModel):
    senderUid: str
    receiverUid: str
    message: str

class NewMessageGroup(BaseModel):
    groupName: str
    senderUid: str
    users: List[str]
    message: str

class GroupModel(BaseModel):
    uid: str
    title: str
    imageUid: str
    members: Dict[str, str]
    messages: List[str]

class Request(BaseModel):
    receiverUid: str
    senderUid: str
