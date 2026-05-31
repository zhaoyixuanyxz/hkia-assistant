from __future__ import annotations

from fastapi import APIRouter

from app.survey_template import template_field_metadata

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/report-survey-template")
def report_survey_template() -> dict:
    return template_field_metadata()
