from datetime import datetime, timezone as dt_timezone

from django.db import models
from django.utils.translation import gettext_lazy as _

from common.base import BaseModel
from common.models import Org
from offers.utils import generate_access_token, slugify

BRAND_CHOICES = (
    ("bluebee", "BlueBee"),
    ("bespoke", "BespokeSoft"),
)

STATUS_CHOICES = (
    ("draft", "Szkic"),
    ("sent", "Wysłana"),
    ("viewed", "Wyświetlona"),
    ("accepted", "Zaakceptowana"),
    ("rejected", "Odrzucona"),
)


class Offer(BaseModel):
    """A data-driven AI sales offer (ported from bluebee-website, type=`data`).

    `offer_data` holds the validated structured offer (hero + sections of the 10
    block types — see `offers.schema`). Rendered publicly at
    `/oferta/{slug}-{access_token}`. Org-scoped like the rest of the CRM.
    """

    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="offers")
    # Optional originating deal — the Opportunity "Generuj ofertę" flow links here.
    opportunity = models.ForeignKey(
        "opportunity.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offers",
    )

    client_name = models.CharField(_("Klient"), max_length=255)
    title = models.CharField(_("Tytuł oferty"), max_length=255)
    brand = models.CharField(
        _("Brand"), max_length=16, choices=BRAND_CHOICES, default="bespoke"
    )
    # Validated structured offer (offers.schema.validate_offer_data).
    offer_data = models.JSONField(_("Dane oferty"), default=dict)

    status = models.CharField(
        _("Status"), max_length=16, choices=STATUS_CHOICES, default="draft"
    )

    # Public link parts. slug is globally unique (public lookup = slug+token);
    # access_token is generated once at create and never changes afterwards.
    slug = models.SlugField(_("Slug"), max_length=255, unique=True, blank=True)
    access_token = models.CharField(_("Access token"), max_length=16, blank=True)

    # Tracking
    sent_at = models.DateTimeField(_("Wysłano"), null=True, blank=True)
    viewed_at = models.DateTimeField(_("Pierwsze wyświetlenie"), null=True, blank=True)
    responded_at = models.DateTimeField(_("Odpowiedź klienta"), null=True, blank=True)

    valid_until = models.DateField(_("Ważność do"), null=True, blank=True)
    value = models.DecimalField(
        _("Wartość netto (PLN)"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(_("Wewnętrzne notatki"), blank=True, null=True)

    class Meta:
        verbose_name = "Oferta"
        verbose_name_plural = "Oferty"
        db_table = "offer"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["org", "-created_at"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.client_name} — {self.title}"

    # --- slug / token lifecycle ------------------------------------------------

    def _unique_slug(self) -> str:
        """`slugify(client_name)-YYYY-MM`, suffixed on collision (mirrors source)."""
        now = datetime.now(dt_timezone.utc)
        ym = f"{now.year}-{now.month:02d}"
        base = f"{slugify(self.client_name) or 'oferta'}-{ym}"
        if not Offer.objects.filter(slug=base).exists():
            return base
        for i in range(2, 100):
            candidate = f"{base}-{i}"
            if not Offer.objects.filter(slug=candidate).exists():
                return candidate
        return f"{base}-{generate_access_token()[:4]}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            if not self.access_token:
                self.access_token = generate_access_token()
            if not self.slug and self.client_name:
                self.slug = self._unique_slug()
        else:
            # access_token is immutable after creation — never overwrite it on update.
            if self.pk:
                original = (
                    Offer.objects.filter(pk=self.pk)
                    .values_list("access_token", flat=True)
                    .first()
                )
                if original:
                    self.access_token = original
        super().save(*args, **kwargs)

    @property
    def public_path(self) -> str:
        """`/oferta/{slug}-{access_token}` — relative public path."""
        return f"/oferta/{self.slug}-{self.access_token}"
