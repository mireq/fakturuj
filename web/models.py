# -*- coding: utf-8 -*-
import re
from decimal import Decimal as D
from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from .utils import normalize_decimal


COMPANY_MAPPING = [
	('Name', 'name'),
	('Address', 'address'),
	('Number', 'ico'),
	('DIC', 'dic'),
	('Vat', 'ic_dph'),
	('Bank-account', 'bank_account'),
	('Bank-code', 'bank_code'),
	('IBAN', 'iban'),
]

INVOICE_MAPPING = [
	('Due', 'due'),
	('Delivery', 'delivery'),
]

TEXT_DATABASE_LOCATION = Path(settings.TEXT_DATABASE_LOCATION).expanduser().resolve()


class Company(models.Model):
	is_archived = models.BooleanField(
		verbose_name=_("Is archived"),
		blank=True,
		default=False,
	)
	slug = models.SlugField(
		verbose_name=_("Slug"),
		unique=True,
	)

	def get_text_db_path(self, date):
		year = date.strftime('%Y')
		return TEXT_DATABASE_LOCATION / year / 'data' / 'companies' / self.slug

	@property
	def current(self):
		if self.pk is None:
			return None
		return CompanyVersion.objects.filter(company_id=self.pk).order_by('-pk').first()

	def __str__(self):
		return str(self.current)

	class Meta:
		verbose_name = _("Company")
		verbose_name_plural = _("Companies")


class CompanyVersion(models.Model):
	LABELS = {
		'ico': "IČO",
		'dic': "DIČ",
		'ic_dph': "IČ DPH",
		'iban': "IBAN",
	}

	company = models.ForeignKey(
		Company,
		verbose_name=_("Company"),
		on_delete=models.CASCADE,
	)
	name = models.CharField(
		verbose_name=_("Company name"),
		max_length=100
	)
	address = models.TextField(
		verbose_name=_("Address"),
	)
	ico = models.CharField(
		verbose_name="IČO",
		max_length=20,
		blank=True
	)
	dic = models.CharField(
		verbose_name="DIČ",
		max_length=20,
		blank=True
	)
	ic_dph = models.CharField(
		verbose_name="IČ DPH",
		max_length=20,
		blank=True
	)
	bank_account = models.CharField(
		verbose_name=_("Bank account number"),
		max_length=20,
		blank=True
	)
	bank_code = models.CharField(
		verbose_name=_("Bank code"),
		max_length=20,
		blank=True
	)
	swift = models.CharField(
		verbose_name=_("Swift code"),
		max_length=20,
		blank=True
	)
	iban = models.CharField(
		verbose_name=_("IBAN"),
		max_length=50,
		blank=True
	)

	def get_company_data(self, issuer=False):
		values = []
		fields = ['ico', 'dic', 'ic_dph']
		if issuer:
			fields.append('iban')
		for field in fields:
			value = getattr(self, field)
			if value:
				values.append((self.LABELS[field], value))
		if issuer and not self.iban and self.bank_account:
			value = f'{self.bank_account} / {self.bank_code}'
			values.append(("Číslo účtu", value))
		return values

	@property
	def issuer_company_data(self):
		return self.get_company_data(issuer=True)

	@property
	def company_data(self):
		return self.get_company_data(issuer=False)

	def __str__(self):
		return self.name

	class Meta:
		verbose_name = _("Company version")
		verbose_name_plural = _("Company versions")


