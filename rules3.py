from __future__ import print_function
import sys
import csv
from enum import Enum
from StringIO import StringIO
import copy
import collections
import random
import re
from bitvecdb import bitvecdb

import utils
import rules2
from rules2 import conn_type
from rules2 import rec_def_type

# TBD: Move this to a utils py. This function is copied all over the place
def convert_charvec_to_arr(bin, size=-1):
	if size == -1:
		size = len(bin)
	bin_arr = bitvecdb.charArray(size)
	for ib in range(size): bin_arr[ib] = chr(bin[ib])
	return bin_arr


class cl_ext_rules(object):
	def __init__(self, fn):
		self.__l_rules = []
		self.__l_categories = []
		self.__l_names = []
		self.__lll_vars = [] # ll_vars for each rule
		self.__lll_phrase_data = []
		self.__lll_el_data = []
		self.__lll_vars = []
		self.__lll_el_cds = []
		self.__el_bitvec_mgr = None
		self.__bitvec_size = -1
		self.__phrase_mgr = None
		self.__l_active_rules = [] # A list of pairs, first a bool for ext rule, second an index into either l_rules or rule_learn.py's write_recs array
		self.__hcdb_rules = None
		self.__lrule_mgr = None
		self.__test_stat_num_rules_found = 0
		self.__test_stat_num_rules_not_found = 0
		self.load_rules(fn)

	def register_lrule(self, ilrule):
		ret = len(self.__l_active_rules)
		self.__l_active_rules.append((False, ilrule))
		return ret

	def register_rule_learner(self, lrule_mgr):
		self.__lrule_mgr = lrule_mgr

	def get_hcdb_rules(self):
		return self.__hcdb_rules

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
			rule, ll_phrase_data, ll_el_data, ll_vars, ll_el_cds = self.extract_rec_from_str(srule)

			self.__l_categories.append(category)
			self.__l_rules.append(rule)
			self.__l_names.append(rule_name)
			self.__lll_el_data.append(ll_el_data)
			self.__lll_phrase_data.append(ll_phrase_data)
			self.__lll_vars.append(ll_vars)
			self.__lll_el_cds.append(ll_el_cds)

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
		ll_el_cds = [] # list of phrases, each containg one cd per el
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
					b_in_phrase = True
					ipos_in_phrase = -1
					iphrase += 1
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
				if len(l_phrase_data) <= iphrase:
					l_phrase_data.append([])
					ll_el_data.append([])
					ll_el_cds.append([])
				l_phrase_data[iphrase].append(lelf[0])
				ivar = vars_dict.get(lelf[0], -1)
				if ivar == -1:
					vars_dict[lelf[0]] = len(l_vars_tbl)
					l_vars_tbl.append((ipos, (iphrase, ipos_in_phrase)),)
					if len(lelf) == 1 or (len(lelf) > 1 and lelf[1] == ''):
						if bgens:
							el = [rec_def_type.obj]
							el += [lelf[0]]
							ll_el_data[iphrase].append([rec_def_type.obj])
						else:
							el = [rec_def_type.like] # old. change this to obj
							el += [lelf[0], 1., ipos]
							ll_el_data[iphrase].append([rec_def_type.like])
						ll_el_cds[iphrase].append(1.)
					else:
						el = [rec_def_type.like]
						el += [lelf[0], float(lelf[1]), ipos]
						ll_el_data[iphrase].append([rec_def_type.like])
						ll_el_cds[iphrase].append(float(lelf[1]))
				else:
					el = [rec_def_type.var]
					el += [l_vars_tbl[ivar][0]]
					ll_el_data[iphrase].append([rec_def_type.var])
					vpos = l_vars_tbl[ivar][1]
					ll_vars.append((vpos[0], vpos[1], iphrase, ipos_in_phrase))
					ll_el_cds[iphrase].append(1.)
				if len(lelf) > 2 and lelf[2] == 'r':
					el += [conn_type.replace_with_next]
					ll_el_data[iphrase][-1].append(conn_type.replace_with_next)

			rec += [el]

		return rec, l_phrase_data, ll_el_data, ll_vars, ll_el_cds

	def set_mgrs(self, nlbitvec_mgr, phrase_mgr, phraseperms_mgr):
		self.__el_bitvec_mgr = nlbitvec_mgr
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms_mgr
		self.__bitvec_size = nlbitvec_mgr.get_bitvec_size()
		self.__hcdb_rules = bitvecdb.init_capp()
		bitvecdb.set_name(self.__hcdb_rules, 'rules')
		bitvecdb.set_b_rules(self.__hcdb_rules)
		self.__bitvec_size = nlbitvec_mgr.get_bitvec_size()
		bitvecdb.set_el_bitvec_size(self.__hcdb_rules, self.__bitvec_size)
		for i_ext_rule, _ in enumerate(self.__lll_phrase_data):
			self.write_crec(i_ext_rule)
			self.__l_active_rules.append((True, i_ext_rule))

	def write_crec(self, irule):
		phrase_data, ll_vars, ll_el_cds = self.__lll_phrase_data[irule], self.__lll_vars[irule], self.__lll_el_cds[irule]
		phrase_bitvec = []; plen = 0; phrase_offsets = []; l_hds = []; phrase_offset = 0
		for iphrase, (phrase, l_el_cds) in enumerate(zip(phrase_data, ll_el_cds)):
			self.__phrase_mgr.add_phrase(phrase)
			for iel, (el, cd) in enumerate(zip(phrase, l_el_cds)):
				el_bitvec = self.__el_bitvec_mgr.get_el_bin(el)
				assert el_bitvec.count(1) > 0, 'Any external rule may only use one word not found in samples in a rule'
				phrase_bitvec += el_bitvec
				plen += 1
				l_hds.append(int(((1.0 - cd)*self.__bitvec_size)))
			phrase_offsets.append(phrase_offset)
			phrase_offset += len(phrase)
		bitvecdb.add_rec(self.__hcdb_rules, plen, convert_charvec_to_arr(phrase_bitvec))
		bitvecdb.set_rule_el_data(	self.__hcdb_rules, len(self.__l_active_rules), len(phrase_offsets),
									utils.convert_intvec_to_arr(phrase_offsets),
									utils.convert_intvec_to_arr(l_hds), len(ll_vars),
									utils.convert_intvec_to_arr([vv for var_def in ll_vars for vv in var_def]))
		pass

	# def run_one_rule(self, irule_rec, rperm_ret):
	# 	bext, irule = self.__l_active_rules[irule_rec]
	#
	# 	if not bext:
	# 		self.__lrule_mgr.test_rule(irule, rperm_ret, result_words, mpdbs, idb)
	# 		continue
	# 	print('should run rule called', self.__l_names[irule])
	# 	self.run_one_rule(irule, rperm_ret, result_words, mpdbs, idb)

	def test_rule(self, mpdbs, stmt, l_results, idb):
		phrase = utils.full_split(stmt)
		result_words = ''
		if l_results != []:
			result_words = ' '.join(utils.full_split(utils.convert_phrase_to_word_list(l_results[0][1:]))).lower()
		print('Testing rules for', phrase)
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		l_rperms = self.__phraseperms.get_perms(rphrase)
		# The maximum theoretical returns is the num of rules * the number of source perms
		num_poss_ret = len(self.__l_active_rules) * len(l_rperms)
		irule_arr = bitvecdb.intArray(num_poss_ret); rperms_ret_arr = bitvecdb.intArray(num_poss_ret)
		rperms_arr = utils.convert_intvec_to_arr(l_rperms)
		num_rules_found = bitvecdb.find_matching_rules(	self.__hcdb_rules, irule_arr, rperms_ret_arr,
														self.__phraseperms.get_bdb_all_hcdb(), len(l_rperms), rperms_arr)
		for iret in range(num_rules_found):
			# self.run_one_rule(irule_arr[iret], rperms_ret_arr[iret])
			bext, irule = self.__l_active_rules[irule_arr[iret]]
			rperm_ret = rperms_ret_arr[iret]
			if not bext:
				self.__lrule_mgr.test_rule(irule, rperm_ret, result_words, mpdbs, idb)
				continue
			print('should run rule called', self.__l_names[irule])
			self.run_one_rule(irule, rperm_ret, result_words, mpdbs, idb)


		if num_rules_found > 0:
			self.__test_stat_num_rules_found += 1
		else:
			self.__test_stat_num_rules_not_found += 1
		pass

	def run_one_rule(self, irule, src_rperm, result_words, mpdbs, idb):
		ll_phrase_data, ll_vars, ll_el_cds, = self.__lll_phrase_data[irule], self.__lll_vars[irule], self.__lll_el_cds[irule]
		ll_rperms_src, ll_rperms = [[src_rperm]], []
		for i_phrase_close, (l_phrase, l_el_cds) in enumerate(zip(ll_phrase_data[1:], ll_el_cds[1:])):
			num_len_recs, irec_arr = mpdbs.get_bdb_story().get_plen_irecs(idb, len(l_phrase))
			for rperm_combo in ll_rperms_src:
				ll_eids = [self.__phraseperms.get_perm_eids(rperm1) for rperm1 in rperm_combo]
				# l_phrase_eids = [self.__phraseperms.get_perm_eids(rperm1) for el in l_phrase]
				iclose_vars = filter(lambda l: l[2] == (i_phrase_close + 1), ll_vars)
				num_match, match_arr = num_len_recs, irec_arr
				for iel, el_cd in enumerate(l_el_cds):
					one_var = filter(lambda l: l[3] == iel, iclose_vars)
					if one_var == []:
						num_match, match_arr = \
							mpdbs.get_bdb_story().get_el_hd_recs(	iel, int((1 - el_cd)*self.__bitvec_size),
																	l_phrase[iel], num_match, match_arr)
					else:
						src_eid = ll_eids[one_var[0]][one_var[1]]
						num_match, match_arr = \
							mpdbs.get_bdb_story().get_rperms_with_eid_at(idb, src_eid, one_var[3], num_match, match_arr)
					if num_match == 0:
						break
				for imatch in range(num_match):
					ll_rperms.append(rperm_combo + [match_arr[imatch]])
			if ll_rperms == []: return []
			ll_rperms_src = list(ll_rperms)
			ll_rperms = []

		return ll_rperms_src

