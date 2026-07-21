from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import delete, desc, func, nullslast, select
from sqlalchemy.orm import Session

from app.agents.conversation_runner import merge_rolling_conversation_summary, run_conversation_turn
from app.agents.report_graph import build_report_graph
from app.compliance import (
    assistant_content_for_llm,
    assistant_pipeline_failure_reply,
    finalize_chat_assistant_text,
    merge_report_disclaimer,
)
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.embeddings import get_embedding_service
from app.locale_support import normalize_locale
from app.llm import (
    LLMService,
    get_llm_service,
    report_fallback,
)
from app.models import (
    Conversation,
    ConversationSurvey,
    Message,
    ProductRecommendationTrace,
    ProfileSnapshot,
    Report,
    User,
    UserSurveyLibrary,
)
from app.prompt_version import PROMPT_VERSION
from app.qdrant_store import search_top_memories, upsert_memory_points
from app.rag.retriever import HybridProductRetriever, retrieval_request_from_profile
from app.report_products import (
    enrich_product_picks_with_sources,
    hydrate_concrete_picks_from_candidates,
    sanitize_concrete_product_picks,
)
from app.report_integrated_profile import build_integrated_profile_for_report
from app.report_survey_overlay import (
    overlay_report_when_model_ignores_survey,
    prune_follow_up_questions_after_survey_merge,
)
from app.survey_merge import merge_survey_into_profile_snapshot
from app.survey_template import (
    SURVEY_TEMPLATE_VERSION,
    coerce_survey_answers,
    compute_report_depth,
    count_filled_optional,
    survey_answers_for_prompt,
    validate_survey_answers,
)
from app.schemas import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationPatch,
    ConversationSurveyOut,
    ConversationSurveyUpsert,
    MessageCreate,
    MessageOut,
    ReportGenerateBody,
    ReportOut,
    ReportPayload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation(
    db: Session, conv_id: int, user: User, *, active_only: bool = True
) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if active_only and conv.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


def _latest_profile_row(db: Session, conversation_id: int) -> ProfileSnapshot | None:
    return db.scalar(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.conversation_id == conversation_id)
        .order_by(ProfileSnapshot.id.desc())
        .limit(1)
    )


def _latest_profile_summary(db: Session, conversation_id: int) -> str:
    prof = _latest_profile_row(db, conversation_id)
    return prof.summary_text if prof else ""


def _latest_profile_structured(db: Session, conversation_id: int) -> dict | None:
    prof = _latest_profile_row(db, conversation_id)
    if prof is None or not prof.structured_json:
        return None
    if isinstance(prof.structured_json, dict):
        return prof.structured_json
    return None


def _get_conversation_survey_row(
    db: Session, conversation_id: int
) -> ConversationSurvey | None:
    return db.scalar(
        select(ConversationSurvey).where(
            ConversationSurvey.conversation_id == conversation_id
        )
    )


def _survey_response(
    conversation_id: int,
    row: ConversationSurvey | None,
) -> ConversationSurveyOut:
    if row is None:
        empty = coerce_survey_answers({})
        return ConversationSurveyOut(
            conversation_id=conversation_id,
            answers=empty,
            template_version=SURVEY_TEMPLATE_VERSION,
            status="draft",
            report_depth=None,
            optional_filled_count=count_filled_optional(empty),
            required_complete=False,
        )
    ans = coerce_survey_answers(
        row.answers_json if isinstance(row.answers_json, dict) else {}
    )
    req_ok = False
    depth: str | None = None
    try:
        full = validate_survey_answers(ans)
        req_ok = True
        depth = compute_report_depth(full)
        ans = full
    except ValueError:
        pass
    return ConversationSurveyOut(
        conversation_id=conversation_id,
        answers=ans,
        template_version=row.template_version or SURVEY_TEMPLATE_VERSION,
        status=row.status or "draft",
        report_depth=depth,
        optional_filled_count=count_filled_optional(ans),
        required_complete=req_ok,
    )


