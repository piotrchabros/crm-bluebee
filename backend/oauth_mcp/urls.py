from django.urls import path

from . import views

urlpatterns = [
    path(".well-known/oauth-authorization-server", views.authorization_server_metadata),
    path(".well-known/oauth-protected-resource", views.protected_resource_metadata),
    path(".well-known/oauth-protected-resource/mcp", views.protected_resource_metadata),
    path("oauth/register", views.register),
    path("oauth/authorize", views.authorize),
    path("oauth/token", views.token),
]
