# -*- coding: utf-8 -*-
from datetime import timedelta

from django import forms
from django.utils import timezone
from django.db.models import Max, Q

from .models import Company, CompanyVersion, Invoice, Item
from .utils import normalize_decimal


COMPANY_FIELDS = ['name', 'address', 'ico', 'dic', 'ic_dph', 'bank_account', 'bank_code', 'swift', 'iban']


class CompanyForm(forms.ModelForm):
	name = CompanyVersion._meta.get_field('name').formfield()
	address = CompanyVersion._meta.get_field('address').formfield()
	ico = CompanyVersion._meta.get_field('ico').formfield()
	dic = CompanyVersion._meta.get_field('dic').formfield()
	ic_dph = CompanyVersion._meta.get_field('ic_dph').formfield()
	bank_account = CompanyVersion._meta.get_field('bank_account').formfield()
	bank_code = CompanyVersion._meta.get_field('bank_code').formfield()
	swift = CompanyVersion._meta.get_field('swift').formfield()
	iban = CompanyVersion._meta.get_field('iban').formfield()

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		current_company = self.instance.current
		if current_company is not None:
			for field in COMPANY_FIELDS:
				self.initial[field] = getattr(current_company, field)

	class Meta:
		model = Company
		fields = COMPANY_FIELDS + ['slug', 'is_archived']


class InvoiceForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['due'].required = False # Automatically add 2 weeks if is empty
		self.limit_company_queryset(self.fields['issuer'])
		self.limit_company_queryset(self.fields['company'])
		last_invoice = Invoice.objects.order_by('-pk').first()
		if last_invoice:
			self.initial.setdefault('issuer', last_invoice.issuer)
			self.initial.setdefault('company', last_invoice.company)

	def limit_company_queryset(self, field):
		last_versions = (Company.objects
			.filter(is_archived=False)
			.values('pk')
			.annotate(last_version=Max('companyversion__pk'))
			.values('last_version'))
		additional_pk = []
		if self.instance.issuer_id:
			additional_pk.append(self.instance.issuer_id)
		if self.instance.company_id:
			additional_pk.append(self.instance.company_id)
		field.queryset = field.queryset.filter(Q(pk__in=last_versions) | Q(pk__in=additional_pk))

	def save(self, commit=True):
		obj = super().save(commit=False)
		if not obj.due:
			obj.due = timezone.localdate() + timedelta(14)
		if commit:
			obj.save()
		return obj

	class Meta:
		model = Invoice
		fields = '__all__'


class ItemForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['unit'].widget.attrs['style'] = 'width: 4em'
		self.fields['quantity'].widget.attrs['style'] = 'width: 5em'
		self.fields['unit_price'].widget.attrs['style'] = 'width: 7em'
		value = self.initial.get('unit_price')
		if value is not None:
			self.initial['unit_price'] = normalize_decimal(value)
		value = self.initial.get('quantity')
		if value is not None:
			self.initial['quantity'] = normalize_decimal(value)

	def save(self, commit=True):
		obj = super().save(commit=False)
		obj.price = self.cleaned_data['unit_price'] * self.cleaned_data['quantity']
		if commit:
			obj.save()
		return obj

	class Meta:
		model = Item
		exclude = ['price']
