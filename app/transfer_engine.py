import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import (
    Account, AccountStatus, Transaction, JournalEntry, EntryDirection,
)


def _replay(txn: Transaction) -> dict:
    return {"transaction_id": txn.id, "reference": txn.reference_number,
            "status": "SUCCESS", "duplicate": True}


def execute_transfer(db: Session, req, user_id: uuid.UUID):
    """Move money atomically: lock both rows (in sorted order to avoid
    deadlocks), validate, write the transaction + double-entry journal,
    then commit once."""

    # Resolve recipient (UUID or account number)
    dest_id = req.destination_account_id
    if dest_id is None:
        dest_id = db.execute(
            select(Account.id).where(Account.account_number == req.destination_account_number)
        ).scalar_one_or_none()
        if dest_id is None:
            raise HTTPException(status_code=404, detail="Recipient account not found.")

    if req.source_account_id == dest_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same account.")

    # Database-level idempotency safety net (survives Redis expiry/restart)
    existing = db.execute(
        select(Transaction).where(Transaction.idempotency_key == req.idempotency_key)
    ).scalar_one_or_none()
    if existing:
        if existing.source_account_id == req.source_account_id:
            return _replay(existing)
        raise HTTPException(status_code=409, detail="Idempotency key already used.")

    try:
        locked = {}
        for acc_id in sorted([req.source_account_id, dest_id]):
            acc = db.execute(
                select(Account).where(Account.id == acc_id).with_for_update()
            ).scalar_one_or_none()
            if not acc:
                raise HTTPException(status_code=404, detail="Account not found.")
            locked[acc_id] = acc

        sender, receiver = locked[req.source_account_id], locked[dest_id]

        if sender.user_id != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access to source account.")
        if sender.status != AccountStatus.ACTIVE or receiver.status != AccountStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Account is not active.")
        if sender.balance < req.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds.")

        ref = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        txn = Transaction(
            reference_number=ref, idempotency_key=req.idempotency_key,
            source_account_id=sender.id, destination_account_id=receiver.id,
            amount=req.amount,
        )
        db.add(txn)
        db.flush()

        sender.balance -= req.amount
        receiver.balance += req.amount
        sender.version += 1
        receiver.version += 1

        db.add(JournalEntry(transaction_id=txn.id, account_id=sender.id,
                            direction=EntryDirection.DEBIT, amount=req.amount,
                            balance_after=sender.balance))
        db.add(JournalEntry(transaction_id=txn.id, account_id=receiver.id,
                            direction=EntryDirection.CREDIT, amount=req.amount,
                            balance_after=receiver.balance))

        db.commit()
        return {"transaction_id": txn.id, "reference": ref, "status": "SUCCESS"}

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        # Two identical requests raced past the checks; the unique key wins.
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate transfer request.")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Transfer failed. Please try again.")
