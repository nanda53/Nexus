from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_
from jose import jwt, JWTError
from contextlib import asynccontextmanager
import json
import uuid
import redis
import os

from . import models, schemas, security, transfer_engine
from .database import engine, get_db
from .seed import run_seed

# Safe startup sequence via lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Create tables first
    models.Base.metadata.create_all(bind=engine)
    # 2. Run initial seeder safely
    try:
        run_seed()
    except Exception as e:
        print(f"Seed notice: {e}")
    yield

app = FastAPI(title="Core Banking API", lifespan=lifespan)

# In AWS the browser calls /api on the same origin (nginx), so CORS is not needed.
# These are only for local development; add more via CORS_ORIGINS if required.
allowed_origins = [
    #"http://localhost:5173",
    "http://localhost:3000",
]
allowed_origins += [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True
)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return uuid.UUID(user_id)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "Nexus Banking API"}

@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    hashed_pw = security.get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_pw)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    acc = models.Account(account_number=f"ACC-{uuid.uuid4().hex[:6].upper()}", user_id=db_user.id, balance=10000.00)
    db.add(acc)
    db.commit()
    return {"message": "User and Account created", "user_id": db_user.id}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    token = security.create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/accounts")
def get_my_accounts(user_id: uuid.UUID = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Account).filter(models.Account.user_id == user_id).all()

@app.post("/transfers")
def create_transfer(req: schemas.TransferRequest, user_id: uuid.UUID = Depends(get_current_user), db: Session = Depends(get_db)):
    """Idempotent transfer. Same idempotency_key => money moves once and the
    original response is replayed. Redis is the fast lock; the unique key on
    the transactions table is the safety net."""
    redis_key = f"idempotency:{user_id}:{req.idempotency_key}"
    try:
        acquired = redis_client.set(redis_key, "processing", nx=True, ex=60)
        if not acquired:
            cached = redis_client.get(redis_key)
            if cached and cached != "processing":
                return json.loads(cached)  # replay the original result
            raise HTTPException(status_code=409, detail="Transfer already in progress.")
    except redis.RedisError:
        # Fail closed: never move money if we cannot guarantee idempotency.
        raise HTTPException(status_code=503, detail="Service temporarily unavailable.")

    try:
        result = transfer_engine.execute_transfer(db, req, user_id)
        try:
            redis_client.set(redis_key, json.dumps(result, default=str), ex=86400)
        except redis.RedisError:
            pass  # DB unique key still protects against duplicates
        return result
    except Exception:
        try:
            redis_client.delete(redis_key)  # let the user retry after a failure
        except redis.RedisError:
            pass
        raise

@app.get("/transactions")
def get_transactions(user_id: uuid.UUID = Depends(get_current_user), db: Session = Depends(get_db)):
    user_accounts = db.query(models.Account.id).filter(models.Account.user_id == user_id).all()
    account_ids = [acc.id for acc in user_accounts]
    
    transactions = db.query(models.Transaction).filter(
        or_(
            models.Transaction.source_account_id.in_(account_ids),
            models.Transaction.destination_account_id.in_(account_ids)
        )
    ).order_by(models.Transaction.created_at.desc()).limit(10).all()
    return transactions