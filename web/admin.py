# -*- coding: utf-8 -*-
from django.contrib import admin
from django.db.models import Max, Sum, Subquery, OuterRef, Value as V
from django.db.models.functions import JSONObject, Coalesce
from decimal import Decimal as D

from . import models as invoicing_models, admin_forms
from .signals import invoice_saved


class CompanyAdmin(admin.ModelAdmin):
	form = admin_forms.CompanyForm
	list_display = ['get_name', 'is_archived']
	list_filter = ['is_archived']

	def get_queryset(self, request):
		name_query = Subquery(invoicing_models.CompanyVersion.objects
			.filter(pk=OuterRef('last_version'))
			.values('name')[:1]
		)
		last_version_query = Subquery(invoicing_models.CompanyVersion.objects
			.filter(company_id=OuterRef('pk'))
			.values('company_id')
			.annotate(max_id=Max('pk'))
			.values('max_id')[:1]
		)
		return (super().get_queryset(request)
			.annotate(last_version=last_version_query)
			.annotate(name=name_query)
			.order_by('-last_version')
		)

	def save_model(self, request, obj, form, *args, **kwargs):
		created = not obj.pk
		super().save_model(request, obj, form, *args, **kwargs)
		changed = set((field for field in form.changed_data if field in admin_forms.COMPANY_FIELDS))
		if changed or created:
			version = invoicing_models.CompanyVersion(company=obj)
			for field in admin_forms.COMPANY_FIELDS:
				setattr(version, field, form.cleaned_data.get(field))
			version.save()

	def get_name(self, obj):
		return obj.name
	get_name.short_description = invoicing_models.CompanyVersion._meta.get_field('name').verbose_name
	get_name.admin_order_field = 'name'

	def get_prepopulated_fields(self, *args, **kwargs):
		return {'slug': ('name',)}


class ItemInline(admin.TabularInline):
	model = invoicing_models.Item
	extra = 10


class InvoiceAdmin(admin.ModelAdmin):
	form = admin_forms.InvoiceForm
	list_display = ['number', 'get_company_name', 'get_price', 'date_created', 'due']
	list_filter = ['date_created']
	inlines = [ItemInline]

	def get_queryset(self, request):
		return (super().get_queryset(request)
			.annotate(price=Coalesce(Sum('item__price'), V(D(0))))
			.select_related('company')
			.order_by('-pk'))

	def get_company_name(self, obj):
		return obj.company.name
	get_company_name.short_description = invoicing_models.CompanyVersion._meta.get_field('name').verbose_name
	get_company_name.admin_order_field = 'company__name'

	def get_price(self, obj):
		return obj.price
	get_price.short_description = invoicing_models.Item._meta.get_field('price').verbose_name
	get_price.admin_order_field = 'price'

	def get_changeform_initial_data(self, request):
		initial = super().get_changeform_initial_data(request)
		if not initial.get('number'):
			initial['number'] = invoicing_models.Invoice.get_next_number()
		return initial

	def save_related(self, request, form, formsets, *args, **kwargs):
		super().save_related(request, form, formsets, *args, **kwargs)
		invoice_saved.send(sender=invoicing_models.Invoice, instance=form.instance)


admin.site.register(invoicing_models.Company, CompanyAdmin)
admin.site.register(invoicing_models.Invoice, InvoiceAdmin)
