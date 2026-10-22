from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    survey_library: Mapped["UserSurveyLibrary | None"] = relationship(
        back_populates="user",
        uselist=False,
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(512), default="新会话")
    status: Mapped[str] = mapped_column(String(64), default="active")
    is_pinned: Mapped[bool] = mapped_column(default=False)
    pinned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    rolling_summary: Mapped[str] = mapped_column(Text, default="")
    rolling_folded_message_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
    )
    profiles: Mapped[list["ProfileSnapshot"]] = relationship(back_populates="conversation")
    reports: Mapped[list["Report"]] = relationship(back_populates="conversation")
    supplement_survey: Mapped["ConversationSurvey | None"] = relationship(
        back_populates="conversation",
        uselist=False,
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    summary_text: Mapped[str] = mapped_column(Text, default="")
    structured_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="profiles")


class ConversationSurvey(Base):
    __tablename__ = "conversation_surveys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"),
        unique=True,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    answers_json: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    template_version: Mapped[str] = mapped_column(String(32), default="1")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="supplement_survey")


class UserSurveyLibrary(Base):
    __tablename__ = "user_survey_library"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    answers_json: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    template_version: Mapped[str] = mapped_column(String(32), default="1")
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="survey_library")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    title: Mapped[str] = mapped_column(String(512), default="")
    body_json: Mapped[str] = mapped_column(Text)
    charts_json: Mapped[str] = mapped_column(Text, default="[]")
    disclaimer_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="reports")


class ProductRecommendationTrace(Base):
    __tablename__ = "product_recommendation_traces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id"), nullable=True
    )
    query_json: Mapped[str] = mapped_column(Text, default="{}")
    candidates_json: Mapped[str] = mapped_column(Text, default="[]")
    final_choice_json: Mapped[str] = mapped_column(Text, default="{}")
    rationale_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    highlights: Mapped[str] = mapped_column(Text, default="")
    coverage_summary: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    clause_summary: Mapped[str] = mapped_column(Text, default="")
    official_url: Mapped[str] = mapped_column(String(1024), default="")
    source_note: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review", index=True)
    is_sample: Mapped[bool] = mapped_column(default=False)
    sum_assured: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    premium: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    excerpt_date: Mapped[date | None] = mapped_column(nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sources: Mapped[list["ProductSource"]] = relationship(back_populates="product")


class ProductSource(Base):
    __tablename__ = "product_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="manual")
    ref: Mapped[str] = mapped_column(String(512), default="")
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="sources")


class MarketIndicator(Base):
    __tablename__ = "market_indicators"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    value_text: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    trend_note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DataUpdateJob(Base):
    __tablename__ = "data_update_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
