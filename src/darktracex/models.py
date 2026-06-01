from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship
from .db import Base


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    investigation_id: Mapped[str] = Column(String(24), unique=True, nullable=False, index=True)
    entity_type: Mapped[str] = Column(String(64), nullable=False)
    target: Mapped[str] = Column(String(256), nullable=False)
    status: Mapped[str] = Column(String(32), nullable=False, default="created")
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    timeline: Mapped[str] = Column(Text, nullable=True)
    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="investigation", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    investigation_id: Mapped[int] = Column(Integer, ForeignKey("investigations.id"), nullable=False)
    category: Mapped[str] = Column(String(64), nullable=False)
    title: Mapped[str] = Column(String(256), nullable=False)
    details: Mapped[str] = Column(Text, nullable=False)
    source: Mapped[str] = Column(String(256), nullable=False)
    timestamp: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    confidence: Mapped[float] = Column(Float, nullable=False, default=0.0)

    investigation: Mapped[Investigation] = relationship("Investigation", back_populates="findings")
