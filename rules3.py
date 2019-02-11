from __future__ import print_function
import sys
import csv
from enum import Enum
from StringIO import StringIO
import copy
import collections
import random
import re
import numpy as np
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
		self.__d_rcats = dict() # keyed by cat names, returns an index into __l_irules_in_cats and __l_cat_names
		self.__l_irules_in_cats = []
		self.__l_cat_names = []
		self.__l_names = []
		self.__d_rnames = dict()
		self.__lll_vars = [] # ll_vars for each rule
		self.__lll_phrase_data = []
		self.__lll_el_data = []
		self.__lll_vars = []
		self.__lll_el_cds = []
		self.__l_bresults = [] # for each rule does it have a result phrase
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

	def get_cid(self, rule_cat):
		cid = self.__d_rcats.get(rule_cat, -1)
		if cid == -1:
			cid = len(self.__l_irules_in_cats)
			self.__d_rcats[rule_cat] = cid
			self.__l_irules_in_cats.append([])
			self.__l_cat_names.append(rule_cat)
		return cid

	def get_cid_name(self, cid):
		return self.__l_cat_names[cid]

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
			rule, ll_phrase_data, ll_el_data, ll_vars, ll_el_cds, bresult = self.extract_rec_from_str(srule)

			icat = self.__d_rcats.get(category, -1)
			irule = len(self.__l_rules)
			if icat == -1:
				icat = len(self.__l_irules_in_cats)
				self.__d_rcats[category] = icat
				self.__l_irules_in_cats.append([])
				self.__l_cat_names.append(category)
			self.__l_irules_in_cats[icat].append(irule)
			# remove trailing dots
			rule_name = rule_name.rstrip('.')
			self.__d_rnames[rule_name] = irule
			self.__l_categories.append(category)
			self.__l_rules.append(rule)
			self.__l_names.append(rule_name)
			self.__lll_el_data.append(ll_el_data)
			self.__lll_phrase_data.append(ll_phrase_data)
			self.__lll_vars.append(ll_vars)
			self.__lll_el_cds.append(ll_el_cds)
			self.__l_bresults.append(bresult)

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

		return rec, l_phrase_data, ll_el_data, ll_vars, ll_el_cds, bgens

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
									utils.convert_intvec_to_arr([vv for var_def in ll_vars for vv in var_def]),
									int(self.__l_bresults[irule]),
									self.__d_rcats[self.__l_categories[irule]], self.__d_rnames[self.__l_names[irule]])
		pass

	def run_rule(self, mpdbs, stmt, phase_data, idb, l_rule_cats, l_rule_names=[]):
		results, l_use_rules_ids = [], []
		for rule_cat in l_rule_cats:
			cid = self.__d_rcats.get(rule_cat, -1)
			if cid != -1:
				l_use_rules_ids += self.__l_irules_in_cats[cid]
		# l_use_rules = [self.__l_fixed_rules[ir] for ir in l_use_rules_ids]
		for rule_name in l_rule_names:
			rid = self.__d_rnames.get(rule_name, -1)
			if rid == -1:
				print('Error. Unknown rule name requested for run rule:', rule_name)
				exit(1)
			l_use_rules_ids.append(rid)

		phrase = utils.full_split(stmt)
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		l_rperms = self.__phraseperms.get_perms(rphrase)
		ll_result_eids, ll_result_phrases = [], []
		for rid in l_use_rules_ids:
			for rperm in l_rperms:
				l_eids = self.__phraseperms.get_perm_eids(rperm)
				iclose_vars = filter(lambda l: l[2] == 0, self.__lll_vars[rid])
				bmatch = True
				for pos, eid in enumerate(l_eids):
					bvar = False
					for var in iclose_vars:
						if var[3] == pos:
							bvar = True
							if eid != l_eids[var[1]]:
								bmatch = False
								break
					if not bvar:
						nd_qbitvec = np.array(self.__el_bitvec_mgr.get_bin_by_id(eid), dtype=np.int8)
						nd_rbitvec = np.array(self.__el_bitvec_mgr.get_el_bin(self.__lll_phrase_data[rid][0][pos]), dtype=np.int8)
						hd = np.sum(np.not_equal(nd_qbitvec, nd_rbitvec))
						if hd > int((1. - self.__lll_el_cds[rid][0][pos])*self.__bitvec_size):
							bmatch =  False
							break
				if not bmatch: continue
				_, ll_result_eids_one_rule = self.run_one_rule(rid, rperm, [], mpdbs, idb)
				ll_result_eids += ll_result_eids_one_rule
				for l_result_eids in ll_result_eids_one_rule:
					ll_result_phrases.append([self.__el_bitvec_mgr.get_el_by_eid(eid) for eid in l_result_eids])

		return ll_result_eids, ll_result_phrases



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

	# currently this function is used to run one external rule on one src_rperm. The first clause has already been
	# checked. There is always a result clause.
	def run_one_rule(self, irule, src_rperm, result_words, mpdbs, idb):
		ll_phrase_data, ll_vars, ll_el_cds, = self.__lll_phrase_data[irule], self.__lll_vars[irule], self.__lll_el_cds[irule]
		ll_rperms_src, ll_rperms = [[src_rperm]], []
		for i_phrase_close, (l_phrase, l_el_cds) in enumerate(zip(ll_phrase_data[1:-1], ll_el_cds[1:-1])):
			num_len_recs, irec_arr = mpdbs.get_bdb_story().get_plen_irecs(idb, len(l_phrase))
			for rperm_combo in ll_rperms_src:
				ll_eids = [self.__phraseperms.get_perm_eids(rperm1) for rperm1 in rperm_combo]
				# l_phrase_eids = [self.__phraseperms.get_perm_eids(rperm1) for el in l_phrase]
				iclose_vars = filter(lambda l: l[2] == (i_phrase_close + 1), ll_vars)
				num_match, match_arr = num_len_recs, irec_arr
				for iel, el_cd in enumerate(l_el_cds):
					# There can only be one var matching a dest, so we simply take the first from the list created by the filter
					l_one_var = filter(lambda l: l[3] == iel, iclose_vars)
					if l_one_var == []:
						num_match, match_arr = \
							mpdbs.get_bdb_story().get_el_hd_recs(	iel, int((1 - el_cd)*self.__bitvec_size),
																	l_phrase[iel], num_match, match_arr)
					else:
						one_var = l_one_var[0]
						src_eid = ll_eids[one_var[0]][one_var[1]]
						num_match, match_arr = \
							mpdbs.get_bdb_story().get_rperms_with_eid_at(idb, src_eid, one_var[3], num_match, match_arr)
					if num_match == 0:
						break
				for imatch in range(num_match):
					ll_rperms.append(rperm_combo + [match_arr[imatch]])
			if ll_rperms == []: return [], []
			ll_rperms_src = list(ll_rperms)
			ll_rperms = []

		iresult_vars = filter(lambda l: l[2] == len(ll_phrase_data)-1, ll_vars)
		l_result_eids = [self.__el_bitvec_mgr.get_el_id(el) for el in ll_phrase_data[-1]]
		ll_result_eids = []
		for l_rperms in ll_rperms_src:
			ll_eids = [self.__phraseperms.get_perm_eids(rperm1) for rperm1 in l_rperms]
			l_result_eids_copy = list(l_result_eids)
			for var in iresult_vars:
				l_result_eids_copy[var[3]] = ll_eids[var[0]][var[1]]
			ll_result_eids.append(l_result_eids_copy)
		return ll_rperms_src, ll_result_eids

	def find_rules_matching_result(self, goal_phrase, l_cat_names, l_rule_names):
		print('find_rules_matching_result rules for', goal_phrase)
		rphrase = self.__phrase_mgr.get_rphrase(goal_phrase)
		l_rperms = self.__phraseperms.get_perms(rphrase)
		num_poss_ret = len(self.__l_active_rules) * len(l_rperms)
		irule_arr = bitvecdb.intArray(num_poss_ret); rperms_ret_arr = bitvecdb.intArray(num_poss_ret)
		num_vars_ret_arr = bitvecdb.intArray(num_poss_ret)
		rperms_arr = utils.convert_intvec_to_arr(l_rperms)
		cat_arr, rid_arr, num_cats, num_rids  = 0, 0, 0, 0
		l_rcats, l_rids = [], []
		for cat_name in l_cat_names:
			cid = self.__d_rcats.get(cat_name, -1)
			if cid >= 0: l_rcats.append(cid)
			num_cats = len(l_rcats)
		if num_cats > 0: cat_arr = utils.convert_intvec_to_arr(l_rcats)
		for rule_name in l_rule_names:
			rid = self.__d_rnames.get(rule_name, -1)
			if rid >= 0: l_rids.append(rid)
			num_rids = len(l_rids)
		# if num_rids > 0:
		rid_arr = utils.convert_intvec_to_arr(l_rids)
		num_rules_found = bitvecdb.find_result_matching_rules(	self.__hcdb_rules, irule_arr, num_vars_ret_arr,
																rperms_ret_arr, self.__phraseperms.get_bdb_all_hcdb(),
																len(l_rperms), rperms_arr, num_cats, cat_arr, num_rids, rid_arr)
		print('num_rules_found', num_rules_found)
		for ifound in range(num_rules_found):
			print('irule', irule_arr[ifound], 'num vars ret', num_vars_ret_arr[ifound], 'for rperm', rperms_ret_arr[ifound])

