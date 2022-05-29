# -*- coding: utf-8 -*-
import threading
from io import BytesIO
from .models import TEXT_DATABASE_LOCATION

import qrcode
from django.conf import settings
from django.http.response import HttpResponse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

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


class EpsImage(qrcode.image.base.BaseImage):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._rectangles = []

	def drawrect(self, row, col):
		self._rectangles.append((row, col))

	def save(self, stream, kind=None):
		self.check_kind(kind=kind)
		stream.write((f'<!--{self.width}-->').encode('utf-8'))
		for row, col in self._rectangles:
			row = self.width - row - 1 # invert Y axis
			stream.write(f'<rect x="{col}cm" y="{row}cm" width="1.02cm" height="1.02cm" fill="true" stroke="false" />'.encode('utf-8'))


def generate_qr(invoice):
	code = invoice_to_square_code(invoice)
	img = qrcode.make(code, version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, image_factory=EpsImage)
	buf = BytesIO()
	img.save(buf)
	buf.seek(0)
	return buf.read().decode('utf-8')


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
		'qr': mark_safe(generate_qr(invoice)),
	}
	ctx.update(kwargs)
	render_to_pdf('invoice.rml', ctx, data)
	invoice.get_pdf_path().parent.mkdir(parents=True, exist_ok=True)
	with open(invoice.get_pdf_path(), 'wb') as fp:
		data.seek(0)
		fp.write(data.read())
	data.seek(0)
	buffer.write(data.read())
