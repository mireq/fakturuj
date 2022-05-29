# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django import apps


class AppConfig(apps.AppConfig):
	name = 'web'
	verbose_name = 'web'

	def ready(self):
		from . import signals
		self.patch_migrations()

	def patch_migrations(self):
		from django.db.migrations.writer import MigrationWriter
		rx = re.compile('^(    )+', flags=re.MULTILINE)
		replace = lambda match: '\t'*(len(match.group())//4)
		old_as_string = MigrationWriter.as_string
		MigrationWriter.as_string = lambda self: rx.sub(replace, old_as_string(self))
