# -*- coding: utf-8 -*-
import binascii
import lzma
from decimal import Decimal as D
from typing import Optional

from django.utils import timezone

from .models import Invoice


def generate_code(*, amount, iban, swift='', date=None, beneficiary_name='', currency='EUR', variable_symbol='', constant_symbol='', specific_symbol='', note='', beneficiary_address_1='', beneficiary_address_2=''):
	'''Generate pay-by-square code that can by used to create QR code for
	banking apps
	When date is not provided current date will be used.
	'''

	if date is None:
		date = timezone.localdate()

	# 1) create the basic data structure
	data = '\t'.join(
		[
			'',
			'1',  # payment
			'1',  # simple payment
			str(amount.quantize(D('0.01'))),
			currency,
			date.strftime('%Y%m%d'),
			variable_symbol,
			constant_symbol,
			specific_symbol,
			'',  # previous 3 entries in SEPA format, empty because already provided above
			note,
			'1',  # to an account
			iban,
			swift,
			'0',  # not recurring
			'0',  # not 'inkaso'
			beneficiary_name,
			beneficiary_address_1,
			beneficiary_address_2,
		]
	)

	# 2) Add a crc32 checksum
	checksum = binascii.crc32(data.encode()).to_bytes(4, 'little')
	total = checksum + data.encode()

	# 3) Run through XZ
	compressed = lzma.compress(
		total,
		format=lzma.FORMAT_RAW,
		filters=[
			{
				'id': lzma.FILTER_LZMA1,
				'lc': 3,
				'lp': 0,
				'pb': 2,
				'dict_size': 128 * 1024,
			}
		],
	)

	# 4) prepend length and convert to hex
	compressed_with_length = b'\x00\x00' + len(total).to_bytes(2, 'little') + compressed

	# 5) Convert to padded binary string
	binary = ''.join(
		[bin(single_byte)[2:].zfill(8) for single_byte in compressed_with_length]
	)

	# 6) Pad with zeros on the right up to a multiple of 5
	length = len(binary)
	remainder = length % 5
	if remainder:
		binary += '0' * (5 - remainder)
		length += 5 - remainder

	# 7) Substitute each quintet of bits with corresponding character
	subst = '0123456789ABCDEFGHIJKLMNOPQRSTUV'
	return ''.join(
		[subst[int(binary[5 * i : 5 * i + 5], 2)] for i in range(length // 5)]
	)


def invoice_to_square_code(invoice):
	issuer = invoice.issuer
	return generate_code(
		amount=invoice.total,
		iban=issuer.iban.replace(' ', ''),
		swift=issuer.swift or '',
		variable_symbol=invoice.number,
		date=invoice.date_created,
	)
