from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class EventIn(BaseModel):
    timestamp: datetime
    event_type: str
    user_id: str
    device_id: str
    ip_address: str
    service: str
    resource: str


class EventOut(BaseModel):
    event_id: str
    timestamp: str
    event_type: str
    user_id: str
    device_id: str
    ip_address: str
    service: str
    resource: str


class WhatIfRequest(BaseModel):
    action: str       # isolate | block | disable
    target: str


class WhatIfResponse(BaseModel):
    before: int
    after: int
    delta: int
    summary: str