from django.urls import path

from . import views

urlpatterns = [
    path("orgs/", views.orgs, name="orgs"),
    path("disagreements/", views.disagreements, name="disagreements"),
]
