"""Silent market detection for incoming requests.

Resolution chain (first match wins):
  1. lex_market cookie (sticky after first detection)
  2. CF-IPCountry header (if Cloudflare ever sits in front — costs nothing to support)
  3. GeoLite2 / db-ip lookup on the client IP (offline DB at instance/geo/*.mmdb)
  4. Accept-Language sniff (ar-SA / ar-EG)
  5. DEFAULT_MARKET ('eg')

The result is cached in g.market for the request and written back into the
lex_market cookie so subsequent requests skip the geo lookup entirely.

Post-signup code paths should prefer tenant.market over g.market — once a
tenant has been registered, its market is frozen.
"""
import os
from flask import current_app, g, request

from app.utils.market_config import (
    DEFAULT_MARKET, SUPPORTED_MARKETS, normalize_market,
)


COOKIE_NAME = 'lex_market'
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year

# ISO country code → market code. Anything not listed falls through to default.
_COUNTRY_TO_MARKET = {
    'EG': 'eg',
    'SA': 'sa',
}


# ── lazy GeoIP reader (cached on the app instance) ────────────────────────────

def _geoip_reader():
    """Return a cached geoip2.database.Reader or None if unavailable.

    Stored on current_app to avoid reopening the DB file on every request.
    Returns None silently if either the package or the DB file is missing —
    the caller falls through to the next detection step.
    """
    cached = current_app.extensions.get('_market_geoip_reader_attempted')
    if cached is not None:
        return cached if cached is not False else None

    db_path = os.path.join(
        current_app.root_path, '..', 'instance', 'geo', 'dbip-country-lite.mmdb'
    )
    db_path = os.path.normpath(db_path)
    if not os.path.exists(db_path):
        current_app.extensions['_market_geoip_reader_attempted'] = False
        return None

    try:
        import geoip2.database  # type: ignore
        reader = geoip2.database.Reader(db_path)
        current_app.extensions['_market_geoip_reader_attempted'] = reader
        return reader
    except Exception:
        current_app.extensions['_market_geoip_reader_attempted'] = False
        return None


def _country_from_ip(ip):
    if not ip:
        return None
    reader = _geoip_reader()
    if reader is None:
        return None
    try:
        resp = reader.country(ip)
        return (resp.country.iso_code or '').upper() or None
    except Exception:
        return None


def _client_ip():
    """Best-effort real client IP (works whether or not a proxy is in front)."""
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 — take the leftmost.
        return xff.split(',')[0].strip()
    cf = request.headers.get('CF-Connecting-IP')
    if cf:
        return cf.strip()
    return request.remote_addr


# ── detection ────────────────────────────────────────────────────────────────

def detect_market():
    """Resolve the market for the current request. Returns one of SUPPORTED_MARKETS."""
    # 1. cookie
    cookie_val = request.cookies.get(COOKIE_NAME)
    if cookie_val and cookie_val.lower() in SUPPORTED_MARKETS:
        return cookie_val.lower()

    # 2. Cloudflare header (free if CF is ever proxied in front)
    cf_country = (request.headers.get('CF-IPCountry') or '').upper()
    if cf_country in _COUNTRY_TO_MARKET:
        return _COUNTRY_TO_MARKET[cf_country]

    # 3. GeoIP DB lookup
    geo_country = _country_from_ip(_client_ip())
    if geo_country in _COUNTRY_TO_MARKET:
        return _COUNTRY_TO_MARKET[geo_country]

    # 4. Accept-Language sniff
    accept = (request.headers.get('Accept-Language') or '').lower()
    if 'ar-sa' in accept:
        return 'sa'
    if 'ar-eg' in accept:
        return 'eg'

    # 5. default
    return DEFAULT_MARKET


def install_market_hook(app):
    """Register before_request to populate g.market and after_request to
    persist the cookie. Idempotent — safe to call multiple times."""

    @app.before_request
    def _resolve_market():  # noqa: F811
        # Skip static / health endpoints to avoid useless DB lookups.
        if request.endpoint in ('static',) or request.path.startswith('/static/'):
            return
        try:
            g.market = detect_market()
        except Exception:
            g.market = DEFAULT_MARKET

    @app.after_request
    def _persist_market_cookie(response):
        market = getattr(g, 'market', None)
        if not market:
            return response
        existing = request.cookies.get(COOKIE_NAME)
        if existing == market:
            return response
        # Don't set the cookie on static/asset responses
        if request.endpoint == 'static' or request.path.startswith('/static/'):
            return response
        response.set_cookie(
            COOKIE_NAME, market,
            max_age=COOKIE_MAX_AGE,
            samesite='Lax',
            secure=app.config.get('JWT_COOKIE_SECURE', False),
            httponly=False,  # needs to be readable by JS if we ever add a switcher
            path='/',
        )
        return response


def current_market():
    """Helper for code that needs the market without importing g everywhere."""
    return normalize_market(getattr(g, 'market', DEFAULT_MARKET))