class Invoice(models.Model):
	date_created = models.DateField(
		editable=False
	)
	number = models.CharField(
		verbose_name=_("Number"),
		max_length=20,
		unique=True
	)
	due = models.DateField(
		verbose_name=_("Due date"),
	)
	delivery = models.DateField(
		verbose_name=_("Delivery date"),
		blank=True,
		null=True,
	)
	issuer = models.ForeignKey(
		CompanyVersion,
		verbose_name=_("Issuer"),
		on_delete=models.PROTECT,
		related_name='issued_invoices',
	)
	company = models.ForeignKey(
		CompanyVersion,
		verbose_name=_("Company"),
		on_delete=models.PROTECT,
		related_name='invoices',
	)
	creditnote = models.ForeignKey(
		'self',
		verbose_name=_("Credit note"),
		on_delete=models.PROTECT,
		related_name='creditnotes',
		blank=True,
		null=True
	)

	@property
	def total(self):
		return normalize_decimal(sum((item.price for item in self.item_set.all()), D(0)))

	@cached_property
	def has_unit_quantity(self):
		for quantity, unit in self.item_set.values_list('quantity', 'unit'):
			if unit or quantity != 1:
				return True
		return False

	def get_absolute_url(self):
		return reverse('invoice_pdf', args=(self.pk,))

	def get_filename(self):
		return (self.delivery or self.date_created).strftime('%Y%m%d-%m') + ("%02d" % self.get_suffix_number()) + '-' + self.company.company.slug

	def get_pdf_filename(self):
		return f'{self.get_filename()}.pdf'

	def get_text_db_path(self):
		filename = self.get_filename()
		year = (self.delivery or self.date_created).strftime('%Y')
		return TEXT_DATABASE_LOCATION / year / 'data' / 'income' / filename

	def get_pdf_path(self):
		filename = self.get_pdf_filename()
		year = (self.delivery or self.date_created).strftime('%Y')
		return TEXT_DATABASE_LOCATION / year / 'output' / filename

	def save(self, *args, **kwargs):
		if not self.id and not self.date_created:
			self.date_created = timezone.localdate()
		return super().save(*args, **kwargs)

	@staticmethod
	def get_next_number(invoice_date=None):
		if invoice_date is None:
			invoice_date = timezone.localdate()
		pat = invoice_date.strftime(settings.ORDER_NUMBER_FORMAT)
		#suffix_len = int(re.search('\<(\d+)\>', pat).group(1))
		number_format = re.sub('\<(\d+)\>', r'%0\1d', pat)
		pat = re.sub('\<(\d+)\>', r'([0-9]{\1})', pat)
		pat = f'^{pat}$'
		last_invoice_number = (Invoice.objects
			.filter(number__regex=pat)
			.order_by('-number')
			.values_list('number', flat=True)
			.first())
		if last_invoice_number is None:
			last_invoice_number = 0
		else:
			last_invoice_number = int(re.match(pat, last_invoice_number).group(1))
		return number_format % (last_invoice_number + 1)

	def get_suffix_number(self):
		pat = (self.delivery or self.date_created).strftime(settings.ORDER_NUMBER_FORMAT)
		pat = re.sub('\<(\d+)\>', r'([0-9]{\1})', pat)
		re_match = re.match(pat, self.number)
		if re_match is None:
			return None
		else:
			return int(re_match.group(1))

	def get_suffix_number(self):
		pat = self.date_created.strftime(settings.ORDER_NUMBER_FORMAT)
		suffix_len = int(re.match('.*\<(\d+)\>.*', pat).group(1))
		return int(self.number[-suffix_len:])

	def __str__(self):
		return self.number

	class Meta:
		verbose_name = _("Invoice")
		verbose_name_plural = _("Invoices")


class Item(models.Model):
	invoice = models.ForeignKey(
		Invoice,
		verbose_name=_("Invoice"),
		on_delete=models.CASCADE,
	)
	item = models.CharField(
		verbose_name=_("Item"),
		max_length=100
	)
	price = models.DecimalField(
		verbose_name=_("Price"),
		max_digits=20,
		decimal_places=2
	)
	unit_price = models.DecimalField(
		verbose_name=_("Unit price"),
		max_digits=20,
		decimal_places=2
	)
	quantity = models.DecimalField(
		verbose_name=_("Quantity"),
		max_digits=20,
		decimal_places=5,
		default=1
	)
	unit = models.CharField(
		verbose_name=_("Unit"),
		max_length=20,
		blank=True,
		default=''
	)

	@property
	def normalized_price(self):
		return normalize_decimal(self.price)

	@property
	def normalized_unit_price(self):
		return normalize_decimal(self.unit_price.quantize(D('0.01')))

	@property
	def normalized_quantity(self):
		return normalize_decimal(self.quantity)

	def __str__(self):
		return self.item

	class Meta:
		verbose_name = _("Invoice item")
		verbose_name_plural = _("Invoice items")
		ordering = ('pk',)
