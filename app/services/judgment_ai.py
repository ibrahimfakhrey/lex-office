"""Claude analysis of extracted judgment text — text and vision paths.

Two entry points:

  - analyze_judgment(text, tenant, user)
        Digital judgments. Uses Claude Haiku 4.5 (cheap, fast). Default path.

  - analyze_judgment_images(images, tenant, user)
        Scanned PDFs. Uses Claude Sonnet 4.6 with vision — Sonnet's Arabic
        OCR quality is materially better than Haiku's on scanned documents,
        and the per-call cost (~$0.02-0.05) is still trivial relative to
        manual data entry.

Both produce the same Pydantic-validated JudgmentAnalysis, route through the
same governance (`ai_usage.check_can_use` / `record`), and burn the same
`judgment_extract` feature key — the admin sees one combined feature, not
two.

Why no prompt caching: Haiku 4.5 needs a 4096-token prefix to cache. Our
system prompt is ~1500 tokens, so caching costs more than it saves. Sonnet
4.6 caches at 1024 tokens — worth revisiting if vision usage scales up.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional, List, Sequence

from flask import current_app
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Model used for vision OCR. Sonnet 4.6 reads Arabic significantly better
# than Haiku on scanned/photo'd docs and supports structured outputs the
# same way. Override via env var ANTHROPIC_VISION_MODEL if needed.
_DEFAULT_VISION_MODEL = 'claude-sonnet-4-6'


# ── Output schema ─────────────────────────────────────────────────────────────

class JudgmentParties(BaseModel):
    plaintiff: Optional[str] = Field(None, description='اسم المدعي / الطرف الأول')
    defendant: Optional[str] = Field(None, description='اسم المدعى عليه / الطرف الثاني')


class JudgmentAnalysis(BaseModel):
    """Structured fields extracted from an Arabic legal judgment.

    All fields nullable — the model returns null when not confident, which is
    safer than guessing. Date is ISO-8601 (YYYY-MM-DD) or null.
    """
    court_name: Optional[str] = Field(None, description='اسم المحكمة الكامل')
    judgment_date: Optional[str] = Field(
        None, description='تاريخ الحكم بصيغة YYYY-MM-DD، أو null إذا غير واضح'
    )
    judgment_type: Optional[str] = Field(
        None, description='نوع الحكم: primary | appeal | cassation | constitutional'
    )
    result: Optional[str] = Field(
        None,
        description='نتيجة الحكم: full_win | partial_win | loss | postponement '
                    '| procedural | absence',
    )
    judge_name: Optional[str] = Field(None, description='اسم القاضي/المستشار')
    case_number: Optional[str] = Field(None, description='رقم الدعوى/القضية')
    awarded_amount: Optional[float] = Field(
        None, description='المبلغ المحكوم به بالأرقام (بدون رمز عملة)'
    )
    parties: Optional[JudgmentParties] = None
    summary_ar: str = Field(
        ..., description='ملخص الحكم في 2-4 جمل عربية واضحة'
    )
    key_points_ar: List[str] = Field(
        default_factory=list,
        description='3-5 نقاط رئيسية من الحكم باللغة العربية',
    )


# ── Errors ────────────────────────────────────────────────────────────────────

class AnalysisError(Exception):
    """Top-level error surface — message is Arabic, safe for users."""


class AnalysisConfigError(AnalysisError):
    """Raised when ANTHROPIC_API_KEY is missing."""


class AnalysisRateLimitError(AnalysisError):
    pass


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """أنت مساعد قانوني متخصص في تحليل الأحكام القضائية باللغة العربية. \
ستُعطى نص حكم قضائي (من مصر أو السعودية) وعليك استخراج البيانات المنظمة منه.

