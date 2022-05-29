# -*- coding: utf-8 -*-
from django.http.response import HttpResponse
from django.views.generic import DetailView

from .models import Invoice
from .pdf import get_or_create_pdf


class InvoicePDFView(DetailView):
	model = Invoice

	def get(self, request, **kwargs):
		self.invoice = self.get_object()
		response = HttpResponse(content_type='application/pdf')
		response['Content-Disposition'] = f'filename={self.invoice.get_pdf_filename()}'
		get_or_create_pdf(self.invoice, response, force_generate='generate' in request.GET, stamp='stamp' in request.GET)
		return response


invoice_pdf_view = InvoicePDFView.as_view()
