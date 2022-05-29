# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from . import views


urlpatterns = [
	path('admin/', admin.site.urls),
	path('<int:pk>/', views.invoice_pdf_view, name="invoice_pdf"),
]

if settings.DEBUG:
	urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

