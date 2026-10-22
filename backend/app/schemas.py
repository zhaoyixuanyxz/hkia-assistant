from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.chart_spec import GLOBAL_MAX_REPORT_CHARTS


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: str
    password: str
    display_name: str = ""


class UserLogin(BaseModel):
    email: str
    password: str


ChartType = Literal[
    "radar",
    "pie",
    "donut",
    "line",
    "area",
    "bar",
    "bar_horizontal",
    "scatter",
    "radial_bar",
    "funnel",
    "composed",
    "treemap",
]


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str = "user"

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationPatch(BaseModel):
    is_pinned: bool | None = None


class ConversationOut(BaseModel):
    id: int
    title: str
    status: str
    is_pinned: bool = False
    pinned_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str
    locale: str | None = None


class ReportGenerateBody(BaseModel):
    locale: str | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]
    profile_summary: str
    profile_structured: dict[str, Any] | None = None
    key_memories: list[str] = Field(default_factory=list)


class ConversationSurveyUpsert(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
    merge_to_profile: bool = False
    sync_to_user_library: bool = False


class ConversationSurveyOut(BaseModel):
    conversation_id: int
    answers: dict[str, Any]
    template_version: str
    status: str
    report_depth: str | None = None
    optional_filled_count: int = 0
    required_complete: bool = False


class UserSurveyLibraryUpsert(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class UserSurveyLibraryOut(BaseModel):
    answers: dict[str, Any]
    template_version: str
    updated_at: datetime | None = None


class ChartSpec(BaseModel):
    type: ChartType
    title: str
    data: list[dict[str, Any]]


class ReportProductPick(BaseModel):
    product_id: str = ""
    name: str = ""
    rationale: str = ""
    source_url: str = ""


class ReportPayload(BaseModel):
    title: str = ""
    user_background: str = ""
    insights: str = ""
    allocation_direction: str = ""
    product_category_suggestions: str = ""
    risk_notes: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    concrete_product_picks: list[ReportProductPick] = Field(default_factory=list)
    limited_data_notice: str = (
        "当前报告基于示例产品与有限公开市场信息整理，具体产品名称与条款以官方资料为准。"
    )
    disclaimer: str = ""

    @field_validator("charts")
    @classmethod
    def chart_count(cls, v: list[ChartSpec]) -> list[ChartSpec]:
        if len(v) > GLOBAL_MAX_REPORT_CHARTS:
            return v[:GLOBAL_MAX_REPORT_CHARTS]
        return v


class ReportOut(BaseModel):
    id: int
    conversation_id: int
    title: str
    body: ReportPayload
    disclaimer_text: str
    created_at: datetime


class ProductStubOut(BaseModel):
    id: str
    name: str
    category: str
    summary: str
    source_url: str
    is_sample: bool = True
    updated_at: str
    review_status: str = "active"
    match_score: float | None = None
    match_reason: str | None = None


class ProductDetailOut(BaseModel):
    id: str
    name: str
    category: str
    highlights: str = ""
    coverage_summary: str = ""
    target_audience: str = ""
    clause_summary: str = ""
    source_note: str = ""
    official_url: str = ""
    is_sample: bool = True
    sum_assured: str | None = None
    premium: str | None = None
    excerpt_date: str | None = None  # ISO date YYYY-MM-DD when present
    updated_at: str
    review_status: str = "active"


class MarketIndicatorOut(BaseModel):
    id: str
    name: str
    value: str
    explanation: str
    source_url: str
    updated_at: str
    trend_note: str = ""


class DataUpdateJobOut(BaseModel):
    id: int
    job_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str = ""
    detail_json: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class ProductRetrievalRequest(BaseModel):
    profile_summary: str = ""
    structured_hints: dict[str, Any] = Field(default_factory=dict)
    goals: str = ""
    product_categories: list[str] = Field(default_factory=list)
    budget_hint: str = ""
    risk_appetite: str = ""
    exclusions: list[str] = Field(default_factory=list)


class ProductCandidate(BaseModel):
    product_id: str
    name: str
    category: str = ""
    match_score: float = 0.0
    hit_fields: list[str] = Field(default_factory=list)
    match_reason: str = ""
    source_url: str = ""
    updated_at: str = ""
