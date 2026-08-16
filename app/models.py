from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserState(Base):
    __tablename__ = "user_states"

    line_user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    mode: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        UniqueConstraint(
            "line_user_id",
            "stock_code",
            "metric",
            "operator",
            "threshold",
            "active",
            name="uq_active_rule_shape",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_user_id: Mapped[str] = mapped_column(String(128), index=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64), default="")
    market: Mapped[str] = mapped_column(String(8), default="tse")
    metric: Mapped[str] = mapped_column(String(16), default="price")
    operator: Mapped[str] = mapped_column(String(4), default=">=")
    threshold: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)


class StockMasterEntry(Base):
    __tablename__ = "stock_master_entries"
    __table_args__ = (
        UniqueConstraint("market", "code", name="uq_stock_master_market_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    market: Mapped[str] = mapped_column(String(8), index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SyncState(Base):
    __tablename__ = "sync_states"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