def _merge_key_memories(
    db: Session,
    user: User,
    conversation_id: int,
    summary_text: str,
    message_hint: str = "",
) -> list[str]:
    prof = _latest_profile_row(db, conversation_id)
    km: list[str] = []
    if prof and isinstance(prof.structured_json, dict):
        raw = prof.structured_json.get("key_memories")
        if isinstance(raw, list):
            km.extend(str(x).strip() for x in raw if str(x).strip())
    qn = "\n".join(
        x for x in ((summary_text or "").strip(), (message_hint or "").strip()) if x
    ).strip()
    if qn:
        try:
            vec = get_embedding_service().embed_texts([qn[:800]])[0]
            for t in search_top_memories(
                user.id,
                vec,
                limit=get_settings().chat_qdrant_memory_search_limit,
                conversation_id=conversation_id,
            ):
                if t and t not in km:
                    km.append(t)
        except Exception:
            logger.exception(
                "key_memory_qdrant_failed user_id=%s conversation_id=%s",
                user.id,
                conversation_id,
            )
    cap = get_settings().chat_key_memories_merge_cap
    out: list[str] = []
    for x in km:
        if x not in out:
            out.append(x)
        if len(out) >= cap:
            break
    return out


def _looks_like_product_intent(text: str) -> bool:
    return bool(re.search(r"(产品|推荐|保单|链接|官网|医疗|重疾|人寿|储蓄|年金)", text))


def get_llm_dep() -> LLMService:
    return get_llm_service()


def _clamp_rolling_after_truncate(
    conv: Conversation,
    msgs_after: list[Message],
    settings,
) -> None:
    k = settings.chat_history_max_messages
    ln = len(msgs_after)
    if ln <= k:
        conv.rolling_folded_message_count = 0
        conv.rolling_summary = ""
        return
    fold_upto = ln - k
    folded = min(int(conv.rolling_folded_message_count or 0), fold_upto)
    conv.rolling_folded_message_count = folded


def _delete_profile_snapshots_from_turn(
    db: Session, conversation_id: int, anchor: datetime
) -> None:
    keeper_id = db.scalar(
        select(func.max(ProfileSnapshot.id)).where(
            ProfileSnapshot.conversation_id == conversation_id,
            ProfileSnapshot.updated_at < anchor,
        )
    )
    if keeper_id is None:
        db.execute(
            delete(ProfileSnapshot).where(
                ProfileSnapshot.conversation_id == conversation_id
            )
        )
    else:
        db.execute(
            delete(ProfileSnapshot).where(
                ProfileSnapshot.conversation_id == conversation_id,
                ProfileSnapshot.id > keeper_id,
            )
        )


