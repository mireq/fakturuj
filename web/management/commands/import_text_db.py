# -*- coding: utf-8 -*-
from django.core.management import BaseCommand
from django.conf import settings
from pathlib import Path
import re
from decimal import Decimal as D
from datetime import date, datetime
from ...models import COMPANY_MAPPING, Company, CompanyVersion, Invoice, Item


COMPANY_MAPPING_LOWER = dict([(key.lower(), value) for key, value in COMPANY_MAPPING])


class Command(BaseCommand):
	def handle(self, *args, **options):
		numbers = set()
		self.companies_cache = {}
		for invoice in self.invoices:
			invoice['issuer_id'] = self.get_or_create_company(invoice['issuer'])
			invoice['company_id'] = self.get_or_create_company(invoice['company'])
			invoice['number'] = invoice['date_created'].strftime('%Y%m') + ('%02d' % invoice['number_suffix'])
			if invoice['number'] in numbers:
				continue
			numbers.add(invoice['number'])
			del invoice['issuer']
			del invoice['company']
			del invoice['number_suffix']
			items = invoice.pop('items')
			invoice = Invoice(**invoice)
			Invoice.objects.bulk_create([invoice])
			invoice = Invoice.objects.order_by('-pk').first()
			items = [Item(invoice=invoice, price=item[0], item=item[1]) for item in items]
			Item.objects.bulk_create(items)

	@property
	def db_location(self):
		return Path(settings.TEXT_DATABASE_LOCATION).expanduser().resolve()

	@property
	def invoices(self):
		invoice_files = sorted(self.db_location.glob('*/data/income/*'))
		return [self.load_invoice(f) for f in invoice_files if '.' if f.name[:4].isnumeric()]

	def load_invoice(self, path):
		path_match = re.match(r'^(\d{4})(\d{2})(\d{2})-\d{2}(\d{2})-(.*)$', path.name)
		date_created = date(int(path_match.group(1)), int(path_match.group(2)), int(path_match.group(3)))
		number_suffix = int(path_match.group(4))
		company_slug = path_match.group(5)
		invoice_data = {
			'issuer': self.load_company('my-company', date_created),
			'company': self.load_company(company_slug, date_created),
			'date_created': date_created,
			'number_suffix': number_suffix,
			'items': []
		}
		with open(path, 'r') as fp:
			for line in fp:
				line = line.strip()
				if not line:
					continue
				key, value = line.split(': ', 1)
				key = key.lower()
				if key in ['due', 'delivry']:
					invoice_data[key] = datetime.strptime(value, '%Y-%m-%d').date()
				elif key == 'item':
					price, item = value.split(': ', 1)
					price = D(price)
					invoice_data['items'].append((price, item))
		return invoice_data

	def load_company(self, slug, date_created):
		company_data = {'slug': slug}
		company_filename = self.db_location / date_created.strftime('%Y') / 'data' / 'companies' / slug
		db_values = {}
		with open(company_filename, 'r') as fp:
			for line in fp:
				line = line.strip()
				if not line:
					continue
				key, value = line.split(': ', 1)
				field = COMPANY_MAPPING_LOWER[key.lower()]
				db_values.setdefault(field, [])
				db_values[field].append(value)
		db_values = {key: '\n'.join(value) for key, value in db_values.items()}
		company_data.update(db_values)
		return company_data

	def get_or_create_company(self, company):
		cache = self.companies_cache.get(company['slug'])
		if cache is not None and cache[1] != company:
			cache = None
		if cache is None:
			company_instance = Company.objects.get_or_create(slug=company['slug'])[0]
			version_data = company.copy()
			del version_data['slug']
			version_data['company'] = company_instance
			version = CompanyVersion.objects.create(**version_data)
			cache = [version.pk, company]
		self.companies_cache[company['slug']] = cache
		return cache[0]
