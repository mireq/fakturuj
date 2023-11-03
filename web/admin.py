# -*- coding: utf-8 -*-
from decimal import Decimal as D

from django.contrib import admin
from django.contrib.admin.filters import SimpleListFilter
from django.db.models import Max, Sum, Subquery, OuterRef, Value as V
from django.db.models.functions import Coalesce

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
	form = admin_forms.ItemForm
	model = invoicing_models.Item
	extra = 10


class InvoiceDateListFilter(SimpleListFilter):
	title = invoicing_models.Invoice._meta.get_field('date_created').verbose_name
	parameter_name = 'date_created'

	def lookups(self, request, model_admin):
		years = model_admin.get_queryset(request).values_list('date_created__year', flat=True).order_by('-date_created__year').distinct()
		return [(y, str(y)) for y in years]

	def queryset(self, request, queryset): # pylint: disable=unused-argument
		value = self.value()
		if value is not None:
			return queryset.filter(date_created__year=value)
		return queryset


class InvoiceAdmin(admin.ModelAdmin):
	form = admin_forms.InvoiceForm
	list_display = ['number', 'get_company_name', 'get_price', 'date_created', 'due']
	list_filter = [InvoiceDateListFilter, 'company']
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

	def changelist_view(self, request, extra_context=None):
		extra_context = extra_context or {}
		cl = self.get_changelist_instance(request)
		queryset = cl.get_queryset(request)
		total = queryset.aggregate(total=Sum('price'))['total'] or D(0)
		extra_context['total'] = total
		return super().changelist_view(request, extra_context)


admin.site.register(invoicing_models.Company, CompanyAdmin)
admin.site.register(invoicing_models.Invoice, InvoiceAdmin)