قواعد صارمة:
1. أعد جميع الحقول النصية باللغة العربية الفصحى الواضحة.
2. إذا لم تكن متأكداً من قيمة حقل ما، اتركه null. لا تخمّن.
3. التاريخ يُكتب بصيغة YYYY-MM-DD (مثلاً 2026-04-15). \
حوّل التاريخ الهجري للميلادي إن أمكن، وإلا اتركه null.
4. judgment_type يجب أن يكون أحد: primary, appeal, cassation, constitutional.
   - primary: حكم ابتدائي (المحاكم العامة / محاكم الدرجة الأولى)
   - appeal: حكم استئناف
   - cassation: حكم نقض / تمييز
   - constitutional: حكم دستوري
5. result يجب أن يكون أحد: full_win, partial_win, loss, postponement, procedural, absence.
   - full_win: قبول الدعوى بالكامل / المدعي ربح كلياً
   - partial_win: قبول جزئي / ربح جزئي
   - loss: رفض الدعوى / المدعي خسر
   - postponement: تأجيل الفصل
   - procedural: حكم شكلي (عدم الاختصاص، عدم القبول شكلاً)
   - absence: حكم غيابي
6. awarded_amount: رقم فقط (بدون "ج.م" أو "ر.س"). إن كان "غير محدود" أو غير ذلك، اتركه null.
7. summary_ar: ملخص في 2 إلى 4 جمل واضحة. ركّز على ما حُكم به ولماذا.
8. key_points_ar: من 3 إلى 5 نقاط أساسية. كل نقطة جملة قصيرة.

