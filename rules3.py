from __future__ import print_function
import sys
import csv
from enum import Enum
from StringIO import StringIO
import copy
import collections
import random
import re

import rules2
from rules2 import conn_type
from rules2 import rec_def_type

class cl_ext_rules(object):
	def __init__(self, fn):
		self.__l_rules = []
		self.__l_categories = []
		self.__l_names = []
		self.load_rules(fn)

	def load_rules(self, fn):
		l_rules_data = []
		try:
		# if True:
			with open(fn, 'rb') as fh:
				csvr = csv.reader(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				if int(version_str) != 1:
					raise ValueError('rules2 rules file', fn, 'version cannot be used. Starting from scratch')
				rule_start_marker = next(csvr)[0]
				if rule_start_marker != 'rules start':
					raise IOError('no rules start marker')
				# for irule in xrange(int(num_rules)):
				while True:
					trule = next(csvr)
					if trule[0] == 'rules end':
						break
					rule_name, category, srule = trule
					srule = self.extract_ml_srule(srule, csvr)
					l_rules_data.append((rule_name, category, srule))
		except ValueError as verr:
			print(verr.args)
		except IOError:
		# except:
			print('Could not open db_len_grps file! Starting from scratch.')
		except:
			print('Unexpected error:', sys.exc_info()[0])
			raise

		for rule_name, category, srule in l_rules_data:
			rule_pre = self.extract_rec_from_str(srule)
			rule, var_dict = [], dict()
			for iel, el in enumerate(rule_pre):
				if el[0] in [rec_def_type.like, rec_def_type.obj] and len(el) > 3:
					var_dict[el[3]] = iel
					rule += [el[:3]]
				elif el[0] == rec_def_type.var:
					rule += [[el[0], var_dict[el[1]]]]
					if len(el) > 2:
						rule[-1] += [el[2]]
				elif el[0] == rec_def_type.conn \
						and el[1] in [conn_type.Insert, conn_type.Modify, conn_type.Broadcast,
									  conn_type.Remove, conn_type.Unique, conn_type.start] \
						and len(el) > 2:
					rule += [el[:2] + [var_dict[e] for e in el[2:]]]
				else:
					rule += [el]

			self.__l_categories.append(category)
			self.__l_rules.append(rule)
			self.__l_names.append(rule_name)

		pass

	def extract_ml_srule(self, srule, csvr):
		ret = ''
		if srule[:3] == 'ml,':
			srule = srule[3:]
			while srule[-4:] != ',mle':
				ret += srule
				srule = next(csvr)[-1]
			ret += srule[:-4]
			return  ret
		return srule

	def extract_rec_from_str(self, srec):
		if srec == '':
			return None

		vars_dict = dict(); ipos = 0
		f = StringIO(srec)
		# csvw = csv.writer(l)
		rec = []; bgens = False
		b_in_phrase = False
		iphrase = -1
		ipos_in_phrase = -2
		l_phrase_data = []
		ll_el_data = [] # list of phrases, each containing data
		ll_vars = [] # quartets of (src_iphrase, src_pos, dest_iphrase, dest_pos)
		l_logic_ops = [] # list of [0, phrase ids] or [1, index to l_logic_ops]
		l_vars_tbl = []
		# lelr = csv.reader(f, delimiter=',')
		# row = next(lelr)

		row = re.split(',| ', srec)
		for lcvo in row:
			fcvo = StringIO(lcvo)
			lelf = next(csv.reader(fcvo, delimiter=':'))
			if lelf[0] == 'c':
				el = [rec_def_type.conn]
				if lelf[1] == 'a':
					el += [conn_type.AND]
				elif lelf[1] == 'r':
					el += [conn_type.OR]
				elif lelf[1] == 's':
					el += [conn_type.start]
					b_in_phrase = True
					ipos_in_phrase = -1
					iphrase += 1
				elif lelf[1] == 'e':
					el += [conn_type.end]
					b_in_phrase = False
				elif lelf[1] == 'i':
					el += [conn_type.Insert]
				elif lelf[1] == 'u':
					el += [conn_type.Unique]
				elif lelf[1] == 'm':
					el += [conn_type.Modify]
				elif lelf[1] == 'd':
					el += [conn_type.Remove]
				elif lelf[1] == 'f':
					el += [conn_type.IF]
				elif lelf[1] == 't':
					el += [conn_type.THEN]
					bgens = True
				elif lelf[1] == 'b':
					el += [conn_type.Broadcast]
				else:
					print('Unknown rec def. Exiting.')
					exit()
				if lelf[1] in ['s', 'i', 'u', 'm', 'd', 'b']:
					if len(lelf) > 2:
						el += [int(v) for v in lelf[2:]]
			elif lelf[0] == 'v':
				el = [rec_def_type.var]
				el += [int(lelf[1])]
				if len(lelf) > 2 and lelf[2] == 'r':
					el += [conn_type.replace_with_next]
			elif lelf[0] == 'o':
				el = [rec_def_type.obj]
				el += [lelf[1]]
				if len(lelf) > 2 and lelf[2] == 'r':
					el += [conn_type.replace_with_next]
			elif lelf[0] == 'l':
				el = [rec_def_type.like]
				el += [lelf[1], float(lelf[2])]
				if len(lelf) > 3:
					el += [int(lelf[3])]
			else:
				# el = [rec_def_type.error]
				# el += [lelf[1]]
				ipos += 1
				ipos_in_phrase += 1
				ivar = vars_dict.get(lelf[0], -1)
				if ivar == -1:
					vars_dict[lelf[0]] = len(l_vars_tbl)
					l_vars_tbl.append((ipos, (iphrase, ipos_in_phrase)),)
					if len(lelf) == 1:
						if bgens:
							el = [rec_def_type.obj]
							el += [lelf[0]]
						else:
							el = [rec_def_type.like] # old. change this to obj
							el += [lelf[0], 1., ipos]
					elif len(lelf) == 2:
						el = [rec_def_type.like]
						el += [lelf[0], float(lelf[1]), ipos]
				else:
					el = [rec_def_type.var]
					el += [l_vars_tbl[ivar][0]]

			rec += [el]

		return rec

