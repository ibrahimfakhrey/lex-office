"""Firebase Cloud Messaging service — sends push notifications to user devices.

Initialized lazily; no-op if FIREBASE_SERVICE_ACCOUNT_PATH is unset (dev environments).
"""
import os
import logging
from typing import Iterable, Optional

from flask import current_app
from app.extensions import db
from app.models.device_token import DeviceToken

log = logging.getLogger(__name__)

_initialized = False
_messaging = None


def _init_firebase() -> bool:
    """Lazy init. Returns True if Firebase is usable, False otherwise."""
    global _initialized, _messaging
    if _initialized:
        return _messaging is not None
    _initialized = True

    cred_path = (
        current_app.config.get('FIREBASE_SERVICE_ACCOUNT_PATH')
        or os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
    )
    if not cred_path or not os.path.exists(cred_path):
        log.info('FCM disabled: FIREBASE_SERVICE_ACCOUNT_PATH not set or file missing.')
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging as fb_messaging
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        _messaging = fb_messaging
        log.info('FCM initialized successfully.')
        return True
    except Exception as e:
        log.warning('FCM init failed: %s', e)
        _messaging = None
        return False


def send_push(
    user_id: int,
    title: str,
    body: Optional[str] = None,
    *,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
    route: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> int:
    """Push a notification to all of `user_id`'s registered devices.

    Returns the number of successful sends. Silently no-ops if Firebase is not
    initialized (e.g., dev environments without service account configured).
    Cleans up invalid tokens automatically.
    """
    tokens_q = DeviceToken.query.filter_by(user_id=user_id).all()
    if not tokens_q:
        return 0

    fcm_ready = _init_firebase()

    # Build data payload — values must be strings for FCM
    data = {'type': related_type or '', 'route': route or ''}
    if related_id is not None:
        data['id'] = str(related_id)
    if extra_data:
        for k, v in extra_data.items():
            data[str(k)] = str(v) if v is not None else ''

    success_count = 0
    invalid_tokens = []

    for dt in tokens_q:
        sent = False

        # 1) Try FCM first (works for Android + iOS where Google isn't blocked)
        if fcm_ready and dt.fcm_token:
            try:
                message = _messaging.Message(
                    token=dt.fcm_token,
                    notification=_messaging.Notification(
                        title=title,
                        body=body or '',
                    ),
                    data=data,
                    android=_messaging.AndroidConfig(
                        priority='high',
                        notification=_messaging.AndroidNotification(
                            channel_id='lexoffice_default',
                            sound='default',
                        ),
                    ),
                    apns=_messaging.APNSConfig(
                        headers={'apns-priority': '10'},
                        payload=_messaging.APNSPayload(
                            aps=_messaging.Aps(sound='default', content_available=True),
                        ),
                    ),
                )
                _messaging.send(message)
                success_count += 1
                sent = True
            except Exception as e:
                err_str = str(e).lower()
                if any(s in err_str for s in (
                    'unregistered', 'invalid-registration-token',
                    'mismatched-credential', 'sender-id-mismatch',
                    'invalid-argument',
                )):
                    # FCM token is dead — clear it; APNs may still work
                    log.info('FCM: clearing stale token id=%s reason=%s', dt.id, e)
                    dt.fcm_token = None
                else:
                    log.warning('FCM send failed (token id=%s): %s', dt.id, e)

        # 2) Fallback to direct APNs for iOS if FCM didn't deliver
        if not sent and dt.platform == 'ios' and dt.apns_token:
            try:
                from app.services.apns_service import send_apns, is_configured
                if is_configured():
                    ok, err = send_apns(
                        dt.apns_token, title, body, data=data,
                    )
                    if ok:
                        success_count += 1
                        sent = True
                        log.info('APNs direct: ✓ delivered (token id=%s)', dt.id)
                    else:
                        log.warning('APNs direct failed (id=%s): %s', dt.id, err)
                        # Clean up dead APNs tokens
                        if err and any(s in err.lower() for s in (
                            'unregistered', 'baddevicetoken', '410', 'devicetokennotforapps',
                        )):
                            invalid_tokens.append(dt.id)
            except Exception as e:
                log.warning('APNs direct exception (id=%s): %s', dt.id, e)

        # 3) If neither worked and no usable token left → mark for cleanup
        if not sent and not dt.fcm_token and not dt.apns_token:
            invalid_tokens.append(dt.id)

    # Clean stale tokens
    if invalid_tokens:
        try:
            DeviceToken.query.filter(DeviceToken.id.in_(invalid_tokens)).delete(
                synchronize_session=False
            )
            db.session.commit()
        except Exception as e:
            log.warning('Failed to clean stale tokens: %s', e)
            db.session.rollback()
    else:
        # commit any fcm_token-cleared changes
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return success_count


def send_push_to_users(
    user_ids: Iterable[int],
    title: str,
    body: Optional[str] = None,
    **kwargs,
) -> int:
    """Convenience: push to multiple users. Returns total successful sends."""
    total = 0
    for uid in user_ids:
        total += send_push(uid, title, body, **kwargs)
    return total
