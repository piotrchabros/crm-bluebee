from django.urls import path

from offers.views import (
    OfferDetailView,
    OfferEditView,
    OfferListCreateView,
)

app_name = "api_offers"

urlpatterns = [
    path("", OfferListCreateView.as_view()),
    path("<str:pk>/", OfferDetailView.as_view()),
    path("<str:pk>/edit/", OfferEditView.as_view()),
]
