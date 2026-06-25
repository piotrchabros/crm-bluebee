"""OAuth 2.1 Authorization Server for the CRM MCP connector.

Lets OAuth-only MCP hosts (e.g. Claude.ai custom connectors, which cannot send
a static bearer token) connect to the CRM MCP server. The issued access token
is a Personal Access Token (PAT), so the MCP server validates it with the
existing PAT machinery -- no new token-validation path.

Flow: register (Dynamic Client Registration) -> authorize (CRM login via the
jwt_access cookie + explicit consent) -> token (PKCE check -> mint a PAT).
"""

import base64
import hashlib
import json
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from common.models import PersonalAccessToken, Profile

from .models import OAuthAuthCode, OAuthClient

CODE_TTL_SECONDS = 90

logger = logging.getLogger("oauth_mcp")


def _issuer(request):
    # The CRM always runs behind TLS (Caddy); the proxy SSL header isn't set,
    # so request.scheme is http -- force https for the public metadata URLs.
    return "https://%s" % request.get_host()


def _set_org_rls(org_id):
    """Set the Postgres RLS org context so org-scoped tables (Profile, the PAT
    table) are visible / writable in this request."""
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.current_org', %s, false)", [str(org_id)])


def _decode_jwt_claims(raw):
    """Return (user_id, org_id) from a SimpleJWT access token.

    Tolerates expiry: the jwt_access cookie lives a day but the access-token
    JWT expires in ~1h (the frontend refreshes it on navigation). For the
    consent screen we only need to identify the logged-in user, and the real
    authorization check is that an active Profile still exists -- so a stale
    but validly *signed* token is acceptable here. The signature is always
    verified, so the token cannot be forged.
    """
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        tok = AccessToken(raw)
        return tok["user_id"], tok.get("org_id")
    except TokenError:
        pass  # expired / failed lifetime check -- verify signature only below

    import jwt as pyjwt
    from django.conf import settings as dj_settings
    from rest_framework_simplejwt.settings import api_settings as jwt_settings

    key = jwt_settings.VERIFYING_KEY or jwt_settings.SIGNING_KEY or dj_settings.SECRET_KEY
    payload = pyjwt.decode(
        raw,
        key,
        algorithms=[jwt_settings.ALGORITHM],
        options={"verify_exp": False, "verify_aud": False},
    )
    return payload.get("user_id"), payload.get("org_id")


def _profile_from_session(request):
    """Resolve the logged-in CRM user from the jwt_access cookie.

    The browser carries the frontend's jwt_access cookie (not an Authorization
    header), so we decode it here. Returns a Profile or None.
    """
    raw = request.COOKIES.get("jwt_access")
    if not raw:
        logger.warning("oauth authorize: no jwt_access cookie on the request")
        return None
    try:
        user_id, org_id = _decode_jwt_claims(raw)
    except Exception as exc:
        logger.warning("oauth authorize: jwt decode failed: %s", exc)
        return None
    if not org_id:
        logger.warning("oauth authorize: token has no org_id (user_id=%s)", user_id)
        return None
    _set_org_rls(org_id)
    try:
        return Profile.objects.select_related("org", "user").get(
            user_id=user_id, org_id=org_id, is_active=True
        )
    except Profile.DoesNotExist:
        logger.warning(
            "oauth authorize: no active profile for user_id=%s org_id=%s", user_id, org_id
        )
        return None


# --------------------------------------------------------------------------- #
# Discovery metadata
# --------------------------------------------------------------------------- #

@require_http_methods(["GET"])
def protected_resource_metadata(request):
    issuer = _issuer(request)
    return JsonResponse(
        {
            "resource": "%s/mcp" % issuer,
            "authorization_servers": [issuer],
            "bearer_methods_supported": ["header"],
        }
    )


@require_http_methods(["GET"])
def authorization_server_metadata(request):
    issuer = _issuer(request)
    return JsonResponse(
        {
            "issuer": issuer,
            "authorization_endpoint": "%s/oauth/authorize" % issuer,
            "token_endpoint": "%s/oauth/token" % issuer,
            "registration_endpoint": "%s/oauth/register" % issuer,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": ["mcp"],
        }
    )


# --------------------------------------------------------------------------- #
# Dynamic Client Registration (RFC 7591)
# --------------------------------------------------------------------------- #

@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "invalid_client_metadata"}, status=400)
    redirect_uris = body.get("redirect_uris") or []
    if not isinstance(redirect_uris, list) or not redirect_uris or not all(
        isinstance(u, str) for u in redirect_uris
    ):
        return JsonResponse({"error": "invalid_redirect_uri"}, status=400)
    client = OAuthClient.objects.create(
        client_name=str(body.get("client_name") or "")[:255],
        redirect_uris=redirect_uris,
    )
    return JsonResponse(
        {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "redirect_uris": client.redirect_uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
        },
        status=201,
    )


# --------------------------------------------------------------------------- #
# Authorization endpoint
# --------------------------------------------------------------------------- #

def _validate_authorize_params(request):
    p = request.GET if request.method == "GET" else request.POST
    try:
        client = OAuthClient.objects.get(client_id=p.get("client_id", ""))
    except OAuthClient.DoesNotExist:
        return None, "unknown client_id"
    redirect_uri = p.get("redirect_uri", "")
    if redirect_uri not in client.redirect_uris:
        return None, "redirect_uri not registered for this client"
    if p.get("response_type", "") != "code":
        return None, "unsupported response_type (only 'code')"
    challenge = p.get("code_challenge", "")
    if not challenge or p.get("code_challenge_method", "") != "S256":
        return None, "PKCE code_challenge with S256 is required"
    return (
        {
            "client": client,
            "redirect_uri": redirect_uri,
            "challenge": challenge,
            "state": p.get("state", ""),
            "scope": p.get("scope", ""),
        },
        None,
    )


