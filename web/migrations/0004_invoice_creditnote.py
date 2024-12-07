# Generated by Django 4.2.7 on 2024-01-03 20:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		('web', '0003_item_unit_price_alter_item_quantity'),
	]

	operations = [
		migrations.AddField(
			model_name='invoice',
			name='creditnote',
			field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='creditnotes', to='web.invoice', verbose_name='Credit note'),
		),
	]