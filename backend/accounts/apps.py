from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        # Wire account<->contact relationship-sync signals.
        from . import signals  # noqa: F401
