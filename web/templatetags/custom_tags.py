# -*- coding: utf-8 -*-
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
import re
from decimal import Decimal as D


register = template.Library()


@register.filter
def linebreaksbr_xml(value):
	lines = value.splitlines()
	lines = [escape(line) for line in lines]
	return mark_safe('<br />'.join(lines))


@register.filter
def resize_qr(code, target_size):
	code = re.match(r'^<!--(\d+)-->(.*)$', code)
	width, code = D(code.group(1)), code.group(2)
	try:
		target_size, move_x, move_y = target_size.split(',')
	except ValueError:
		move_x = '0'
		move_y = '0'
	target_size = re.match(r'^([0-9.]+)(.*)$', target_size)
	target_size, target_unit = D(target_size.group(1)), target_size.group(2)
	move_x = D(move_x)
	move_y = D(move_y)
	def resize(re_match):
		attr = re_match.group(1)
		size = D(re_match.group(2)) * target_size / width
		if attr == 'x':
			size += move_x
		if attr == 'y':
			size += move_y
		value = str(size.quantize(D('0.0001'))) + target_unit
		return f'{attr}="{value}"'
	code = re.sub(r'(width|height|x|y)="([0-9.]+)cm"', resize, code)
	return mark_safe(code)
