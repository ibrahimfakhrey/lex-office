"""Direct APNs HTTP/2 sender — used as fallback when FCM is blocked on the device.

Sends a push directly to Apple's `api.push.apple.com` using a JWT signed with
the team's APNs auth key (.p8). No Google contact required, so this works
even when the device's network blocks Firebase.

Configuration via env:
    APNS_AUTH_KEY_PATH   = /etc/lexoffice/AuthKey_L2TU4GBD8A.p8
    APNS_KEY_ID          = L2TU4GBD8A
    APNS_TEAM_ID         = 52D8TDFTXN
    APNS_BUNDLE_ID       = com.lexoffice.lexofficeMobile
    APNS_USE_SANDBOX     = false  (true → uses api.sandbox.push.apple.com)
"""
import json
import logging
import os
import time
from typing import Optional

from flask import current_app

log = logging.getLogger(__name__)

_jwt_cache = {'token': None, 'expires_at': 0}


def _conf(key: str) -> Optional[str]:
    return current_app.config.get(key) or os.environ.get(key)


def _make_jwt() -> Optional[str]:
    """Build a JWT signed with the .p8 APNs auth key. Cached for 30 minutes."""
    now = int(time.time())
    if _jwt_cache['token'] and _jwt_cache['expires_at'] - now > 60:
        return _jwt_cache['token']

    key_path = _conf('APNS_AUTH_KEY_PATH')
    key_id = _conf('APNS_KEY_ID')
    team_id = _conf('APNS_TEAM_ID')

    if not all([key_path, key_id, team_id]):
        return None
    if not os.path.exists(key_path):
        log.warning('APNs key file not found at %s', key_path)
        return None

    try:
        import jwt as pyjwt
        with open(key_path, 'rb') as f:
            private_key = f.read()
        token = pyjwt.encode(
            {'iss': team_id, 'iat': now},
            private_key,
            algorithm='ES256',
            headers={'kid': key_id, 'alg': 'ES256'},
        )
        _jwt_cache['token'] = token
        _jwt_cache['expires_at'] = now + 1800  # 30 minutes
        return token
    except Exception as e:
        log.warning('APNs JWT build failed: %s', e)
        return None


def is_configured() -> bool:
    return bool(
        _conf('APNS_AUTH_KEY_PATH')
        and _conf('APNS_KEY_ID')
        and _conf('APNS_TEAM_ID')
        and _conf('APNS_BUNDLE_ID')
    )


def send_apns(
    apns_token: str,
    title: str,
    body: Optional[str] = None,
    *,
    data: Optional[dict] = None,
) -> tuple[bool, Optional[str]]:
    """Send one APNs push.

    Returns (success, error_message). On unrecoverable token errors
    (Unregistered, BadDeviceToken) the caller should delete the token.
    """
    if not is_configured():
        return False, 'apns_not_configured'

    jwt_token = _make_jwt()
    if not jwt_token:
        return False, 'jwt_build_failed'

    bundle_id = _conf('APNS_BUNDLE_ID')
    use_sandbox = (_conf('APNS_USE_SANDBOX') or '').lower() in ('1', 'true', 'yes')
    host = 'api.sandbox.push.apple.com' if use_sandbox else 'api.push.apple.com'
    url = f'https://{host}/3/device/{apns_token}'

    payload = {
        'aps': {
            'alert': {'title': title, 'body': body or ''},
            'sound': 'default',
            'badge': 1,
        },
    }
    if data:
        for k, v in data.items():
            payload[str(k)] = str(v) if v is not None else ''

    try:
        import httpx
        with httpx.Client(http2=True, timeout=10.0) as client:
            resp = client.post(
                url,
                headers={
                    'authorization': f'bearer {jwt_token}',
                    'apns-topic': bundle_id,
                    'apns-push-type': 'alert',
                    'apns-priority': '10',
                    'apns-expiration': '0',
                },
                content=json.dumps(payload),
            )
        if resp.status_code == 200:
            return True, None
        err_reason = ''
        try:
            err_reason = (resp.json() or {}).get('reason', '')
        except Exception:
            err_reason = resp.text[:200]
        log.warning('APNs send failed: %s — %s', resp.status_code, err_reason)
        return False, f'{resp.status_code}:{err_reason}'
    except Exception as e:
        log.warning('APNs send exception: %s', e)
        return False, str(e)
