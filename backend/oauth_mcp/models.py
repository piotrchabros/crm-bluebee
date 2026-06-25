"""Models backing the MCP OAuth 2.1 authorization server.

Deliberately small: a dynamically-registered public client and a short-lived,
single-use, PKCE-bound authorization code. The issued access token is a
Personal Access Token (see common.models.PersonalAccessToken), so there is no
token model here.
"""

import secrets

from django.db import models
from django.utils import timezone

from common.models import Org, Profile


def _gen_client_id():
    return "mcp_" + secrets.token_urlsafe(24)


class OAuthClient(models.Model):
    """An MCP host (e.g. Claude) registered via Dynamic Client Registration.

    Public client: no secret. It is constrained to the redirect URIs it
    declared at registration and must use PKCE.
    """

    client_id = models.CharField(max_length=128, unique=True, default=_gen_client_id)
    client_name = models.CharField(max_length=255, blank=True, default="")
    redirect_uris = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.client_name or self.client_id


class OAuthAuthCode(models.Model):
    """Single-use, short-lived authorization code.

    Bound to the authenticated profile/org, the client, the exact redirect URI,
    and a PKCE challenge so a leaked code is useless without the verifier.
    """

    code = models.CharField(max_length=128, unique=True)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    org = models.ForeignKey(Org, on_delete=models.CASCADE)
    redirect_uri = models.TextField()
    code_challenge = models.CharField(max_length=255)
    scope = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (not self.used) and self.expires_at > timezone.now()
