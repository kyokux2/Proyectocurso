from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import User, Plan, Subscription, Transaction, Role, SubStatus, TxStatus

def get_or_create_user(db: Session, email: str) -> User:
    u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if u:
        return u
    u = User(email=email, role=Role.user)
    db.add(u)
    db.flush()
    return u

def fake_charge(force_fail: bool) -> bool:
    return not force_fail

def subscribe(db: Session, email: str, plan_id: int, idempotency_key: str, force_fail: bool):
    # idempotency: si ya existe un tx con esa key, no cobramos de nuevo
    existing = db.execute(select(Transaction).where(Transaction.idempotency_key == idempotency_key)).scalar_one_or_none()
    if existing:
        # devolvemos el estado basado en lo ya registrado
        sub = None
        if existing.subscription_id:
            sub = db.get(Subscription, existing.subscription_id)
        return existing, sub

    user = get_or_create_user(db, email)
    plan = db.get(Plan, plan_id)
    if not plan or not plan.is_active:
        raise ValueError("Plan not found or inactive")

    ok = fake_charge(force_fail)

    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=plan.period_days)

    sub = None
    if ok:
        sub = Subscription(user_id=user.id, plan_id=plan.id, status=SubStatus.active, current_period_end=period_end)
        db.add(sub)
        db.flush()

    tx = Transaction(
        user_id=user.id,
        subscription_id=sub.id if sub else None,
        amount=plan.price,
        currency="RUB",
        status=TxStatus.succeeded if ok else TxStatus.failed,
        idempotency_key=idempotency_key
    )
    db.add(tx)
    db.flush()
    return tx, sub
def run_renewals(db: Session, now=None):
    from datetime import datetime, timezone, timedelta
    if now is None:
        now = datetime.now(timezone.utc)

    subs = db.execute(
        select(Subscription).where(
            Subscription.status == SubStatus.active,
            Subscription.current_period_end <= now
        )
    ).scalars().all()

    renewed = 0
    failed = 0

    for sub in subs:
        plan = db.get(Plan, sub.plan_id)
        user = db.get(User, sub.user_id)

        period_key = f"renew-{sub.id}-{sub.current_period_end.date()}"

        existing = db.execute(
            select(Transaction).where(Transaction.idempotency_key == period_key)
        ).scalar_one_or_none()
        if existing:
            continue

        ok = True
        if "fail" in user.email:
            ok = False

        if ok:
            sub.current_period_end = now + timedelta(days=plan.period_days)
            tx = Transaction(
                user_id=user.id,
                subscription_id=sub.id,
                amount=plan.price,
                currency="RUB",
                status=TxStatus.succeeded,
                idempotency_key=period_key
            )
            db.add(tx)
            renewed += 1
        else:
            sub.status = SubStatus.past_due
            tx = Transaction(
                user_id=user.id,
                subscription_id=sub.id,
                amount=plan.price,
                currency="RUB",
                status=TxStatus.failed,
                idempotency_key=period_key
            )
            db.add(tx)
            failed += 1

    return {"checked": len(subs), "renewed": renewed, "failed": failed}