def _complete_chat_turn(
    db: Session,
    conv: Conversation,
    user: User,
    llm: LLMService,
    user_msg: Message,
    locale: str | None = None,
) -> list[MessageOut]:
    """Run assistant reply + optional profile/memory/rolling fold after a user row exists."""
    settings = get_settings()
    loc = normalize_locale(locale)
    text = user_msg.content.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty message")

    user_turn_count = db.scalar(
        select(func.count(Message.id)).where(
            Message.conversation_id == conv.id,
            Message.role == "user",
        )
    )
    structured_before = _latest_profile_structured(db, conv.id)
    run_profile = user_turn_count > 0 and (
        user_turn_count % settings.profile_refresh_every_n_user_turns == 0
        or structured_before is None
    )

    msgs = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.asc())
    ).all()
    history = []
    k_window = settings.chat_history_max_messages
    for m in msgs[-k_window:]:
        if m.role not in ("user", "assistant"):
            continue
        content = (
            assistant_content_for_llm(m.content)
            if m.role == "assistant"
            else m.content
        )
        history.append({"role": m.role, "content": content})
    profile_before = _latest_profile_summary(db, conv.id)
    structured = structured_before
    inject_max = get_settings().chat_key_memories_inject_max
    key_memories_for_llm = _merge_key_memories(
        db, user, conv.id, profile_before, text
    )[:inject_max]
    retrieval_context = ""
    if _looks_like_product_intent(text):
        try:
            req = retrieval_request_from_profile(
                profile_before,
                structured,
                f"user: {text}",
            )
            cands = HybridProductRetriever(get_embedding_service()).retrieve(req, limit=3)
            if cands:
                lines = [
                    f"- {c.name}（ID:{c.product_id}，类别:{c.category}，来源:{c.source_url or '未提供'}）"
                    for c in cands
                ]
                retrieval_context = (
                    "以下摘录来自中国人寿海外产品知识库的检索命中（仅限下列条目；"
                    "答覆中仅可引用所列 product_id 与所示官方来源，不得编造，亦不得以全港开放式经纪口吻延伸推荐他司产品）：\n"
                    + "\n".join(lines)
                )
        except Exception:
            logger.exception("chat_retrieval_context_failed conversation_id=%s", conv.id)

    t0 = time.perf_counter()
    try:
        out = run_conversation_turn(
            {
                "conversation_id": conv.id,
                "user_id": user.id,
                "user_message": text,
                "messages_history": history,
                "profile_summary": profile_before,
                "profile_structured": structured,
                "key_memories": key_memories_for_llm,
                "retrieval_context": retrieval_context,
                "run_profile_architect": run_profile,
                "rolling_summary": conv.rolling_summary or "",
                "locale": loc,
            },
            llm,
        )
    except Exception:
        logger.exception(
            "chat_runner_invoke_failed conversation_id=%s user_id=%s prompt_version=%s",
            conv.id,
            user.id,
            PROMPT_VERSION,
        )
        out = {
            "assistant_reply": assistant_pipeline_failure_reply(loc),
            "profile_refresh_done": False,
        }
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "chat_turn_done conversation_id=%s user_id=%s ms=%s run_profile=%s prompt_version=%s",
        conv.id,
        user.id,
        elapsed_ms,
        run_profile,
        PROMPT_VERSION,
    )

    assistant_text = finalize_chat_assistant_text(
        str(out.get("assistant_reply") or "").strip(),
        locale=loc,
    )
    if not assistant_text.strip():
        assistant_text = assistant_pipeline_failure_reply(loc)

    asst_msg = Message(
        conversation_id=conv.id, role="assistant", content=assistant_text
    )
    db.add(asst_msg)

    if out.get("profile_refresh_done"):
        summary_new = str(out.get("profile_summary_new") or "").strip()
        blob = out.get("profile_structured_blob")
        if isinstance(blob, dict) and summary_new:
            row = ProfileSnapshot(
                user_id=user.id,
                conversation_id=conv.id,
                summary_text=summary_new,
                structured_json=blob,
            )
            db.add(row)
            kms = out.get("key_memories_new") or []
            if isinstance(kms, list) and kms:
                texts = [str(x).strip() for x in kms if str(x).strip()]
                try:
                    emb = get_embedding_service()
                    vecs = emb.embed_texts(texts)
                    upsert_memory_points(user.id, conv.id, texts, vecs)
                except Exception:
                    logger.exception(
                        "memory_upsert_failed conversation_id=%s", conv.id
                    )

        if len(msgs) > k_window:
            fold_upto = len(msgs) - k_window
            folded = int(conv.rolling_folded_message_count or 0)
            if fold_upto > folded:
                fold_slice = msgs[folded:fold_upto]
                lines: list[str] = []
                for m in fold_slice:
                    if m.role not in ("user", "assistant"):
                        continue
                    c = (
                        assistant_content_for_llm(m.content)
                        if m.role == "assistant"
                        else m.content
                    )
                    lines.append(f"{m.role}: {c}")
                transcript = "\n".join(lines)
                conv.rolling_summary = merge_rolling_conversation_summary(
                    llm, conv.rolling_summary or "", transcript
                )[:16000]
                conv.rolling_folded_message_count = fold_upto

    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asst_msg)

    return [MessageOut.model_validate(user_msg), MessageOut.model_validate(asst_msg)]


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    rows = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.deleted_at.is_(None))
        .order_by(
            desc(Conversation.is_pinned),
            nullslast(desc(Conversation.pinned_at)),
            desc(Conversation.updated_at),
        )
    ).all()
    return list(rows)


