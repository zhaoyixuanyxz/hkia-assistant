from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, UserSurveyLibrary
from app.schemas import UserSurveyLibraryOut, UserSurveyLibraryUpsert
from app.survey_template import SURVEY_TEMPLATE_VERSION, coerce_survey_answers

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/survey-library", response_model=UserSurveyLibraryOut)
def get_survey_library(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserSurveyLibraryOut:
    row = db.get(UserSurveyLibrary, user.id)
    if row is None:
        return UserSurveyLibraryOut(
            answers={},
            template_version=SURVEY_TEMPLATE_VERSION,
            updated_at=None,
        )
    return UserSurveyLibraryOut(
        answers=row.answers_json if isinstance(row.answers_json, dict) else {},
        template_version=row.template_version or SURVEY_TEMPLATE_VERSION,
        updated_at=row.updated_at,
    )


@router.put("/me/survey-library", response_model=UserSurveyLibraryOut)
def put_survey_library(
    body: UserSurveyLibraryUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserSurveyLibraryOut:
    coerced = coerce_survey_answers(body.answers)
    row = db.get(UserSurveyLibrary, user.id)
    if row is None:
        row = UserSurveyLibrary(
            user_id=user.id,
            answers_json=coerced,
            template_version=SURVEY_TEMPLATE_VERSION,
        )
        db.add(row)
    else:
        row.answers_json = coerced
        row.template_version = SURVEY_TEMPLATE_VERSION
        row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return UserSurveyLibraryOut(
        answers=coerced,
        template_version=row.template_version,
        updated_at=row.updated_at,
    )
