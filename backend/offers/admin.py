from django.contrib import admin

from offers.models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("client_name", "title", "brand", "status", "value", "slug", "created_at")
    list_filter = ("brand", "status", "org")
    search_fields = ("client_name", "title", "slug")
    readonly_fields = ("slug", "access_token", "created_at", "updated_at")