تذكّر: المحامي سيراجع كل حقل ويصححه. هدفك أن توفّر عليه الكتابة، وليس أن تتظاهر بالمعرفة. \
الـ null في حقل غير واضح أفضل من قيمة خاطئة."""


_VISION_USER_PREFIX = (
    "هذه صور الصفحات الممسوحة ضوئياً لحكم قضائي. اقرأ النص العربي من الصور "
    "(OCR) واستخرج بياناته المنظمة وفق نفس القواعد:"
)


# ── Internals ─────────────────────────────────────────────────────────────────

def _client():
    """Lazy Anthropic client — built once per app config, validates the key."""
    from anthropic import Anthropic
    api_key = current_app.config.get('ANTHROPIC_API_KEY') or ''
    if not api_key:
        raise AnalysisConfigError(
            'مفتاح Claude غير مُعدّ — يرجى التواصل مع مدير النظام'
        )
    return Anthropic(api_key=api_key)


def _parse_with_governance(*, model: str, messages: list, max_tokens: int,
                           tenant, user) -> JudgmentAnalysis:
    """Shared call path for both text and vision routes.

    Performs the API call, handles every Anthropic exception type with the
    correct Arabic user message, records both successes and failures into
    ai_usage. Quota check is done by the public callers BEFORE this runs —
    no double-checking here.
    """
    import anthropic
    from app.services import ai_usage

    client = _client()

    response = None
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            messages=messages,
            output_format=JudgmentAnalysis,
        )
    except anthropic.AuthenticationError as e:
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=None, success=False,
                            error=f'auth: {e}')
        logger.exception('Anthropic auth failed — bad API key')
        raise AnalysisError(
            'فشل التحقق من مفتاح Claude — يرجى مراجعة إعدادات النظام'
        )
    except anthropic.RateLimitError as e:
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=None, success=False,
                            error=f'rate_limit: {e}')
        logger.warning('Anthropic rate limited')
        raise AnalysisRateLimitError(
            'تم تجاوز حد الطلبات — يرجى المحاولة بعد دقيقة'
        ) from e
    except anthropic.BadRequestError as e:
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=None, success=False,
                            error=f'bad_request: {getattr(e, "message", str(e))}')
        logger.exception('Anthropic 400: %s', getattr(e, 'message', str(e)))
        raise AnalysisError(
            'تعذّر تحليل المحتوى — قد يكون كبيراً جداً. يرجى المحاولة بنسخة مختصرة'
        )
    except anthropic.APIStatusError as e:
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=None, success=False,
                            error=f'api_error: {e}')
        logger.exception('Anthropic API error: %s', e)
        raise AnalysisError(
            'حدث خطأ في خدمة التحليل — يرجى المحاولة لاحقاً'
        )
    except anthropic.APIConnectionError as e:
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=None, success=False,
                            error=f'connection: {e}')
        logger.exception('Anthropic connection error: %s', e)
        raise AnalysisError(
            'تعذّر الاتصال بخدمة التحليل — تحقق من اتصال الإنترنت'
        )

    if response.parsed_output is None:
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=response, success=False,
                            error='parse_failure_or_refusal')
        logger.warning('Claude returned unparsed response (stop_reason=%s)',
                       response.stop_reason)
        raise AnalysisError(
            'فشل التحليل التلقائي — يرجى إدخال البيانات يدوياً'
        )

    # Record the successful call. Quota is enforced on success counts, so
    # this is what burns the tenant's monthly cap.
    if tenant is not None:
        ai_usage.record(tenant, user, feature='judgment_extract',
                        model=model, response=response, success=True)

    return response.parsed_output


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_judgment(text: str, tenant=None, user=None) -> JudgmentAnalysis:
    """Analyze digital judgment text. Returns a validated JudgmentAnalysis.

    Raises:
        AnalysisConfigError: missing API key.
        AnalysisRateLimitError: temporary 429 from Anthropic.
        AnalysisError: any other failure (with Arabic, user-safe message).
        ai_usage.QuotaError: tenant blocked by entitlement or monthly cap.
            Caller should catch and surface the message verbatim.
    """
    from app.services import ai_usage

    if not text or not text.strip():
        raise AnalysisError('النص فارغ — لا يمكن تحليله')

    if tenant is not None:
        ai_usage.check_can_use(tenant, feature_key='judgment_extract')

    model = current_app.config.get('ANTHROPIC_MODEL', 'claude-haiku-4-5')
    user_message = (
        f"حلّل الحكم التالي واستخرج بياناته المنظمة:\n\n"
        f"--- بداية نص الحكم ---\n{text}\n--- نهاية نص الحكم ---"
    )
    messages = [{"role": "user", "content": user_message}]

    return _parse_with_governance(
        model=model, messages=messages, max_tokens=2000,
        tenant=tenant, user=user,
    )


def analyze_judgment_images(
    images: Sequence[bytes], tenant=None, user=None,
) -> JudgmentAnalysis:
    """Analyze a scanned judgment via Claude vision (OCR + extraction in one call).

    `images` is an ordered sequence of PNG byte strings — one per PDF page,
    in reading order. Sent to Claude Sonnet 4.6 as base64 image blocks.
    """
    from app.services import ai_usage

    if not images:
        raise AnalysisError('لا توجد صور للتحليل')

    if tenant is not None:
        # Same feature key as text path — admins manage one feature, not two.
        ai_usage.check_can_use(tenant, feature_key='judgment_extract')

    model = current_app.config.get('ANTHROPIC_VISION_MODEL') or _DEFAULT_VISION_MODEL

    # Build the multimodal message: each page as an image block, then the
    # instruction text. Anthropic SDK accepts base64 image blocks per the
    # claude-api skill (Vision section).
    content_blocks = []
    for img_bytes in images:
        b64 = base64.standard_b64encode(img_bytes).decode('ascii')
        content_blocks.append({
            'type': 'image',
            'source': {
                'type': 'base64',
                'media_type': 'image/png',
                'data': b64,
            },
        })
    content_blocks.append({'type': 'text', 'text': _VISION_USER_PREFIX})
    messages = [{"role": "user", "content": content_blocks}]

    # Vision needs more output room — Sonnet on a multi-page judgment may
    # produce a longer summary. Headroom doesn't cost anything until used.
    return _parse_with_governance(
        model=model, messages=messages, max_tokens=4000,
        tenant=tenant, user=user,
    )
