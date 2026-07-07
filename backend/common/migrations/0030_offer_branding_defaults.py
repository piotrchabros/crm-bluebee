"""Seed per-org offer branding so existing orgs don't visually regress.

Maps orgs by name to the brand they used pre-Feature-5; everything else keeps
the model defaults (dark + lime). Only the new offer_* fields are touched —
email/website are left alone (they're shared with invoices/documents).
"""

from django.db import migrations


def set_branding(apps, schema_editor):
    Org = apps.get_model("common", "Org")
    for org in Org.objects.all():
        name = f"{org.name or ''} {org.company_name or ''}".lower()
        changed = []
        if "bespoke" in name:
            org.offer_theme = "light"
            org.offer_accent = "#0d6efd"
            if not org.offer_prepared_by:
                org.offer_prepared_by = "BespokeSoft (Dawid Kawalec)"
            changed = ["offer_theme", "offer_accent", "offer_prepared_by"]
        elif "bluebee" in name:
            org.offer_theme = "dark"
            org.offer_accent = "#E3FF04"
            if not org.offer_prepared_by:
                org.offer_prepared_by = "BlueBee"
            changed = ["offer_theme", "offer_accent", "offer_prepared_by"]
        if changed:
            org.save(update_fields=changed)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0029_org_offer_accent_org_offer_prepared_by_and_more"),
    ]
    operations = [migrations.RunPython(set_branding, noop)]
