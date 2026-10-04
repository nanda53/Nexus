import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Enum, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base

class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"

class EntryDirection(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="CUSTOMER")
    accounts = relationship("Account", back_populates="owner")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_number = Column(String, unique=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    balance = Column(Numeric(18, 4), default=0.0000)
    status = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE)
    version = Column(Integer, default=0)
    owner = relationship("User", back_populates="accounts")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference_number = Column(String, unique=True)
    idempotency_key = Column(String, unique=True)
    source_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    destination_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    amount = Column(Numeric(18, 4))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"))
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    direction = Column(Enum(EntryDirection))
    amount = Column(Numeric(18, 4))
    balance_after = Column(Numeric(18, 4))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))