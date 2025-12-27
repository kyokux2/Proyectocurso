import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .db import Base

class Role(str, enum.Enum):
    admin = "admin"
    user = "user"

class SubStatus(str, enum.Enum):
    active = "ACTIVE"
    past_due = "PAST_DUE"
    canceled = "CANCELED"

class TxStatus(str, enum.Enum):
    succeeded = "SUCCEEDED"
    failed = "FAILED"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.user)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subscriptions = relationship("Subscription", back_populates="user")

class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    period_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(Enum(SubStatus), nullable=False, default=SubStatus.active)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="subscriptions")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, nullable=False, default="RUB")
    status = Column(Enum(TxStatus), nullable=False)
    idempotency_key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
