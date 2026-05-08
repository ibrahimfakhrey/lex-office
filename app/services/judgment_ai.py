"""Claude analysis of extracted judgment text.

Uses Claude Haiku 4.5 with structured outputs (Pydantic via
`client.messages.parse()`) to extract the fields a lawyer would otherwise
type by hand on /judgments/create. The output is shape-validated by the
SDK before it reaches the caller.

Why no prompt caching: Haiku 4.5 needs a 4096-token prefix to cache. Our
system prompt is ~1500 tokens, so caching would cost more (1.25× write
premium) without giving any read benefit. If we ever switch to Sonnet 4.6
(1024-token min), revisit.
"""
from __future__ import annotations

import logging
from typing import Optional, List

from flask import current_app
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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


# ── Public API ────────────────────────────────────────────────────────────────

def _client():
    """Lazy Anthropic client — built once per app config, validates the key."""
    from anthropic import Anthropic
    api_key = current_app.config.get('ANTHROPIC_API_KEY') or ''
    if not api_key:
        raise AnalysisConfigError(
            'مفتاح Claude غير مُعدّ — يرجى التواصل مع مدير النظام'
        )
    return Anthropic(api_key=api_key)


def analyze_judgment(text: str, tenant=None, user=None) -> JudgmentAnalysis:
    """Analyze an extracted judgment text. Returns a validated JudgmentAnalysis.

    Args:
        text: extracted Arabic text from the uploaded judgment.
        tenant: required for governance (quota check + usage logging).
                Routes that don't pass it will skip enforcement — so callers
                must always pass it from inside a request context.
        user: optional, for attribution in the usage log.

    Raises:
        AnalysisConfigError: missing API key.
        AnalysisRateLimitError: temporary 429 from Anthropic.
        AnalysisError: any other failure (with Arabic, user-safe message).
        ai_usage.QuotaError: tenant blocked by entitlement or monthly cap.
            Caller should catch and surface the message verbatim.
    """
    import anthropic
    from app.services import ai_usage

    if not text or not text.strip():
        raise AnalysisError('النص فارغ — لا يمكن تحليله')

    # 1. Governance check — raises QuotaError subclasses with Arabic messages.
    # Feature key must match the one used in record() below and in the
    # KNOWN_AI_FEATURES registry.
    if tenant is not None:
        ai_usage.check_can_use(tenant, feature_key='judgment_extract')

    client = _client()
    model = current_app.config.get('ANTHROPIC_MODEL', 'claude-haiku-4-5')

    user_message = (
        f"حلّل الحكم التالي واستخرج بياناته المنظمة:\n\n"
        f"--- بداية نص الحكم ---\n{text}\n--- نهاية نص الحكم ---"
    )

    response = None
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=2000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
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
            'تعذّر تحليل النص — قد يكون طويلاً جداً. يرجى استخدام نسخة مختصرة'
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
        # Either a refusal or schema validation failure. Record as failure
        # but still don't burn the tenant's quota for this.
        if tenant is not None:
            ai_usage.record(tenant, user, feature='judgment_extract',
                            model=model, response=response, success=False,
                            error='parse_failure_or_refusal')
        logger.warning('Claude returned unparsed response (stop_reason=%s)',
                       response.stop_reason)
        raise AnalysisError(
            'فشل التحليل التلقائي — يرجى إدخال البيانات يدوياً'
        )

    # 2. Success — record usage. Quota is enforced on success counts, so this
    # is what burns the tenant's monthly cap.
    if tenant is not None:
        ai_usage.record(tenant, user, feature='judgment_extract',
                        model=model, response=response, success=True)

    return response.parsed_output
