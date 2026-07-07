from django.urls import path

from accounts import import_views, views

app_name = "api_accounts"

urlpatterns = [
    path("", views.AccountsListView.as_view()),
    # CSV import (must be before <str:pk>/ to avoid being captured as an ID)
    path(
        "import/preview/",
        import_views.AccountImportPreviewView.as_view(),
        name="accounts_import_preview",
    ),
    path(
        "import/commit/",
        import_views.AccountImportCommitView.as_view(),
        name="accounts_import_commit",
    ),
    path("<str:pk>/", views.AccountDetailView.as_view()),
    path("<str:pk>/create_mail/", views.AccountCreateMailView.as_view()),
    path("comment/<str:pk>/", views.AccountCommentView.as_view()),
    path("attachment/<str:pk>/", views.AccountAttachmentView.as_view()),
]