@router.post("", response_model=ConversationOut)
def create_conversation(
    body: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    title = (body.title or "新会话").strip() or "新会话"
    conv = Conversation(user_id=user.id, title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.patch("/{conversation_id}", response_model=ConversationOut)
def patch_conversation(
    conversation_id: int,
    body: ConversationPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    if body.is_pinned is not None:
        conv.is_pinned = body.is_pinned
        conv.pinned_at = datetime.utcnow() if body.is_pinned else None
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)
    return conv


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    conv.deleted_at = datetime.utcnow()
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationDetailOut:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    msgs = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.asc())
    ).all()
    summary = _latest_profile_summary(db, conv.id)
    structured = _latest_profile_structured(db, conv.id)
    kms = _merge_key_memories(db, user, conv.id, summary)
    return ConversationDetailOut(
        id=conv.id,
        title=conv.title,
        status=conv.status,
        is_pinned=conv.is_pinned,
        pinned_at=conv.pinned_at,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[MessageOut.model_validate(m) for m in msgs],
        profile_summary=summary,
        profile_structured=structured,
        key_memories=kms,
    )


@router.post("/{conversation_id}/messages", response_model=list[MessageOut])
def post_message(
    conversation_id: int,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm: LLMService = Depends(get_llm_dep),
) -> list[MessageOut]:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    text = body.content.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty message")

    user_msg = Message(conversation_id=conv.id, role="user", content=text)
    db.add(user_msg)
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user_msg)

    return _complete_chat_turn(db, conv, user, llm, user_msg, locale=body.locale)


@router.patch(
    "/{conversation_id}/messages/{message_id}",
    response_model=list[MessageOut],
)
def patch_user_message(
    conversation_id: int,
    message_id: int,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm: LLMService = Depends(get_llm_dep),
) -> list[MessageOut]:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    user_msg = db.get(Message, message_id)
    if user_msg is None or user_msg.conversation_id != conv.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")
    if user_msg.role != "user":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Only user messages can be edited",
        )
    text = body.content.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty message")

    anchor = user_msg.created_at
    db.execute(
        delete(Message).where(
            Message.conversation_id == conv.id,
            Message.id > user_msg.id,
        )
    )
    _delete_profile_snapshots_from_turn(db, conv.id, anchor)
    user_msg.content = text
    conv.updated_at = datetime.utcnow()

    settings = get_settings()
    msgs_after = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.asc())
    ).all()
    _clamp_rolling_after_truncate(conv, msgs_after, settings)

    db.commit()
    db.refresh(user_msg)

    return _complete_chat_turn(db, conv, user, llm, user_msg, locale=body.locale)


