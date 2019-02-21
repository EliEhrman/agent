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
import nlbitvec

import utils
# import rules2
from utils import conn_type
from utils import rec_def_type

nt_match_phrases = collections.namedtuple('nt_match_phrases', 'istage, b_matched, phrase, b_result')

def_type_table = []
def_type_table.append(rec_def_type.err)
def_type_table.append(rec_def_type.obj)
def_type_table.append(rec_def_type.like)

# TBD: Move this to a utils py. This function is copied all over the place
def convert_charvec_to_arr(bin, size=-1):
	if size == -1:
		size = len(bin)
	bin_arr = bitvecdb.charArray(size)
	for ib in range(size): bin_arr[ib] = chr(bin[ib])
	return bin_arr

class cl_nlb_mgr_notifier(nlbitvec.cl_nlb_mgr_notific):
	def __init__(self, client):
		self.__client = client
		nlbitvec.cl_nlb_mgr_notific.__init__(self)


	def iel_bitvec_changed_alert(self, iel, bitvec):
		self.__client.iel_bitvec_changed(iel)


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
		self.__nlb_mgr_notifier = cl_nlb_mgr_notifier(self)
		self.__phrase_mgr = None
		self.__l_active_rules = [] # A list of pairs, first a bool for ext rule, second an index into either l_rules or rule_learn.py's write_recs array
		self.__hcdb_rules = None
		self.__lrule_mgr = None
		self.__mpdbs_mgr = None
		self.__test_stat_num_rules_found = 0
		self.__test_stat_num_rules_not_found = 0
		self.__d_iel_to_l_irules = dict()
		self.__d_irule_to_iactive = dict()
		self.__d_arg_cache = dict()
		self.__d_db_arg_cache = dict()
		self.load_rules(fn)

	def register_lrule(self, ilrule):
		ret = len(self.__l_active_rules)
		self.__l_active_rules.append((False, ilrule))
		return ret

	def register_rule_learner(self, lrule_mgr):
		self.__lrule_mgr = lrule_mgr

	def get_hcdb_rules(self):
		return self.__hcdb_rules

	def clr_db_arg_cache(self):
		self.__d_db_arg_cache = dict()

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
		self.__el_bitvec_mgr.register_notific(self.__nlb_mgr_notifier)
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms_mgr
		self.__bitvec_size = nlbitvec_mgr.get_bitvec_size()
		self.__hcdb_rules = bitvecdb.init_capp()
		bitvecdb.set_name(self.__hcdb_rules, 'rules')
		bitvecdb.set_b_rules(self.__hcdb_rules)
		self.__bitvec_size = nlbitvec_mgr.get_bitvec_size()
		bitvecdb.set_el_bitvec_size(self.__hcdb_rules, self.__bitvec_size)
		bitvecdb.set_pdbels(self.__hcdb_rules, self.__el_bitvec_mgr.get_hcbdb())
		for i_ext_rule, _ in enumerate(self.__lll_phrase_data):
			self.write_crec(i_ext_rule)
			self.__l_active_rules.append((True, i_ext_rule))
		bitvecdb.print_db_recs(self.__hcdb_rules, self.__el_bitvec_mgr.get_hcbdb())

	def init_vo(self, mpdbs_mgr):
		self.__mpdbs_mgr = mpdbs_mgr
		self.__hvos = bitvecdb.create_vo(	self.__hcdb_rules, self.__phraseperms.get_bdb_all_hcdb(),
											mpdbs_mgr.get_hcdb_story(), self.__el_bitvec_mgr.get_hcbdb())

	def iel_bitvec_changed(self, iel):
		s_irules = self.__d_iel_to_l_irules.get(iel, set())
		for irule in s_irules:
			self.write_crec(irule, b_change_not_add=True)

	def write_crec(self, irule, b_change_not_add = False):
		phrase_data, ll_vars, ll_el_cds = self.__lll_phrase_data[irule], self.__lll_vars[irule], self.__lll_el_cds[irule]
		phrase_bitvec = []; plen = 0; phrase_offsets = []; l_hds = []; phrase_offset = 0
		for iphrase, (phrase, l_el_cds) in enumerate(zip(phrase_data, ll_el_cds)):
			self.__phrase_mgr.add_phrase(phrase)
			for iel, (el, cd) in enumerate(zip(phrase, l_el_cds)):
				rel = self.__el_bitvec_mgr.get_el_id(el)
				assert rel != -1, 'Error! External rules at this point should have registered all their names.'
				if not b_change_not_add:
					s_irules = self.__d_iel_to_l_irules.get(rel, set())
					s_irules.add(irule)
					self.__d_iel_to_l_irules[rel] = s_irules
					self.__nlb_mgr_notifier.notify_on_iel(rel)
				el_bitvec = self.__el_bitvec_mgr.get_bin_by_id(rel)
				assert el_bitvec.count(1) > 0, 'Any external rule may only use one word not found in samples in a rule'
				phrase_bitvec += el_bitvec
				plen += 1
				l_hds.append(int(((1.0 - cd)*self.__bitvec_size)))
			phrase_offsets.append(phrase_offset)
			phrase_offset += len(phrase)
		if b_change_not_add:
			bitvecdb.change_rec(self.__hcdb_rules, plen, convert_charvec_to_arr(phrase_bitvec),
								self.__d_irule_to_iactive[irule])
			return
		bitvecdb.add_rec(self.__hcdb_rules, plen, convert_charvec_to_arr(phrase_bitvec))
		self.__d_irule_to_iactive[irule] = len(self.__l_active_rules)
		bitvecdb.set_rule_data(	self.__hcdb_rules, len(self.__l_active_rules), len(phrase_offsets),
									utils.convert_intvec_to_arr(phrase_offsets),
									utils.convert_intvec_to_arr(l_hds), len(ll_vars),
									utils.convert_intvec_to_arr([vv for var_def in ll_vars for vv in var_def]),
									int(self.__l_bresults[irule]),
									self.__d_rcats[self.__l_categories[irule]], self.__d_rnames[self.__l_names[irule]],
									True)
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
		print('run one rule:\n', mpdbs.get_bdb_story().print_db(self.__el_bitvec_mgr.get_hcbdb()))
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
					ll_rperms.append(rperm_combo + [mpdbs.get_bdb_story().get_rperm_from_iperm(match_arr[imatch])])
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

	def find_var_opts(self, idb, irule, num_var_opts, rperm, var_obj_parent, calc_level):
		print('irule', irule, 'num vars ret', num_var_opts, 'for rperm', rperm)

		# num_var_opts = num_vars_ret_arr[ifound]
		iel_ret = bitvecdb.intArray(num_var_opts);
		ivar_ret = bitvecdb.intArray(num_var_opts)
		src_iphrase_ret = bitvecdb.intArray(num_var_opts);
		src_iel_ret = bitvecdb.intArray(num_var_opts)
		bitvecdb.result_matching_rule_get_opt(self.__hcdb_rules, self.__phraseperms.get_bdb_all_hcdb(),
											  self.__el_bitvec_mgr.get_hcbdb(),
											  irule, rperm, iel_ret, ivar_ret,
											  src_iphrase_ret, src_iel_ret, num_var_opts)
		bitvecdb.init_vo(self.__hvos, irule, idb, -1, rperm)
		for ivar in range(num_var_opts):
			print('iel', iel_ret[ivar], 'ivar', ivar_ret[ivar], 'src iphrase', src_iphrase_ret[ivar],
				  'src iel', src_iel_ret[ivar])
			bitvecdb.add_ext_var(self.__hvos, ivar_ret[ivar], True, True, iel_ret[ivar], 0, ivar)
		bitvecdb.do_vo(self.__hvos)
		c_l_match_phrases = [];  l_map_to_obj_only = []
		num_c_match_phrases = bitvecdb.get_num_match_phrases(self.__hvos)
		num_rule_stages = bitvecdb.get_rule_num_phrases(self.__hvos)
		l_open_phrases = []
		for imatch in range(num_c_match_phrases):
			istage = bitvecdb.get_match_phrase_istage(self.__hvos, imatch)
			b_matched = bool(bitvecdb.get_match_phrase_b_matched(self.__hvos, imatch))
			num_phrase_els = bitvecdb.get_num_phrase_els(self.__hvos, imatch)
			match_phrase = []; b_all_obj = True; open_phrase = []
			for iel in range(num_phrase_els):
				i_def_type = bitvecdb.get_phrase_el_def_type(self.__hvos, imatch, iel)
				def_type = def_type_table[i_def_type]
				phrase_rval = bitvecdb.get_phrase_el_val(self.__hvos, imatch, iel)
				phrase_val = '(not found)' if phrase_rval == -1 else self.__el_bitvec_mgr.get_el_by_eid(phrase_rval)
				phrase_hd = bitvecdb.get_phrase_el_hd(self.__hvos, imatch, iel)
				# match_phrase.append([def_type, phrase_val])
				match_phrase.append(phrase_val)
				if def_type == rec_def_type.obj:
					open_phrase.append([rec_def_type.obj, phrase_val])
				elif def_type == rec_def_type.like:
					open_phrase.append([rec_def_type.like, phrase_val, phrase_hd])
					b_all_obj = False
				else:
					assert False, 'only rec_def_type obj and like should be possible in find_var_opts()'

			if b_all_obj:
				l_map_to_obj_only.append(len(c_l_match_phrases))
				c_l_match_phrases.append(nt_match_phrases(istage=istage, b_matched=b_matched, phrase=match_phrase,
														  b_result=self.__l_bresults[irule] and (istage==(num_rule_stages-1))))
			else:
				l_map_to_obj_only.append(-1)
				l_open_phrases.append(open_phrase)
		c_l_match_iphrase_combos = []
		num_c_combos = bitvecdb.get_num_combos(self.__hvos)
		c_combo_len = bitvecdb.get_combo_len(self.__hvos)
		for icombo in range(num_c_combos):
			one_combo = []; b_all_obj = True
			for ival in range(c_combo_len):
				i_combo_val = bitvecdb.get_combo_val(self.__hvos, icombo, ival)
				i_true_combo_val = l_map_to_obj_only[i_combo_val]
				if i_true_combo_val == -1:
					b_all_obj = False
				one_combo.append(i_true_combo_val)
			if b_all_obj:
				c_l_match_iphrase_combos.append(one_combo)
		return cl_var_match_opts(	irule, c_l_match_phrases, c_l_match_iphrase_combos,
									var_obj_parent, calc_level + 1, self.__l_bresults[irule],
									l_open_phrases)

	def find_var_opts_for_rules(self, goal_phrase, l_cat_names, l_rule_names, idb, var_obj_parent, calc_level):
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
		# bitvecdb.print_db_recs(self.__hcdb_rules, self.__el_bitvec_mgr.get_hcbdb())
		num_rules_found = bitvecdb.find_result_matching_rules(	self.__hcdb_rules, self.__phraseperms.get_bdb_all_hcdb(),
																self.__el_bitvec_mgr.get_hcbdb(), irule_arr,
																num_vars_ret_arr, rperms_ret_arr, len(l_rperms),
																rperms_arr, num_cats, cat_arr, num_rids, rid_arr)
		print('num_rules_found', num_rules_found)
		l_var_opt_objs = []
		for ifound in range(num_rules_found):
			l_var_opt_objs.append(self.find_var_opts(	idb, irule_arr[ifound], num_vars_ret_arr[ifound],
														rperms_ret_arr[ifound], var_obj_parent, calc_level))
		return l_var_opt_objs


