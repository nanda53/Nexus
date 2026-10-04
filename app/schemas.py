from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, condecimal, model_validator


class UserCreate(BaseModel):
    email: str = Field(min_length=3, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=6)


class TransferRequest(BaseModel):
    source_account_id: UUID
    # Recipient can be given by internal UUID or by the friendly account number.
    destination_account_id: Optional[UUID] = None
    destination_account_number: Optional[str] = None
    amount: condecimal(gt=0, max_digits=14, decimal_places=4)  # type: ignore
    idempotency_key: str = Field(min_length=8, max_length=100)

    @model_validator(mode="after")
    def need_destination(self):
        if not self.destination_account_id and not self.destination_account_number:
            raise ValueError("Provide destination_account_id or destination_account_number")
        return self
