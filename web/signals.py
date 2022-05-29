# -*- coding: utf-8 -*-
from django.dispatch import receiver, Signal

from .models import Invoice, COMPANY_MAPPING, INVOICE_MAPPING


invoice_saved = Signal()


def save_company(company, date_created):
	path = company.company.get_text_db_path(date_created)
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, 'w') as fp:
		for db_key, field in COMPANY_MAPPING:
			value = getattr(company, field)
			if isinstance(value, str):
				value = value.splitlines()
			elif value:
				value = [value]
			else:
				value = []
			for value in value:
				fp.write(f'{db_key}: {value}\n')


def save_income(invoice):
	path = invoice.get_text_db_path()
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, 'w') as fp:
		for item in invoice.item_set.all():
			fp.write(f'Item: {item.normalized_price}: {item.item}\n')
		for db_key, field in INVOICE_MAPPING:
			value = getattr(invoice, field)
			if value:
				value = value.strftime('%Y-%m-%d')
			if value:
				fp.write(f'{db_key}: {value}\n')


@receiver(invoice_saved, sender=Invoice)
def save_text_db(sender, instance, **kwargs):
	save_company(instance.issuer, instance.date_created)
	save_company(instance.company, instance.date_created)
	save_income(instance)
