from pydantic import BaseModel, EmailStr
from datetime import datetime
from decimal import Decimal

class PlanOut(BaseModel):
    id: int
    name: str
    price: Decimal
    period_days: int
    class Config:
        from_attributes = True

class SubscribeIn(BaseModel):
    email: EmailStr
    plan_id: int
    idempotency_key: str
    force_fail: bool = False  # para simular fallo

class SubscribeOut(BaseModel):
    subscription_id: int
    status: str
    current_period_end: datetime
