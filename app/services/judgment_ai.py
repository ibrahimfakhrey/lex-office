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

Why we use tool-use (not `messages.parse`): Anthropic's constrained-grammar
compiler intermittently times out on multi-page vision requests ("Grammar
compilation timed out"). We use a regular tool (no `strict: true`) — Claude
returns its result as the tool's `input` dict, pre-parsed JSON, no fragile
text-extraction step. Pydantic validates on our side.

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
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None


# Short field descriptions only — Anthropic's structured-outputs grammar
# compiler can time out when descriptions are long, especially with Arabic
# multi-byte text. Detailed instructions live in the system prompt.
class JudgmentAnalysis(BaseModel):
    court_name: Optional[str] = None
    judgment_date: Optional[str] = None       # YYYY-MM-DD
    judgment_type: Optional[str] = None       # primary | appeal | cassation | constitutional
    result: Optional[str] = None              # full_win | partial_win | loss | postponement | procedural | absence
    judge_name: Optional[str] = None
    case_number: Optional[str] = None
    awarded_amount: Optional[float] = None
    parties: Optional[JudgmentParties] = None
    full_text_ar: Optional[str] = None        # entire verbatim ruling
    dispositive_ar: Optional[str] = None      # operative ruling only
    summary_ar: str                           # 2-4 sentence summary
    key_points_ar: List[str] = Field(default_factory=list)


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
   ملحوظة: قضايا الأحوال الشخصية والطلاق وغيرها لا تتضمن مبلغاً مالياً عادةً — اتركه null.
7. full_text_ar (النص الكامل): انسخ النص الكامل للحكم حرفياً كما يظهر في \
الوثيقة، بكل فقراته (الديباجة، الوقائع، الأسباب، المنطوق). لا تختصر ولا تحذف \
أي فقرة. حافظ على الترقيم والتنسيق ما أمكن. هذا هو ما سيُحفظ في حقل "نص الحكم / \
المنطوق" الذي يراه المحامي.
8. dispositive_ar (منطوق الحكم): انسخ النص الحرفي للجزء الذي تنطق به المحكمة \
فقط ("حكمت المحكمة بـ..." أو "قضت المحكمة بـ..."). حقل مستقل يُستخدم \
للبحث والفهرسة. اتركه null إن لم يظهر بوضوح.
9. summary_ar: ملخص في 2 إلى 4 جمل واضحة. ركّز على ما حُكم به ولماذا.
10. key_points_ar: من 3 إلى 5 نقاط أساسية. كل نقطة جملة قصيرة.

تذكّر: المحامي سيراجع كل حقل ويصححه. هدفك أن توفّر عليه الكتابة، وليس أن تتظاهر بالمعرفة. \
الـ null في حقل غير واضح أفضل من قيمة خاطئة.

استخدم أداة save_judgment_analysis لإرسال النتيجة. لا تجب بنص حر — \
استدع الأداة فقط بالحقول المطلوبة."""


# Tool schema — used in place of structured outputs to avoid the grammar
# timeout issue. NOT marked strict, so Claude's output isn't constrained
# at decode time; we validate with Pydantic on our side.
_ANALYSIS_TOOL = {
    'name': 'save_judgment_analysis',
    'description': 'حفظ التحليل المنظم للحكم القضائي.',
    'input_schema': {
        'type': 'object',
        'properties': {
            'court_name':     {'type': ['string', 'null']},
            'judgment_date':  {'type': ['string', 'null']},
            'judgment_type':  {'type': ['string', 'null']},
            'result':         {'type': ['string', 'null']},
            'judge_name':     {'type': ['string', 'null']},
            'case_number':    {'type': ['string', 'null']},
            'awarded_amount': {'type': ['number', 'null']},
            'parties': {
                'type': ['object', 'null'],
                'properties': {
                    'plaintiff': {'type': ['string', 'null']},
                    'defendant': {'type': ['string', 'null']},
                },
            },
            'full_text_ar':   {'type': ['string', 'null']},
            'dispositive_ar': {'type': ['string', 'null']},
            'summary_ar':     {'type': 'string'},
            'key_points_ar':  {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['summary_ar'],
    },
}


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

    Uses Anthropic's tool-use API: defines `save_judgment_analysis` as a
    forced tool and reads the result from response.content's tool_use block.
    The block's `input` is pre-parsed JSON — no fragile text extraction.

    Records both successes and failures into ai_usage. Quota check is done
    by the public callers BEFORE this runs.
    """
    import anthropic
    from pydantic import ValidationError
    from app.services import ai_usage

    client = _client()

    response = None
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            messages=messages,
            tools=[_ANALYSIS_TOOL],
            tool_choice={'type': 'tool', 'name': _ANALYSIS_TOOL['name']},
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

    # Find the tool_use block — Claude was forced to call our tool, so
    # this should always be present on success.
    payload = None
    for block in (response.content or []):
        if getattr(block, 'type', None) == 'tool_use' \
                and getattr(block, 'name', '') == _ANALYSIS_TOOL['name']:
            payload = block.input
            break

    if not isinstance(payload, dict):
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=response, success=False,
                            error=f'no_tool_use_in_response stop={response.stop_reason}')
        logger.warning('Claude returned no tool_use block (stop=%s)',
                       response.stop_reason)
        raise AnalysisError(
            'فشل التحليل التلقائي — يرجى إدخال البيانات يدوياً'
        )

    try:
        analysis = JudgmentAnalysis.model_validate(payload)
    except ValidationError as e:
        # Be lenient: the only required field is summary_ar. If it's
        # missing/blank, synthesize an empty one so the lawyer at least
        # sees whatever else Claude produced.
        if not payload.get('summary_ar'):
            payload['summary_ar'] = ''
        try:
            analysis = JudgmentAnalysis.model_validate(payload)
        except ValidationError:
            if tenant is not None:
                ai_usage.record(tenant, user, feature='judgment_extract',
                                model=model, response=response, success=False,
                                error=f'pydantic_validation: {e!s}'[:500])
            logger.warning('Tool input failed Pydantic validation: %s', e)
            raise AnalysisError(
                'فشل التحليل التلقائي — يرجى إدخال البيانات يدوياً'
            )

    # Record the successful call. Quota is enforced on success counts, so
    # this is what burns the tenant's monthly cap.
    if tenant is not None:
        ai_usage.record(tenant, user, feature='judgment_extract',
                        model=model, response=response, success=True)

    return analysis


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

    # Same reasoning as the vision path: full_text_ar can be long.
    return _parse_with_governance(
        model=model, messages=messages, max_tokens=12000,
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

    # Vision returns full transcribed text in `full_text_ar` (verbatim, no
    # summarization) — that's what populates the "نص الحكم / المنطوق" field
    # on the form. A 1-page Arabic judgment is typically 1.5-3K output
    # tokens; multi-page can hit 8-10K. Headroom only costs when used.
    return _parse_with_governance(
        model=model, messages=messages, max_tokens=12000,
        tenant=tenant, user=user,
    )
