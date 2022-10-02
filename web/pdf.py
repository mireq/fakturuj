# -*- coding: utf-8 -*-
import threading
from io import BytesIO

from django.conf import settings
from django.http.response import HttpResponse
from django.template.loader import render_to_string

from .models import TEXT_DATABASE_LOCATION
from .pay_by_square import invoice_to_square_code


reportlab_lock = threading.Lock()


def rml_to_pdf(rml_code):
	from z3c.rml import rml2pdf

	with reportlab_lock:
		return rml2pdf.parseString(rml_code)


def render_to_pdf(template, ctx, buff=None):
	rml_code = render_to_string(template, ctx)
	pdf = rml_to_pdf(rml_code)
	if buff is not None:
		buff.write(pdf.read())
		pdf.seek(0)

	return pdf


def render_to_pdf_response(template, ctx):
	response = HttpResponse(content_type='application/pdf')
	render_to_pdf(template, ctx, response)
	return response


def get_or_create_pdf(invoice, buffer, force_generate=False, **kwargs):
	if not force_generate:
		try:
			with open(invoice.get_pdf_path(), 'rb') as fp:
				buffer.write(fp.read())
				return
		except FileNotFoundError:
			pass

	data = BytesIO()
	ctx = {
		'invoice': invoice,
		'db_root': TEXT_DATABASE_LOCATION,
		'static_root': settings.BASE_DIR / 'static',
		'bysquare': invoice_to_square_code(invoice),
	}
	ctx.update(kwargs)
	render_to_pdf('invoice.rml', ctx, data)
	invoice.get_pdf_path().parent.mkdir(parents=True, exist_ok=True)
	with open(invoice.get_pdf_path(), 'wb') as fp:
		data.seek(0)
		fp.write(data.read())
	data.seek(0)
	buffer.write(data.read())