class cl_var_match_opts(object):
	num_apply_cache_calls = 0
	max_obj_id = 0

	def __init__(self, irule, l_match_phrases, ll_match_iphrase_combos, parent_obj, calc_level, b_rule_has_result, l_open_phrases):
		self.__irule = irule
		self.__l_match_phrases = l_match_phrases
		self.__ll_match_iphrase_combos = ll_match_iphrase_combos
		self.__l_match_phrase_scores =  [0. for _ in l_match_phrases] # l_match_phrase_scores
		self.__l_combo_scores =  [0. for _ in ll_match_iphrase_combos]
		# self.__ll_var_match_opts = [[] for _ in l_match_phrases]  # for each match_phrase an array of cl_var_match_opts
		self.__l_var_match_opt_conts = [[] for _ in l_match_phrases]  # for each match_phrase an cl_var_match_opt_cont # need a list of var_match_objs for each iphrase, one for each matching rule
		self.__best_score = 0.
		self.__b_score_valid = False
		# self.__parent_obj = parent_obj
		self.__calc_level = calc_level
		self.__cont = []
		self.__obj_id = cl_var_match_opts.max_obj_id
		self.__b_rule_has_result = b_rule_has_result
		self.__l_open_phrases = l_open_phrases
		cl_var_match_opts.max_obj_id += 1

	def get_calc_level(self):
		return self.__calc_level

	def get_parent_obj(self):
		return self.__parent_obj

	def get_irule(self):
		return self.__irule

	def get_l_open_phrases(self):
		return self.__l_open_phrases

	def get_l_match_phrases(self):
		return self.__l_match_phrases

	def get_match_phrase(self, iphrase):
		return self.__l_match_phrases[iphrase]

	def get_ll_match_iphrase_combos(self):
		return self.__ll_match_iphrase_combos

	def get_l_match_phrase_scores(self):
		return self.__l_match_phrase_scores

	def get_match_phrase_score(self, iphrase):
		return self.__l_match_phrase_scores[iphrase]

	def set_cont(self, cont):
		assert self.__cont == [], 'Warning. Setting a cont where there is already one set.'
		self.__cont = cont
	# def set_match_phrase_score(self, iphrase, score):
	# 	self.__l_match_phrase_scores[iphrase] = score

	def get_l_var_match_opt_conts(self):
		return self.__l_var_match_opt_conts

	def get_var_match_opt_conts(self, iphrase):
		return self.__l_var_match_opt_conts[iphrase]

	def get_l_var_match_opts(self, iphrase):
		cont = self.__l_var_match_opt_conts[iphrase]
		if cont == [] or cont == None: return []
		return cont.get_var_match_opt_objs()
	# def get_cont_var_match_opts(self, iphrase):

	def set_score_invalid(self):
		if not self.__b_score_valid: return
		self.__b_score_valid = False
		if self.__cont != []:
			self.__cont.set_score_invalid()

	def loop_check(self, test_cont):
		if self.__cont == []:
			return False
		elif self.__cont == test_cont:
			return True
		else:
			return self.__cont.loop_check(test_cont)

	def set_var_match_opts(self, iphrase, var_match_obj_cont):
		# self.__ll_var_match_opts[iphrase] = l_var_match_objs
		if var_match_obj_cont != []: #  and not self.loop_check(var_match_obj_cont):
			self.__l_var_match_opt_conts[iphrase] = var_match_obj_cont
			self.set_score_invalid()

	# def set_l_var_match_opts(self, ll_var_match_objs):
	# 	self.__ll_var_match_opts = ll_var_match_objs
	# 	self.set_score_invalid()

	def apply_cached_var_match_objs(self, l_cache_var_opt_objs, calc_level, calc_level_limit):
		assert False, 'Old code?'
		if calc_level >= calc_level_limit: return [] # [[] for _ in l_cache_var_opt_objs]
		cl_var_match_opts.num_apply_cache_calls += 1
		l_var_opt_objs = []
		for var_opt_obj in l_cache_var_opt_objs:
			var_opt_obj_copy = cl_var_match_opts(var_opt_obj.get_parent_gg(), copy.deepcopy(var_opt_obj.get_l_match_phrases()),
													copy.deepcopy(var_opt_obj.get_ll_match_iphrase_combos()),
													self, calc_level+1)
			for iphrase, l_var_match_opts in enumerate(var_opt_obj.get_ll_var_match_opts()):
				l_var_match_opts_copy = \
					var_opt_obj_copy.apply_cached_var_match_objs(l_var_match_opts, calc_level+1, calc_level_limit)
				var_opt_obj_copy.set_var_match_opts(iphrase, l_var_match_opts_copy)
			l_var_opt_objs.append(var_opt_obj_copy)
			# need a set_var_match_opts here b_top_call?
		return l_var_opt_objs

	def get_best_score(self):
		if not self.__b_score_valid:
			self.calc_best_score()
		return self.__best_score

	def set_best_score(self, best_score):
		self.__best_score = best_score

	def get_gg_name(self):
		return self.__parent_gg.get_name()

	def calc_best_score(self):
		self.__best_score = 0.
		self.__b_score_valid = True

		for iphrase, match_phrase in enumerate(self.__l_match_phrases):
			if match_phrase.b_result: continue
			if match_phrase.b_matched: # deal with result phrase
				self.__l_match_phrase_scores[iphrase] = 1.
			elif self.__l_var_match_opt_conts[iphrase] == []:
				self.__l_match_phrase_scores[iphrase] = 0.
			else:
				l_var_match_opts = self.get_var_match_opt_conts(iphrase).get_var_match_opt_objs()
				max_child_score = max(l_var_match_opts, key=lambda x: x.get_best_score()).get_best_score()
				self.__l_match_phrase_scores[iphrase] = max_child_score

		l_match_phrase_scores = []
		best_score = 0.
		for icombo, l_match_iphrase_combo in enumerate(self.__ll_match_iphrase_combos):
			if self.get_b_rule_has_result():
				assert len(l_match_iphrase_combo) > 1, 'combo for rule with result must have length of at least 2'
				frac_denom = len(l_match_iphrase_combo) - 1
			else:
				frac_denom = len(l_match_iphrase_combo)
			score, frac = 0., 1. / frac_denom
			for iphrase in l_match_iphrase_combo:
				score += self.__l_match_phrase_scores[iphrase] * frac
			if score > best_score: best_score = score
			self.__l_combo_scores[icombo] = score
		self.__best_score = best_score
		# self.__b_score_valid = True

	def select_combo(self):
		if not self.__b_score_valid:
			self.calc_best_score()
		return np.random.choice(self.__ll_match_iphrase_combos, 1, p=self.__l_combo_scores)

	def get_sorted_l_combo(self):
		if not self.__b_score_valid:
			self.calc_best_score()
		return [match_iphrase_combo for _,match_iphrase_combo in
				sorted(zip([r * (1. - (random.random()/5.)) for r in self.__l_combo_scores],
						   self.__ll_match_iphrase_combos), reverse=True)]

	def get_b_rule_has_result(self):
		return self.__b_rule_has_result

