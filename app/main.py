from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base, engine, get_db
from .models import Plan
from .schemas import PlanOut, SubscribeIn, SubscribeOut
from .services import subscribe
from .models import User, Subscription, Transaction


app = FastAPI(title="Subscription MVP")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # seed plans si no existen
    from sqlalchemy.orm import Session as Sess
    db = Sess(bind=engine)
    try:
        existing = db.execute(select(Plan)).scalars().all()
        if not existing:
            db.add_all([
                Plan(name="monthly", price=499, period_days=30, is_active=True),
                Plan(name="yearly", price=4990, period_days=365, is_active=True),
            ])
            db.commit()
    finally:
        db.close()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/plans", response_model=list[PlanOut])
def get_plans(db: Session = Depends(get_db)):
    return db.execute(select(Plan).where(Plan.is_active == True)).scalars().all()

@app.post("/subscribe", response_model=SubscribeOut)
def post_subscribe(payload: SubscribeIn, db: Session = Depends(get_db)):
    try:
        tx, sub = subscribe(
            db=db,
            email=payload.email,
            plan_id=payload.plan_id,
            idempotency_key=payload.idempotency_key,
            force_fail=payload.force_fail
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal error")

    if not sub:
        # pago falló
        raise HTTPException(status_code=402, detail=f"Payment failed. tx_status={tx.status}")

    return {
        "subscription_id": sub.id,
        "status": sub.status,
        "current_period_end": sub.current_period_end
    }
@app.get("/me/subscription")
def my_subscription(email: str, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub = db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.id.desc())
    ).scalar_one_or_none()

    if not sub:
        return {"subscription": None}

    return {
        "subscription": {
            "id": sub.id,
            "status": sub.status,
            "plan_id": sub.plan_id,
            "current_period_end": sub.current_period_end,
        }
    }

@app.get("/me/transactions")
def my_transactions(email: str, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    txs = db.execute(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.id.desc())
    ).scalars().all()

    return {
        "transactions": [
            {
                "id": t.id,
                "subscription_id": t.subscription_id,
                "amount": str(t.amount),
                "currency": t.currency,
                "status": t.status,
                "idempotency_key": t.idempotency_key,
                "created_at": t.created_at,
            }
            for t in txs
        ]
    }
from .services import run_renewals

@app.post("/internal/run-renewals")
def trigger_renewals(db: Session = Depends(get_db)):
    result = run_renewals(db)
    db.commit()
    return result


