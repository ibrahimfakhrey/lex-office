/**
 * Egyptian national ID autofill — Layer 1 (free, no OCR, no AI).
 *
 * As soon as the user enters 14 digits into the `national_id` field, decode
 * date_of_birth + governorate + gender and fill the dependent form fields.
 * Only fills fields that are currently empty so manual edits are never
 * overwritten. The decoder runs entirely in the browser.
 *
 * Wire-up: include this script after the form renders. The script binds to
 * `input[name="national_id"]` and updates `input[name="date_of_birth"]`
 * and `select[name="governorate"]`.
 */
(function () {
  'use strict';

  // Governorate codes (positions 8–9 of the 14-digit ID) → Arabic name.
  // Must stay in sync with app/utils/national_id.py and EGYPTIAN_GOVERNORATES.
  var GOVERNORATES = {
    '01': 'القاهرة', '02': 'الإسكندرية', '03': 'بورسعيد', '04': 'السويس',
    '11': 'دمياط', '12': 'الدقهلية', '13': 'الشرقية', '14': 'القليوبية',
    '15': 'كفر الشيخ', '16': 'الغربية', '17': 'المنوفية', '18': 'البحيرة',
    '19': 'الإسماعيلية', '21': 'الجيزة', '22': 'بني سويف', '23': 'الفيوم',
    '24': 'المنيا', '25': 'أسيوط', '26': 'سوهاج', '27': 'قنا',
    '28': 'أسوان', '29': 'الأقصر', '31': 'البحر الأحمر', '32': 'الوادي الجديد',
    '33': 'مطروح', '34': 'شمال سيناء', '35': 'جنوب سيناء',
    '88': 'مواليد خارج جمهورية مصر العربية'
  };

  function parse(nid) {
    var digits = String(nid || '').replace(/\D/g, '');
    if (digits.length !== 14) return null;

    var centuryDigit = digits[0];
    var centuryBase;
    if (centuryDigit === '2') centuryBase = 1900;
    else if (centuryDigit === '3') centuryBase = 2000;
    else return { valid: false, error: 'الرقم يبدأ بـ 2 أو 3 فقط' };

    var year = centuryBase + parseInt(digits.substr(1, 2), 10);
    var month = parseInt(digits.substr(3, 2), 10);
    var day = parseInt(digits.substr(5, 2), 10);
    if (month < 1 || month > 12) return { valid: false, error: 'الشهر غير صحيح' };
    if (day < 1 || day > 31) return { valid: false, error: 'اليوم غير صحيح' };
    // Constructor validates calendar days (e.g. Feb 30 → March 2).
    var dob = new Date(year, month - 1, day);
    if (dob.getFullYear() !== year || dob.getMonth() !== month - 1 || dob.getDate() !== day) {
      return { valid: false, error: 'تاريخ الميلاد غير صحيح' };
    }
    if (dob > new Date()) return { valid: false, error: 'تاريخ الميلاد في المستقبل' };

    var govCode = digits.substr(7, 2);
    var governorate = GOVERNORATES[govCode] || null;

    var genderDigit = parseInt(digits.charAt(12), 10);
    var isMale = (genderDigit % 2) === 1;

    // ISO YYYY-MM-DD (the <input type="date"> wants this format).
    var pad = function (n) { return String(n).padStart(2, '0'); };
    var iso = year + '-' + pad(month) + '-' + pad(day);

    return {
      valid: true,
      date_of_birth: iso,
      governorate: governorate,
      governorate_code: govCode,
      gender: isMale ? 'male' : 'female',
      gender_ar: isMale ? 'ذكر' : 'أنثى'
    };
  }

  function findFeedbackEl(input) {
    var el = input.parentElement && input.parentElement.querySelector('.nid-feedback');
    if (el) return el;
    el = document.createElement('div');
    el.className = 'nid-feedback small mt-1';
    if (input.parentElement) input.parentElement.appendChild(el);
    return el;
  }

  function showFeedback(input, ok, text) {
    var el = findFeedbackEl(input);
    el.textContent = text;
    el.style.color = ok ? '#0a7a4a' : '#b32424';
  }

  function clearFeedback(input) {
    var el = input.parentElement && input.parentElement.querySelector('.nid-feedback');
    if (el) el.textContent = '';
  }

  function autofill(parsed) {
    var dobInput = document.querySelector('input[name="date_of_birth"]');
    if (dobInput && !dobInput.value && parsed.date_of_birth) {
      dobInput.value = parsed.date_of_birth;
    }
    var govSelect = document.querySelector('select[name="governorate"]');
    if (govSelect && !govSelect.value && parsed.governorate) {
      // Verify the option exists before assigning, otherwise Chrome silently drops it.
      var match = Array.prototype.find.call(govSelect.options, function (o) {
        return o.value === parsed.governorate;
      });
      if (match) govSelect.value = parsed.governorate;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Image-upload extraction (Tier 1 free + Tier 2 Claude opt-in).
  // Renders an upload widget right below the national_id input.

  function csrfToken() {
    var t = document.querySelector('input[name="csrf_token"]');
    return t ? t.value : '';
  }

  function setIfEmpty(selector, value) {
    if (value == null || value === '') return;
    var el = document.querySelector(selector);
    if (!el) return;
    if (el.tagName === 'SELECT') {
      var match = Array.prototype.find.call(el.options, function (o) { return o.value === value; });
      if (match && !el.value) el.value = value;
      return;
    }
    if (!el.value) el.value = value;
  }

  function applyExtractedFields(data) {
    if (!data) return;
    setIfEmpty('input[name="national_id"]', data.national_id);
    var parsed = data.parsed || data.parsed_from_number || data;
    setIfEmpty('input[name="date_of_birth"]', parsed.date_of_birth);
    setIfEmpty('select[name="governorate"]', parsed.governorate || data.governorate);
    // Tier-2 (Claude) extra fields:
    setIfEmpty('input[name="full_name"]', data.full_name_ar);
    setIfEmpty('input[name="profession"]', data.profession);
    setIfEmpty('input[name="city"]', data.city);
    setIfEmpty('input[name="district"]', data.district);
    setIfEmpty('input[name="street"]', data.street);
    // If we got the national_id from the photo, re-run the input handler so
    // its visible feedback line updates too.
    var nidInput = document.querySelector('input[name="national_id"]');
    if (nidInput && nidInput.value) {
      nidInput.dispatchEvent(new Event('input'));
    }
  }

  function buildUploadWidget(parentEl) {
    var wrap = document.createElement('div');
    wrap.className = 'mt-2 nid-upload';

    var fileLabel = document.createElement('label');
    fileLabel.className = 'btn btn-outline-secondary btn-sm me-2';
    fileLabel.style.cursor = 'pointer';
    fileLabel.textContent = '📷 رفع صورة البطاقة';
    var fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/jpeg,image/png,image/webp';
    fileInput.style.display = 'none';
    fileLabel.appendChild(fileInput);

    var aiBtn = document.createElement('button');
    aiBtn.type = 'button';
    aiBtn.className = 'btn btn-outline-primary btn-sm';
    aiBtn.textContent = '🤖 تحليل أعمق بالذكاء الاصطناعي';
    aiBtn.style.display = 'none';
    aiBtn.title = 'يستخدم AI لاستخراج الاسم والعنوان (يحتسب من رصيد المكتب)';

    var status = document.createElement('div');
    status.className = 'small mt-1';

    wrap.appendChild(fileLabel);
    wrap.appendChild(aiBtn);
    wrap.appendChild(status);
    parentEl.appendChild(wrap);

    var lastFile = null;

    function setStatus(text, kind) {
      status.textContent = text || '';
      status.style.color = (kind === 'err') ? '#b32424' : (kind === 'ok' ? '#0a7a4a' : '#666');
    }

    function postExtract(endpoint, file) {
      var fd = new FormData();
      fd.append('image', file);
      fd.append('csrf_token', csrfToken());
      return fetch(endpoint, {
        method: 'POST',
        body: fd,
        headers: { 'X-CSRFToken': csrfToken() },
        credentials: 'same-origin',
      }).then(function (r) {
        return r.json().then(function (body) { return { ok: r.ok, body: body }; });
      });
    }

    fileInput.addEventListener('change', function () {
      var f = fileInput.files && fileInput.files[0];
      if (!f) return;
      lastFile = f;
      setStatus('جاري قراءة الصورة...', 'info');
      aiBtn.style.display = 'none';
      postExtract('/clients/extract-national-id', f).then(function (res) {
        if (res.body && res.body.success) {
          applyExtractedFields({
            national_id: res.body.national_id,
            parsed: res.body.parsed,
          });
          setStatus('✓ تم قراءة الرقم القومي من الصورة. يمكنك إكمال الباقي أو الضغط على «تحليل أعمق» لاستخراج الاسم والعنوان.', 'ok');
        } else {
          setStatus((res.body && res.body.error) || 'تعذّرت القراءة المجانية', 'err');
        }
        aiBtn.style.display = '';
      }).catch(function () {
        setStatus('تعذّر الاتصال بالخادم', 'err');
        aiBtn.style.display = '';
      });
    });

    aiBtn.addEventListener('click', function () {
      if (!lastFile) {
        setStatus('ارفع صورة البطاقة أولاً', 'err');
        return;
      }
      aiBtn.disabled = true;
      var origLabel = aiBtn.textContent;
      aiBtn.textContent = 'جارٍ التحليل...';
      setStatus('جاري إرسال الصورة للذكاء الاصطناعي...', 'info');
      postExtract('/clients/extract-national-id-ai', lastFile).then(function (res) {
        aiBtn.disabled = false;
        aiBtn.textContent = origLabel;
        if (res.body && res.body.success) {
          applyExtractedFields(res.body.data || {});
          setStatus('✓ تم استخراج البيانات بالذكاء الاصطناعي. راجعها قبل الحفظ.', 'ok');
        } else {
          setStatus((res.body && res.body.error) || 'فشل التحليل بالذكاء الاصطناعي', 'err');
        }
      }).catch(function () {
        aiBtn.disabled = false;
        aiBtn.textContent = origLabel;
        setStatus('تعذّر الاتصال بالخادم', 'err');
      });
    });
  }

  function init() {
    var input = document.querySelector('input[name="national_id"]');
    if (!input) return;

    var handler = function () {
      var raw = input.value || '';
      var digits = raw.replace(/\D/g, '');
      if (digits.length === 0) { clearFeedback(input); return; }
      if (digits.length < 14) { clearFeedback(input); return; }
      var parsed = parse(digits);
      if (!parsed) { clearFeedback(input); return; }
      if (!parsed.valid) {
        showFeedback(input, false, parsed.error || 'الرقم القومي غير صالح');
        return;
      }
      autofill(parsed);
      var bits = [];
      if (parsed.date_of_birth) bits.push('تاريخ الميلاد: ' + parsed.date_of_birth);
      if (parsed.governorate) bits.push('المحافظة: ' + parsed.governorate);
      if (parsed.gender_ar) bits.push('النوع: ' + parsed.gender_ar);
      showFeedback(input, true, '✓ ' + bits.join(' · '));
    };

    input.addEventListener('input', handler);
    // Run once on load in case the field is pre-filled (edit page).
    if (input.value) handler();

    // Add the upload widget under the national_id field (after the feedback line).
    if (input.parentElement) {
      buildUploadWidget(input.parentElement);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
