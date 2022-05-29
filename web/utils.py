# -*- coding: utf-8 -*-
from decimal import Decimal as D


def normalize_decimal(num):
	return num.quantize(D(1)) if num == num.to_integral() else num.normalize()