def _consent_html(csrf, client_name, user_email, org_name, params):
    hidden = "".join(
        '<input type="hidden" name="%s" value="%s">' % (escape(k), escape(v))
        for k, v in params.items()
    )
    return """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Authorize MCP access</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f5f6f8;margin:0;
   display:flex;min-height:100vh;align-items:center;justify-content:center}
 .card{background:#fff;max-width:420px;width:92%%;padding:28px 26px;border-radius:14px;
   box-shadow:0 6px 24px rgba(0,0,0,.08)}
 h1{font-size:18px;margin:0 0 4px}
 p{font-size:14px;color:#444;line-height:1.5}
 .row{font-size:13px;color:#555;margin:14px 0;padding:12px;background:#f7f8fa;border-radius:8px}
 .row b{color:#111}
 .btns{display:flex;gap:10px;margin-top:20px}
 button{flex:1;padding:11px;border:0;border-radius:8px;font-size:14px;cursor:pointer}
 .allow{background:#2563eb;color:#fff}
 .deny{background:#e5e7eb;color:#111}
 .scope{color:#666;font-size:12px;margin-top:6px}
</style></head><body>
<div class="card">
  <h1>Authorize access</h1>
  <p><b>%s</b> wants to access the CRM through the MCP connector on your behalf.</p>
  <div class="row">
    Signed in as <b>%s</b><br>Organization: <b>%s</b>
    <div class="scope">It will act with your role and permissions in this org.</div>
  </div>
  <form method="post">
    <input type="hidden" name="csrfmiddlewaretoken" value="%s">
    %s
    <div class="btns">
      <button class="deny" type="submit" name="decision" value="deny">Deny</button>
      <button class="allow" type="submit" name="decision" value="allow">Allow</button>
    </div>
  </form>
</div></body></html>""" % (
        escape(client_name),
        escape(user_email),
        escape(org_name),
        escape(csrf),
        hidden,
    )


@require_http_methods(["GET", "POST"])
def authorize(request):
    parsed, err = _validate_authorize_params(request)
    if err:
        return HttpResponseBadRequest("invalid_request: %s" % err)

    profile = _profile_from_session(request)
    if not profile:
        # Not logged into the CRM in this browser -> send to the frontend login,
        # then back here.
        return HttpResponseRedirect("/login?" + urlencode({"next": request.get_full_path()}))

    redirect_uri = parsed["redirect_uri"]
    state = parsed["state"]

    if request.method == "GET":
        csrf = get_token(request)
        html = _consent_html(
            csrf,
            parsed["client"].client_name or "An MCP application",
            profile.user.email,
            profile.org.name,
            {
                "client_id": parsed["client"].client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": parsed["challenge"],
                "code_challenge_method": "S256",
                "state": state,
                "scope": parsed["scope"],
            },
        )
        return HttpResponse(html)

    # POST = consent decision
    if request.POST.get("decision") != "allow":
        return HttpResponseRedirect(
            "%s?%s" % (redirect_uri, urlencode({"error": "access_denied", "state": state}))
        )

    code = secrets.token_urlsafe(32)
    OAuthAuthCode.objects.create(
        code=code,
        client=parsed["client"],
        profile=profile,
        org=profile.org,
        redirect_uri=redirect_uri,
        code_challenge=parsed["challenge"],
        scope=parsed["scope"],
        expires_at=timezone.now() + timedelta(seconds=CODE_TTL_SECONDS),
    )
    return HttpResponseRedirect(
        "%s?%s" % (redirect_uri, urlencode({"code": code, "state": state}))
    )


# --------------------------------------------------------------------------- #
# Token endpoint
# --------------------------------------------------------------------------- #

def _pkce_ok(verifier, challenge):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(computed, challenge)


@csrf_exempt
@require_http_methods(["POST"])
def token(request):
    if request.POST.get("grant_type", "") != "authorization_code":
        return JsonResponse({"error": "unsupported_grant_type"}, status=400)

    code = request.POST.get("code", "")
    redirect_uri = request.POST.get("redirect_uri", "")
    client_id = request.POST.get("client_id", "")
    verifier = request.POST.get("code_verifier", "")

    try:
        ac = OAuthAuthCode.objects.select_related("client", "profile", "org").get(code=code)
    except OAuthAuthCode.DoesNotExist:
        return JsonResponse({"error": "invalid_grant"}, status=400)

    if not ac.is_valid():
        return JsonResponse(
            {"error": "invalid_grant", "error_description": "code expired or already used"},
            status=400,
        )
    if ac.client.client_id != client_id or ac.redirect_uri != redirect_uri:
        return JsonResponse({"error": "invalid_grant"}, status=400)
    if not verifier or not _pkce_ok(verifier, ac.code_challenge):
        return JsonResponse(
            {"error": "invalid_grant", "error_description": "PKCE verification failed"},
            status=400,
        )

    ac.used = True
    ac.save(update_fields=["used"])

    _set_org_rls(ac.org_id)
    name = "MCP OAuth (%s)" % (ac.client.client_name or ac.client.client_id)
    raw, _pat = PersonalAccessToken.generate(ac.profile, name)

    return JsonResponse(
        {"access_token": raw, "token_type": "Bearer", "scope": ac.scope or "mcp"}
    )