@router.get("/{conversation_id}/survey", response_model=ConversationSurveyOut)
def get_conversation_survey(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationSurveyOut:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    row = _get_conversation_survey_row(db, conv.id)
    return _survey_response(conv.id, row)


@router.put("/{conversation_id}/survey", response_model=ConversationSurveyOut)
def put_conversation_survey(
    conversation_id: int,
    body: ConversationSurveyUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationSurveyOut:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    coerced = coerce_survey_answers(body.answers)
    if body.merge_to_profile:
        try:
            validated = validate_survey_answers(coerced)
        except ValueError as e:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e
        merge_survey_into_profile_snapshot(
            db,
            user_id=user.id,
            conversation_id=conv.id,
            answers=validated,
        )

    if body.sync_to_user_library:
        lib = db.get(UserSurveyLibrary, user.id)
        if lib is None:
            lib = UserSurveyLibrary(
                user_id=user.id,
                answers_json=coerced,
                template_version=SURVEY_TEMPLATE_VERSION,
            )
            db.add(lib)
        else:
            lib.answers_json = coerced
            lib.template_version = SURVEY_TEMPLATE_VERSION

    row = _get_conversation_survey_row(db, conv.id)
    if row is None:
        row = ConversationSurvey(
            conversation_id=conv.id,
            user_id=user.id,
            answers_json=coerced,
            template_version=SURVEY_TEMPLATE_VERSION,
            status=body.status,
        )
        db.add(row)
    else:
        row.answers_json = coerced
        row.template_version = SURVEY_TEMPLATE_VERSION
        row.status = body.status
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _survey_response(conv.id, row)


@router.delete(
    "/{conversation_id}/survey",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_conversation_survey(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    row = _get_conversation_survey_row(db, conv.id)
    if row is not None:
        db.delete(row)
        conv.updated_at = datetime.utcnow()
        db.commit()


@router.post(
    "/{conversation_id}/survey/pull-from-library",
    response_model=ConversationSurveyOut,
)
def pull_conversation_survey_from_library(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationSurveyOut:
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    lib = db.get(UserSurveyLibrary, user.id)
    if lib is None or not isinstance(lib.answers_json, dict):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="User survey library empty",
        )
    coerced = coerce_survey_answers(lib.answers_json)
    row = _get_conversation_survey_row(db, conv.id)
    if row is None:
        row = ConversationSurvey(
            conversation_id=conv.id,
            user_id=user.id,
            answers_json=coerced,
            template_version=lib.template_version or SURVEY_TEMPLATE_VERSION,
            status="draft",
        )
        db.add(row)
    else:
        row.answers_json = coerced
        row.template_version = lib.template_version or SURVEY_TEMPLATE_VERSION
        row.status = "draft"
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _survey_response(conv.id, row)


@router.post("/{conversation_id}/reports/generate", response_model=ReportOut)
def generate_report(
    conversation_id: int,
    body: ReportGenerateBody = Body(default_factory=ReportGenerateBody),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm: LLMService = Depends(get_llm_dep),
) -> ReportOut:
    loc = normalize_locale(body.locale)
    conv = _get_conversation(db, conversation_id, user, active_only=True)
    msgs = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.id.asc())
    ).all()
    if len(msgs) < 2:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Need more conversation before generating a report",
        )
    transcript = "\n".join(f"{m.role}: {m.content}" for m in msgs)
    srow = _get_conversation_survey_row(db, conv.id)
    if srow is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请先在报告中填写并保存补充调查表（必填项完整）后再生成报告。",
        )
    try:
        survey_answers = validate_survey_answers(
            srow.answers_json if isinstance(srow.answers_json, dict) else {}
        )
    except ValueError as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    report_depth = compute_report_depth(survey_answers)
    survey_block = survey_answers_for_prompt(survey_answers)

    prof = _latest_profile_row(db, conv.id)
    raw_summary = ((prof.summary_text if prof else "") or "").strip()
    structured_base = (
        prof.structured_json if prof and isinstance(prof.structured_json, dict) else None
    )

    profile, structured, fuse_mode = build_integrated_profile_for_report(
        llm,
        conversation_profile_summary=raw_summary,
        conversation_structured=structured_base,
        survey_answers=survey_answers,
        survey_block=survey_block,
        locale=loc,
    )

    retriever = HybridProductRetriever(get_embedding_service())
    rg = build_report_graph(llm, retriever)
    t0 = time.perf_counter()
    try:
        rout = rg.invoke(
            {
                "conversation_id": conv.id,
                "transcript": transcript,
                "profile_summary": profile,
                "profile_structured": structured,
                "survey_supplement": survey_block,
                "report_depth": report_depth,
                "survey_optional_filled": count_filled_optional(survey_answers),
                "locale": loc,
            }
        )
    except Exception:
        logger.exception(
            "report_graph_invoke_failed conversation_id=%s prompt_version=%s",
            conv.id,
            PROMPT_VERSION,
        )
        payload = report_fallback(loc)
        rout = {
            "retrieval_query": {},
            "candidates": [],
            "report_payload_dict": payload.model_dump(),
            "trace_rationale": "graph_invoke_failed_fallback",
        }
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "report_done conversation_id=%s ms=%s prompt_version=%s",
        conv.id,
        elapsed_ms,
        PROMPT_VERSION,
    )

    candidates = rout.get("candidates") or []
    allowed_ids = {str(c.get("product_id")) for c in candidates if c.get("product_id")}
    try:
        payload = ReportPayload.model_validate(rout.get("report_payload_dict") or {})
    except Exception:
        payload = report_fallback(loc)

    if not candidates:
        notice = payload.limited_data_notice + (
            "（检索候选不足，报告仅以类别与框架描述，不包含具体产品引用。）"
        )
        payload = payload.model_copy(
            update={"concrete_product_picks": [], "limited_data_notice": notice}
        )
    else:
        payload = sanitize_concrete_product_picks(payload, allowed_ids)
        payload = enrich_product_picks_with_sources(
            payload,
            {str(c.get("product_id")): c for c in candidates if c.get("product_id")},
        )
        payload = hydrate_concrete_picks_from_candidates(payload, candidates)

    payload = overlay_report_when_model_ignores_survey(payload, survey_answers)
    settings_rf = get_settings()
    if settings_rf.report_follow_up_mode == "prune":
        payload = prune_follow_up_questions_after_survey_merge(
            payload, survey_answers, structured
        )
    else:
        payload = payload.model_copy(update={"follow_up_questions": []})

    disc = merge_report_disclaimer(payload.disclaimer, locale=loc)
    payload_dict = payload.model_dump()
    payload_dict["disclaimer"] = disc

    rep = Report(
        conversation_id=conv.id,
        title=payload.title or "配置说明",
        body_json=json.dumps(payload_dict, ensure_ascii=False),
        charts_json=json.dumps([c for c in payload_dict.get("charts") or []], ensure_ascii=False),
        disclaimer_text=disc,
    )
    db.add(rep)
    conv.updated_at = datetime.utcnow()
    db.flush()

    trace = ProductRecommendationTrace(
        conversation_id=conv.id,
        report_id=rep.id,
        query_json=json.dumps(rout.get("retrieval_query") or {}, ensure_ascii=False),
        candidates_json=json.dumps(candidates, ensure_ascii=False),
        final_choice_json=json.dumps(
            [p.model_dump() for p in payload.concrete_product_picks],
            ensure_ascii=False,
        ),
        rationale_text=(
            str(rout.get("trace_rationale") or "")
            + f"|profile_fuse={fuse_mode}|report_depth={report_depth}|survey_v={SURVEY_TEMPLATE_VERSION}"
        ),
    )
    db.add(trace)
    db.commit()
    db.refresh(rep)

    body = ReportPayload.model_validate(payload_dict)
    return ReportOut(
        id=rep.id,
        conversation_id=rep.conversation_id,
        title=rep.title,
        body=body,
        disclaimer_text=rep.disclaimer_text,
        created_at=rep.created_at,
    )


@router.get("/{conversation_id}/reports/latest", response_model=ReportOut)
def latest_report(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportOut:
    _get_conversation(db, conversation_id, user, active_only=True)
    rep = db.scalar(
        select(Report)
        .where(Report.conversation_id == conversation_id)
        .order_by(Report.id.desc())
        .limit(1)
    )
    if rep is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Report not found")
    raw_body = json.loads(rep.body_json)
    body = ReportPayload.model_validate(raw_body)
    return ReportOut(
        id=rep.id,
        conversation_id=rep.conversation_id,
        title=rep.title,
        body=body,
        disclaimer_text=rep.disclaimer_text,
        created_at=rep.created_at,
    )
