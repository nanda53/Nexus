from .database import engine, SessionLocal
from . import models, security

def run_seed():
    # 1. ALWAYS create tables first before executing any queries!
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 2. Check if users already exist
        user_count = db.query(models.User).count()
        if user_count > 0:
            print("Database already seeded. Skipping.")
            return

        print("Seeding initial demo data...")
        # 3. Create demo users (Alice & Bob)
        alice = models.User(
            email="alice@bank.com",
            hashed_password=security.get_password_hash("demo123"),
            role="customer"
        )
        bob = models.User(
            email="bob@bank.com",
            hashed_password=security.get_password_hash("demo123"),
            role="customer"
        )
        db.add_all([alice, bob])
        db.commit()
        db.refresh(alice)
        db.refresh(bob)

        # 4. Create demo accounts
        acc_alice = models.Account(
            account_number="123",
            user_id=alice.id,
            balance=10000.00
        )
        acc_bob = models.Account(
            account_number="456",
            user_id=bob.id,
            balance=5000.00
        )
        db.add_all([acc_alice, acc_bob])
        db.commit()

        print("Seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()