# def get_sorted_ll_opts(self):
# 	if not self.__b_score_valid:
# 		self.calc_best_score()
# 	return [match_phrase_with_opt for _,match_phrase_with_opt in
# 			sorted(zip([r * (1. - (random.random()/5.)) for r in self.__l_match_phrase_scores],
# 					   zip(self.__l_match_phrases, self.__ll_var_match_opts)), key=lambda pair: pair[0], reverse=True)]




class cl_var_match_opt_cont(object):
	def __init__(self, l_var_match_opt_objs, calc_level, first_parent_obj):
		self.__l_var_match_opt_objs = l_var_match_opt_objs
		self.__calc_level = calc_level
		self.__l_parent_objs = [first_parent_obj]
		for var_opt_obj in l_var_match_opt_objs:
			var_opt_obj.set_cont(self)

	def get_calc_level(self):
		return self.__calc_level

	def add_parent_obj(self, parent_obj):
		self.__l_parent_objs.append(parent_obj)

	def get_var_match_opt_objs(self):
		return self.__l_var_match_opt_objs

	def set_score_invalid(self):
		for parent_var_obj in self.__l_parent_objs:
			if parent_var_obj != None:
				parent_var_obj.set_score_invalid()

	def loop_check(self, test_cont):
		for parent_var_obj in self.__l_parent_objs:
			if parent_var_obj == None: continue
			elif parent_var_obj.loop_check(test_cont):
				return True
			else: continue
		return False

