from __future__ import print_function

import numpy as np
import random
import timeit
import itertools
import copy

import utils
from utils import profile_decor
import rules2
from rules2 import conn_type
from rules2 import rec_def_type
from rules2 import nt_vars
from rules2 import nt_match_phrases

a0time_tot, atime_tot, btime_tot, ctime_tot = 0, 0, 0, 0

class Enum(set):
	def __getattr__(self, name):
		if name in self:
			return name
		raise AttributeError

c_bitvec_gg_learn_min = 30 #100 # must be even
c_bitvec_gg_stats_min = 30 # 100
c_bitvec_gg_initial_valid = 0.3
c_bitvec_gg_delta_on_parent = .2
c_bitvec_learn_min_unusual = 9 # 23
c_bitvec_finetune_num_rnds = 10  # type: int
c_bitvec_rnd_hd_max = 3
assert c_bitvec_gg_learn_min % 2 == 0, 'c_bitvec_gg_learn_min must be even'

rule_status = Enum([	'untried', 'initial', 'perfect', 'expands', 'perfect_block', 'blocks',
						'partial_expand', 'partial_block', 'irrelevant', 'mutant', 'endpoint'])

# total_time = 0.
# num_calls = 0
# b_in_time = False

# def gg_time_decor(fn):
# 	def wr(*args, **kwargs):
# 		global total_time
# 		print('calling function:', fn.func_name)
# 		s = timeit.default_timer()
# 		r = fn(*args, **kwargs)
# 		total_time += timeit.default_timer() - s
# 		return r
# 	return wr

class cl_bitvec_gg(object):
	find_matches_num_calls = 0
	find_matches_time_sum = 0.
	find_matches_time_count = 0.
	bitvec_size = -1
	# test_start_time = timeit.default_timer()


	def __init__(self, mgr, ilen, phrase_len, result, num_stages=1, l_wlist_vars = [],
				 phrase2_ilen = -1, phrase2_len = -1, parent_irule = -1,
				 l_phrases_len=[], l_phrases_ilen=[]):
		self.__l_phrases = []
		self.__ilen = ilen
		self.__phrase_len = phrase_len
		self.__result = result
		self.__num_since_learn = 0
		self.__mgr = mgr
		self.__l_els_rep = [[] for _ in range(phrase_len)]
		self.__l_hd_max = [self.bitvec_size for _ in range(phrase_len)]
		self.__hit_pct = 0.
		self.__b_formed = False
		self.__rule_rec = []
		self.__b_tested = False
		self.__status = rule_status.untried
		self.__num_stages = num_stages
		self.__parent_irule = parent_irule # rule and gg are interchangeable
		self.__child_rules = []
		self.__l_wlist_vars = l_wlist_vars
		self.__phrase2_ilen = phrase2_ilen
		self.__phrase2_len = phrase2_len
		self.__num_stats = 0
		self.__num_hits = 0
		self.__score = -1.0
		self.__match_bins = []
		self.__match_hits = []
		self.__gg_rev_impr = [] # a descendent gg (not child) improvement based on characterizing the misses
		self.__l_gg_rnd_impr = [] # random improvements based on tightening characterization of individuals els
		self.__b_rev_impr = False # I/this/self is a rev improv
		self.__b_rnd_impr = False
		self.__gg_src = [] # The src gg is not a parent but a less improved version of the rule that caused this one to be created
		self.__impr_score = -1.
		self.__d_exdb = dict()
		self.__name = ''
		self.__d_arg_cache = dict()
		self.__d_db_arg_cache = dict()
		if l_phrases_len == []:
			self.__l_phrases_len = [phrase_len]
			self.__l_phrases_ilen = [ilen]
			if num_stages > 1:
				self.__l_phrases_len += [phrase2_len]
				self.__l_phrases_ilen += [phrase2_ilen]
		else:
			self.__l_phrases_len = l_phrases_len
			self.__l_phrases_ilen = l_phrases_ilen

		for stg in range(1, num_stages):
			self.__l_els_rep += [[] for _ in range(self.__l_phrases_len[stg])]
			self.__l_hd_max += [self.bitvec_size for _ in range(self.__l_phrases_len[stg])]

	def clr_db_arg_cache(self):
		self.__d_db_arg_cache = dict()

	def set_imprv(self, gg_src, b_rev_imprv, b_rnd_imprv):
		self.__b_rev_impr = b_rev_imprv
		self.__b_rnd_impr = b_rnd_imprv
		self.__gg_src = gg_src

	def set_els_rep(self, l_els_rep, l_hd_max):
		self.__l_els_rep = l_els_rep
		self.__l_hd_max = l_hd_max

	def get_name(self):
		return self.__name

	def set_name(self, name):
		self.__name = name

	def get_phrase2_ilen(self):
		return self.__phrase2_ilen

	def get_last_phrase_ilen(self):
		return self.__l_phrases_ilen[-1]

	def is_tested(self):
		return self.__b_tested

	def is_scored(self):
		return self.__score > 0.

	def is_formed(self):
		return self.__b_formed

	def set_formed_and_tested(self, bformed, btested):
		self.__b_formed, self.__b_tested = bformed, btested

	def get_num_stages(self):
		return self.__num_stages

	def get_parent(self):
		return self.__mgr.get_rule(self.__parent_irule)

	def get_score(self):
		return self.__score

	def set_score(self, score):
		self.__score = score

	def get_status(self):
		return self.__status

	def get_phrase2_len(self):
		return self.__phrase2_ilen, self.__phrase2_len

	def set_rule_rec(self, rule_rec):
		self.__rule_rec = rule_rec

	def get_gg_rev_impr(self):
		return self.__gg_rev_impr

	def get_gg_rnd_impr(self):
		return self.__l_gg_rnd_impr

	def set_exdb(self, d_exdb):
		self.__d_exdb = d_exdb

	def test_rule_match(self, l_wlist_vars, result, phrase2_ilen):
		if l_wlist_vars == self.__l_wlist_vars and result == self.__result and phrase2_ilen == self.__phrase2_ilen:
			return True
		return False

	def add_child_rule_id(self, child_rule_id):
		self.__child_rules.append(child_rule_id)

	def get_child_rule_ids(self):
		return self.__child_rules

	def add_phrase_stage2(self, iphrase, iphrase2):
		self.__l_phrases.append((iphrase, iphrase2))
		self.__num_since_learn += 1
		l_phrases1, l_phrases2 = [phrases[0] for phrases in self.__l_phrases], [phrases[1] for phrases in self.__l_phrases]
		if self.__num_since_learn <= c_bitvec_gg_learn_min:
			return
		# untested
			# test_set = [(self.__ilen, iphrase), (phrase2_ilen, iphrase2)]
		l_dest_var_pos = [(l_pos[2], l_pos[3]) for l_pos in self.__l_wlist_vars]
		prev_iel = 0
		rule_phrase = [[rec_def_type.conn, conn_type.AND]]
		var_pos_dict = dict()
		for istage, ilen, l_phrases in [(0, self.__ilen, l_phrases1), (1, self.__phrase2_ilen, l_phrases2)]:
			rule_phrase += [[rec_def_type.conn, conn_type.start]]
			len_phrase_bin_db = self.__mgr.get_phrase_bin_db(ilen)
			gg_bin_db = len_phrase_bin_db[l_phrases]
			phrase_len = gg_bin_db.shape[1] / self.bitvec_size
			m_match = np.ones(len(len_phrase_bin_db), dtype=bool)
			for iel in range(phrase_len):
				var_pos_dict[(istage, iel)] = len(rule_phrase)
				if (istage, iel) in l_dest_var_pos: # this is a var dest and so not compared on
					ivar = l_dest_var_pos.index((istage, iel))
					src_istage, src_ipos, _, _ = self.__l_wlist_vars[ivar]
					rule_phrase += [[rec_def_type.var, var_pos_dict[(src_istage, src_ipos)]]]
					continue
				el_bins = gg_bin_db[:, iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
				els_rep = np.median(el_bins, axis=0)
				nd_diffs = np.not_equal(els_rep, el_bins)
				# nd_diffs = np.where(nd_diffs, np.ones_like(nd_phrase_bits_db), np.zeros_like(nd_phrase_bits_db))
				hd_max = np.max(np.sum(nd_diffs, axis=1))
				self.__l_els_rep[prev_iel + iel] = els_rep
				self.__l_hd_max[prev_iel + iel] = hd_max
				hd_rep = np.sum(np.not_equal(self.__mgr.get_el_db(), els_rep), axis=1)
				rep_word = self.__mgr.get_word_by_id(np.argmin(hd_rep))
				rule_phrase += [[rec_def_type.like, rep_word, hd_max]]
			prev_iel += phrase_len
			rule_phrase += [[rec_def_type.conn, conn_type.end]]

		self.__b_formed = True
		self.__rule_rec = rule_phrase
		self.__num_since_learn = 0
		if self.is_tested():
			self.__score = self.__num_hits / float(self.__num_stats)
			if self.__score > c_bitvec_gg_initial_valid:
				parent_score = self.get_parent().get_score()
				if parent_score < self.__score:
					if (self.__score - parent_score) / (1. - parent_score) > c_bitvec_gg_delta_on_parent:
						self.__status = rule_status.expands
					else:
						self.__status = rule_status.irrelevant
				else:
					if (parent_score - self.__score) / parent_score  > c_bitvec_gg_delta_on_parent:
						self.__status = rule_status.blocks
					else:
						self.__status = rule_status.irrelevant
			self.fine_tune(self.__match_bins, self.__match_hits)
			print('parent score:', self.__mgr.get_rule(self.__parent_irule).get_score(),
				  'status', self.__status, 'score', self.__score, 'for rule:', rules2.gen_rec_str(self.__rule_rec) )
			pass

		pass

	def find_rnd_tuning(self, l_els_rep_src, l_hd_max_src, phrase_bins, hits, phrase_len):
		num_hits = np.sum(hits)
		old_true_positive =  num_hits / float(phrase_bins.shape[0])
		b_one_found, best_true_positive, num_hits_best = False, -1.0, -1
		l_els_rep_best, l_hd_max_best = [], []

		for irnd in xrange(c_bitvec_finetune_num_rnds):
			m_matches = np.ones(phrase_bins.shape[0], dtype=np.bool)
			riphrase = random.randint(0, phrase_bins.shape[0]-1)
			l_els_rep, l_hd_max = list(l_els_rep_src), list(l_hd_max_src)
			riel = random.randint(0, phrase_len-1)
			if l_els_rep[riel] == []:
				continue
			l_els_rep[riel] = phrase_bins[riphrase, riel * self.bitvec_size:(riel + 1) * self.bitvec_size].astype(np.float)
			l_hd_max[riel] = random.randint(0, c_bitvec_rnd_hd_max)

			for iel in range(phrase_len):
				if l_els_rep[iel] == []:
					continue
				el_bins = phrase_bins[:, iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
				nd_diffs_hits = np.sum(np.not_equal(l_els_rep[iel], el_bins), axis=1)
				m_matches = np.logical_and(m_matches, (nd_diffs_hits <= l_hd_max[iel]))

			num_matches = np.sum(m_matches)
			if num_matches < c_bitvec_learn_min_unusual:
				continue
			num_match_hits = np.sum(np.logical_and(m_matches, np.array(hits)))
			true_positive = num_match_hits / float(num_matches)
			if true_positive > old_true_positive and \
					(true_positive - old_true_positive) / (1. - old_true_positive) > c_bitvec_gg_delta_on_parent:
				if not b_one_found or true_positive > best_true_positive \
						or (true_positive == best_true_positive and num_match_hits > num_hits_best):
					b_one_found, num_hits_best = True, num_match_hits
					l_els_rep_best, l_hd_max_best, best_true_positive = list(l_els_rep), list(l_hd_max), true_positive

		return b_one_found, l_els_rep_best, l_hd_max_best


	def fine_tune(self, match_bins, match_hits):
		num_matches, num_hits = match_bins.shape[0], np.sum(match_hits)
		if num_hits < c_bitvec_learn_min_unusual or num_matches - num_hits < c_bitvec_learn_min_unusual:
			return
		match_bin_hits = match_bins[match_hits]
		match_bin_miss = match_bins[np.logical_not(match_hits)]
		# if match_bin_hits.shape[0] % 2 == 0:
		# 	match_bin_hits = match_bin_hits[:-1, :]
		if match_bin_miss.shape[0] % 2 == 0:
			match_bin_miss = match_bin_miss[:-1, :]
		# for match_bins, match_bins_other in [(match_bin_hits, match_bin_miss), (match_bin_miss, match_bin_hits)]:
		# 	for iel in range(self.__phrase2_len):
		# 		el_bins = match_bins[:, iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
		# 		el_bins_other = match_bins_other[:, iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
		# 		# figure out if odd, figure out if 1
		# 		els_rep = np.median(el_bins, axis=0)
		# 		nd_diffs = np.sum(np.not_equal(els_rep, el_bins), axis=1)
		# 		hd_max = np.max(nd_diffs)
		# 		nd_diffs_other = np.sum(np.not_equal(els_rep, el_bins_other), axis=1)
		# 		m_other = nd_diffs_other <= hd_max
		# 		del el_bins, el_bins_other, els_rep,

		# m_outside_miss = np.zeros(match_bin_hits.shape[0], dtype=np.bool)
		# for iel in range(self.__phrase2_len):
		# 	el_bins_hits = match_bin_hits[:, iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
		# 	nd_diffs_hits = np.sum(np.not_equal(l_els_rep_miss[iel], el_bins_hits), axis=1)
		# 	m_outside_miss = np.logical_or(m_outside_miss, (nd_diffs_hits > l_hd_max_miss[iel]))

		def create_reps(phrase_bins, phrase_len):
			if phrase_bins.shape[0] % 2 == 0:
				phrase_bins = phrase_bins[:-1, :]
			l_els_rep, l_hd_max = [], []
			for iel in range(phrase_len):
				el_bins = phrase_bins[:, iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
				l_els_rep.append(np.median(el_bins, axis=0))
				nd_diffs = np.sum(np.not_equal(l_els_rep[-1], el_bins), axis=1)
				l_hd_max.append(np.max(nd_diffs))
			return l_els_rep, l_hd_max

		def create_match_arr(l_els_rep, l_hd_max, phrase_bins, phrase_len):
			m_matches = np.ones(phrase_bins.shape[0], dtype=np.bool)
			for iel in range(phrase_len):
				el_bins = phrase_bins[:, iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
				nd_diffs_hits = np.sum(np.not_equal(l_els_rep[iel], el_bins), axis=1)
				m_matches = np.logical_and(m_matches, (nd_diffs_hits <= l_hd_max[iel]))
			return m_matches

		l_els_rep_miss, l_hd_max_miss = create_reps(match_bin_miss, self.__phrase2_len)
		m_outside_miss = np.logical_not(create_match_arr(	l_els_rep_miss, l_hd_max_miss,
															match_bin_hits, self.__phrase2_len))

		if self.__rule_rec[8][0] == rec_def_type.var:
			pass
		if np.sum(m_outside_miss) < c_bitvec_learn_min_unusual:
			return
		m_outside_matches = np.logical_not(create_match_arr(l_els_rep_miss, l_hd_max_miss, match_bins, self.__phrase2_len))
		num_outside_match_hits = np.sum(np.logical_and(m_outside_matches, np.array(match_hits)))
		new_score, old_score = num_outside_match_hits / np.sum(m_outside_matches).astype(np.float), num_hits / float(num_matches)
		b_add_rev_gg = False
		if new_score > old_score and (new_score - old_score) / (1. - old_score) > c_bitvec_gg_delta_on_parent:
			if self.__gg_rev_impr == [] or self.__gg_rev_impr == None:
				igg_rev, imprv_gg = \
					self.__mgr.add_new_rule(self.__ilen, self.__phrase_len, self.__result, self.__num_stages,
											self.__l_wlist_vars, self.__phrase2_ilen, self.__phrase2_len,
											self.__parent_irule)
				imprv_gg.set_imprv(self, b_rev_imprv=True, b_rnd_imprv=False)
				b_add_rev_gg = True
				self.__gg_rev_impr = imprv_gg
			elif  self.__gg_rev_impr.get_score() < new_score:
				b_add_rev_gg = True

			if b_add_rev_gg:
				self.__gg_rev_impr.set_score(new_score)
				self.__gg_rev_impr.set_els_rep(self.__l_els_rep[:self.__phrase_len] + l_els_rep_miss,
											   self.__l_hd_max[:self.__phrase_len] +  l_hd_max_miss)
				if new_score > self.__impr_score:
					self.__impr_score = new_score

		b_rnd_impr_found, l_els_rep_rnd, l_hd_max_rnd = \
			self.find_rnd_tuning(	self.__l_els_rep[self.__phrase_len:], self.__l_hd_max[self.__phrase_len:],
									match_bins, match_hits,  self.__phrase2_len)
		if b_rnd_impr_found:
			print('add an improvement child')

		# bins_outside = match_bin_hits[m_outside_miss]
		# l_els_rep_outside, l_hd_max_outside = create_reps(bins_outside, self.__phrase2_len)
		# m_outside_matches = create_match_arr(l_els_rep_outside, l_hd_max_outside, match_bins, self.__phrase2_len)
		# num_outside_matches = np.sum(np.logical_and(m_outside_matches, np.array(match_hits)))
		# if np.sum(num_outside_matches) < c_bitvec_learn_min_unusual:
		# 	return
		# new_score, old_score = num_outside_matches / np.sum(m_outside_matches).astype(np.float), num_hits / float(num_matches)
		# if new_score > old_score and (new_score - old_score) / (1. - old_score) > c_bitvec_gg_delta_on_parent:
		# 	print('add an improvement child')


		pass

	def add_phrase(self, phrase):
		self.__l_phrases.append(phrase)
		self.__num_since_learn += 1
		if self.__num_since_learn > c_bitvec_gg_learn_min:
			len_phrase_bin_db = self.__mgr.get_phrase_bin_db(self.__ilen)
			gg_bin_db = len_phrase_bin_db[self.__l_phrases]
			# m_match = np.ones(len(len_phrase_bin_db), dtype=bool)
			rule_phrase = [[rec_def_type.conn, conn_type.start]]
			for iel in range(self.__phrase_len):
				el_bins = gg_bin_db[:, iel*self.bitvec_size:(iel+1)*self.bitvec_size]
				els_rep = np.median(el_bins, axis=0)
				nd_diffs = np.not_equal(els_rep, el_bins)
				# nd_diffs = np.where(nd_diffs, np.ones_like(nd_phrase_bits_db), np.zeros_like(nd_phrase_bits_db))
				hd_max =  np.max(np.sum(nd_diffs, axis=1))
				self.__l_els_rep[iel] = els_rep
				self.__l_hd_max[iel] = hd_max
				hd_rep = np.sum(np.not_equal(self.__mgr.get_el_db(), els_rep), axis=1)
				rep_word = self.__mgr.get_word_by_id(np.argmin(hd_rep))
				rule_phrase += [[rec_def_type.like, rep_word, hd_max]]
				# el_phrase_bins = len_phrase_bin_db[:, iel*self.bitvec_size:(iel+1)*self.bitvec_size]
				# nd_phrase_diffs = np.not_equal(els_rep, el_phrase_bins)
				# m_el_match = np.sum(nd_phrase_diffs, axis=1) <= hd_max
				# m_match = np.logical_and(m_match, m_el_match)
			# self.__hit_pct = float(len(self.__l_phrases)) / np.sum(m_match)
			self.__b_formed = True
			rule_phrase += [[rec_def_type.conn, conn_type.end]]
			self.__rule_rec = rule_phrase
			self.__num_since_learn = 0

			if self.is_tested():
				self.__score = self.__num_hits / float(self.__num_stats)
				if self.__score > c_bitvec_gg_initial_valid:
					self.__status = rule_status.initial
				print('status', self.__status, 'score', self.__score, 'for rule:', rules2.gen_rec_str(self.__rule_rec) )

	def does_stmt_match_result(self, stmt):
		iel, bmatch, l_var_tbl = -1, True, []
		for el in self.__result:
			if el[0] == rec_def_type.conn:
				if el[1] in [conn_type.Insert, conn_type.Modify, conn_type.Unique]:
					continue
				else:
					bmatch = False
					break
			iel += 1
			if iel >= len(stmt):
				bmatch = False
				break
			if el[0] == rec_def_type.var:
				if stmt[iel][0] == rec_def_type.obj:
					l_var_tbl += [(el[1], True, stmt[iel][1])]
				elif stmt[iel][0] == rec_def_type.like:
					l_var_tbl += [(el[1], False, stmt[iel][1], stmt[iel][2])]
				else:
					raise ValueError('Error. Code does not consider option of stmt el being neither obj nor like')
			elif el[0] == rec_def_type.obj:
				if el[1] != stmt[iel][1]:
					bmatch = False
					break
		return bmatch, l_var_tbl

	@staticmethod
	def test_for_unexpected_double(l_test_phrases, d_var_opts, l_var_all_locs, l_istage):
		d_els = dict()
		# make sure the checking is on loc pairs and not iel of a single stage
		for istage, test_phrase in zip(l_istage, l_test_phrases):
			for iel, full_el in enumerate(test_phrase):
				if full_el[0] != rec_def_type.obj: continue
				l_pos = d_els.get(full_el[1], [])
				if l_pos == []:
					d_els[full_el[1]] = [(istage, iel)]
				else:
					# print('Warning. Code here never tested. Please debug carefully')
					for pos in l_pos:
						ivar = d_var_opts.get(pos, -1)
						if ivar == -1:
							# m_match[imatch] = False
							return True
							# btrouble = True
							# break
						else:
							var_all_locs = l_var_all_locs[ivar]
							if (istage, iel) not in var_all_locs:
								# m_match[imatch] = False
								return True
								# btrouble = True
								# break
					# if btrouble:
					# 	return True
					d_els[full_el[1]] += [(istage, iel)]
		return False


	@profile_decor
	def find_var_opts(self, l_var_opts, db_name, var_obj_parent, calc_level):
		# global a0time_tot, atime_tot, btime_tot, ctime_tot

		b_rule_works = self.__d_arg_cache.get(tuple(l_var_opts), None)
		if b_rule_works != None and b_rule_works == False:
			return None

		l_match_phrases_che, ll_match_iphrase_combos_che = self.__d_db_arg_cache.get((tuple(l_var_opts), db_name), ([], []))
		if l_match_phrases_che != []:
			return rules2.cl_var_match_opts(self, l_match_phrases_che, ll_match_iphrase_combos_che,
											var_obj_parent, calc_level+1)

		mpdb_mgr = self.__mgr.get_mpdb_mgr()
		idb = mpdb_mgr.get_idb_from_db_name(db_name)
		nd_story_bins = self.__mgr.get_mpdb_bins()
		l_story_rphrases = mpdb_mgr.get_rphrases()

		# a0time = timeit.default_timer()
		utils.profile_start('find_var_opts a0')

		# The first part of this function builds the var tables.
		# Some els have no vars, either external or intenal.
		# Some els are vars but have no reuse of the var except in a THEN claause. The are external,
		# Some els are vars only for internal (re)use.
		# Of the internal and external, some are instantiated by the rules requiring exact matches and some by
		#     matches of the tule cluases with phrases in the database

		# Start with table entry for the external vars. Not all of these are bound

		l_vars = [	nt_vars(loc=vo[0], b_bound=vo[1], b_must_bind=vo[1],
							val=vo[2], cd=None if vo[1] else vo[3], iext_var=ivo)
					for ivo, vo in enumerate(l_var_opts)]
		l_var_vals = [[vo[2]] if vo[1] else [[]] for vo in l_var_opts]

		# The table of vars is supplemented with pair-based locations (istage and iel instead of of since int loc)
		# It is also supplemented with tables for listing all locations of the var as well as a dict to get from
		#    a given location to an entry in the var table

		l_phrase_starts = [0]
		for phrase_len in self.__l_phrases_len: l_phrase_starts.append(l_phrase_starts[-1]+phrase_len)
		l_var_locs = [vo[0] for vo in l_var_opts]
		l_var_loc_pairs, d_var_opts, l_var_all_locs = [], dict(), []
		for iopt, var_loc in enumerate(l_var_locs):
			for itlen, tlen in enumerate(l_phrase_starts):
				if var_loc < tlen:
					l_var_loc_pairs.append((itlen-1, var_loc-l_phrase_starts[itlen-1]))
					l_var_all_locs.append([l_var_loc_pairs[-1]])
					d_var_opts[l_var_loc_pairs[-1]] = iopt
					break

		# bin patterns and and max hds are addded. These are set from the binding of the excternal l_var_opts
		# or from the rule, whichever is tighter. If the hd max requirements mean they do not match, the rule fails
		# right here and an None (Null) object is returned.
		# The main loop in this blocks iters over the var table of the rule itself, not the tables we just built
		# print('TBD: Must make sure that when creating a match phrase there are no repeated els. See comment 6666')
		l_matches, l_b_phrases_matched, l_match_phrases, l_match_bindings = [], [], [], []
		ll_src_pat = [	[self.__l_els_rep[l_phrase_starts[istage]+iel] for iel in range(stage_len)]
						for istage, stage_len in enumerate(self.__l_phrases_len)]
		ll_hd_max = [	[self.__l_hd_max[l_phrase_starts[istage]+iel] for iel in range(stage_len)]
						for istage, stage_len in enumerate(self.__l_phrases_len)]
		for src_istage, src_iel, dest_istage, dest_iel in self.__l_wlist_vars:
			iopt = d_var_opts.get((src_istage, src_iel), -1)
			if iopt == -1:
				iopt = len(l_vars)
				d_var_opts[(src_istage, src_iel)] = iopt
				d_var_opts[(dest_istage, dest_iel)] = iopt
				l_vars.append(nt_vars(	loc=l_phrase_starts[src_istage]+src_iel, b_bound=False,
										b_must_bind=False, val=None, cd=None))
				l_var_all_locs.append([(src_istage, src_iel), (dest_istage, dest_iel)])
				l_var_vals.append([[]])
			else:
				d_var_opts[(dest_istage, dest_iel)] = iopt
				l_var_all_locs[iopt].append((dest_istage, dest_iel))

		for iopt, var_opt in enumerate(l_vars):
			# var_opt = l_vars[iopt]
			src_istage, src_iel =  l_var_all_locs[iopt][0]
			if not var_opt.b_resolved:
				b_set_by_int = True
				int_els_rep, int_hd_max = ll_src_pat[src_istage][src_iel], ll_hd_max[src_istage][src_iel]
				if var_opt.iext_var != -1:
					ext_var_opt = l_var_opts[var_opt.iext_var]
					ext_els_rep = self.__mgr.get_el_bin(ext_var_opt[2])
					ext_hd_max = 0 if len(ext_var_opt) <= 3 else self.bitvec_size * (1. - ext_var_opt[3])
					max_of_max_hd = max(int_hd_max, ext_hd_max)
					bin_diff = np.sum(np.not_equal(int_els_rep, ext_els_rep))
					if bin_diff > max_of_max_hd:
						# a0time_tot += timeit.default_timer() - a0time
						utils.profile_end('find_var_opts a0')
						self.__d_arg_cache[tuple(l_var_opts)] = False
						return None
					if int_hd_max > ext_hd_max:
						ll_src_pat[src_istage][src_iel], ll_hd_max[src_istage][src_iel] = ext_els_rep, ext_hd_max
						b_set_by_int = False
						l_vars[iopt] = var_opt._replace(b_resolved=True)
				if b_set_by_int:
					nd_el_match_idx = np.argmax(np.sum(np.equal(self.__mgr.get_el_db(),
																int_els_rep), axis=1))
					el_word = self.__mgr.get_word_by_id(nd_el_match_idx)
					b_exact = ll_hd_max[src_istage][src_iel] == 0
					l_vars[iopt] = l_vars[iopt]._replace(	b_bound=b_exact, b_must_bind=b_exact,
															val=el_word, b_resolved=True,
															cd=1.-(float(ll_hd_max[src_istage][src_iel]) / self.bitvec_size))
					if b_exact: l_var_vals[iopt] = [el_word]
			# end if not b_resolved
		self.__d_arg_cache[tuple(l_var_opts)] = True
		# atime = timeit.default_timer()
		# a0time_tot += atime - a0time
		utils.profile_end('find_var_opts a0')
		utils.profile_start('find_var_opts a')

		for src_istage, src_iel, dest_istage, dest_iel in self.__l_wlist_vars:
			ll_src_pat[dest_istage][dest_iel] = ll_src_pat[src_istage][src_iel]
			ll_hd_max[dest_istage][dest_iel] = ll_hd_max[src_istage][src_iel]
		# end loop for var in self.__l_wlist_vars

		# It is possible for the external var not to appear in the rule var table so they are dealt with here.
		# Every var starts with a definition in the rule and the external with its hd_max must match the def with its
		#    requirements
		for iopt, (var_all_locs, one_var) in enumerate(zip(l_var_all_locs, l_vars)):
			if one_var.iext_var == -1 or one_var.b_resolved: continue
			src_istage, src_iel = var_all_locs[0]
			ext_var_opt = l_var_opts[one_var.iext_var]
			ll_src_pat[src_istage][src_iel] = self.__mgr.get_el_bin(ext_var_opt[2])
			if one_var.b_bound:
				ll_hd_max[src_istage][src_iel] = 0
			else:
				assert len(ext_var_opt) > 3, 'if the var loc is not bound, a cd must be provided'
				ll_hd_max[src_istage][src_iel] = int(self.bitvec_size * (1. - ext_var_opt[3]))
			l_vars[iopt] = one_var._replace(b_resolved=True)

		# This block aims to finish the job of building the var table by looking for any element not in the
		# var table already that has non-exact value

		for istage, phrase_len in enumerate(self.__l_phrases_len):
			for iel in range(phrase_len):
				ivar = d_var_opts.get((istage, iel), -1)
				if ivar != -1 or ll_hd_max[istage][iel] == 0: continue
				iopt = len(l_vars)
				d_var_opts[(istage, iel)] = iopt
				nd_el_match_idx = np.argmax(np.sum(np.equal(self.__mgr.get_el_db(), ll_src_pat[istage][iel]), axis=1))
				el_word = self.__mgr.get_word_by_id(nd_el_match_idx)
				l_vars.append(nt_vars(	loc=l_phrase_starts[istage]+iel, b_bound=False,
										b_must_bind=False, val=el_word, b_resolved=True,
										cd=1. - (float(ll_hd_max[istage][iel]) / self.bitvec_size)))
				l_var_all_locs.append([(istage, iel)])
				l_var_vals.append([[]])


		# btime = timeit.default_timer()
		# atime_tot += btime - atime
		utils.profile_end('find_var_opts a')
		utils.profile_start('find_var_opts b')

		# In this block I find the matches and build the options for l_vars
		# This block also contains two stages of building the list of match phrases - the possibilities of a
		# phrase that matches the rules. This contains both phrases found in the db with no open vars as well as
		# phrases with open vars or no open vars neither of which are actually in the db
		# Within this block there is creation of the parts of the phrase that do not depend on db matches and those that do
		nd_default_idb_mrk = mpdb_mgr.get_nd_idb_mrk(idb)
		l_i_null_phrases = []
		l_stage_ivars = [[] for _ in range(len(self.__l_phrases_len))]
		# The stages are the different clauses (phrases) in the rule
		for istage, phrase_len in enumerate(self.__l_phrases_len):
			nd_ilen_mrk = np.array([ilen == self.__l_phrases_ilen[istage] for ilen, _ in l_story_rphrases], dtype=np.bool)
			m_match = np.ones(nd_story_bins.shape[0], dtype=np.bool)
			m_mrks = np.logical_and(nd_default_idb_mrk, nd_ilen_mrk)
			m_match = np.logical_and(m_mrks, m_match)
			l_phrase_found = [[] for _ in range(phrase_len)]
			l_b_unbound, l_i_unbound = [False for _ in range(phrase_len)], [-1 for _ in range(phrase_len)]
			# loop through filling in els that do not require a match. Some of the els in this loop will be replaced
			# by other els if a match is actually found, That way we can complete the loop before getting to the matches
			for iel in range(phrase_len):
				# The following slows things downn. Besides the l_b_unbound can be removed once the ascii scaffoldin is removed
				iopt = d_var_opts.get((istage, iel), -1)
				src_pat, hd_max = ll_src_pat[istage][iel], ll_hd_max[istage][iel]
				if iopt == -1 or not l_vars[iopt].b_bound:
					nd_el_match_idx = np.argmax(np.sum(np.equal(self.__mgr.get_el_db(), src_pat), axis=1))
					el_word = self.__mgr.get_word_by_id(nd_el_match_idx)
				else:
					el_word = l_vars[iopt].val
				if hd_max == 0:
					l_phrase_found[iel] = [rec_def_type.obj, el_word]
				else:
					l_phrase_found[iel] = [rec_def_type.like, el_word, 1. - float(hd_max) / self.bitvec_size]
					l_b_unbound[iel], l_i_unbound[iel] = iopt != -1, iopt

				# Check for the phrase of the rule being longer than the size of the vector in the db
				# Certainly there will noth be any matches in this case
				if (iel+1)*self.bitvec_size > nd_story_bins.shape[1]:
					m_match = np.zeros(nd_story_bins.shape[0], dtype=np.bool)
					continue
				# Build the actual matches
				el_story_bins = nd_story_bins[:, iel*self.bitvec_size:(iel+1)*self.bitvec_size]
				nd_el_diffs = np.not_equal(src_pat, el_story_bins)
				m_el_match = np.sum(nd_el_diffs, axis=1) <= hd_max
				m_match = np.logical_and(m_match, m_el_match)
			# end loop for iel in range(phrase_len)
			m_match = np.logical_and(m_match, m_mrks)

			# one extra piece. Build a table of var idxs that are used for each el of the stage. At this point
			# even though we are in the middle of the stages loop we can say that we know the var table for this stage
			for ivar, (var, var_all_locs) in enumerate(zip(l_vars, l_var_all_locs)):
				if var.b_bound: continue
				for var_loc in var_all_locs:
					if var_loc[0] == istage:
						l_stage_ivars[istage].append(ivar)

			# The match marker vectors have been built but here we actually go through the success cases building match
			# phrases for each match
			l_i_null_phrases.append(len(l_match_phrases))
			l_match_phrases.append(nt_match_phrases(istage=istage, b_matched=False, phrase=l_phrase_found))
			l_match_bindings.append([istage] + [0 for _ in l_stage_ivars[istage]])
			# keeping following two lines so that calling functions can keep working
			l_matches.append(l_phrase_found)
			l_b_phrases_matched.append(False)
			for imatch, bmatch in enumerate(m_match):
				if not bmatch: continue
				l_phrase_found = self.__mgr.get_phrase(*l_story_rphrases[imatch])
				if self.test_for_unexpected_double([rules2.convert_wlist_to_phrase(l_phrase_found)], d_var_opts,
												   l_var_all_locs, [istage]):
					m_match[imatch] = False
					continue
				# if btrouble: continue
				l_match_phrases.append(nt_match_phrases(istage=istage, b_matched=True,
														phrase=rules2.convert_wlist_to_phrases([l_phrase_found])[0]))
				l_match_bindings.append([istage]+ [0 for _ in l_stage_ivars[istage]])
				for iel in range(phrase_len):
					if l_b_unbound[iel]:
						ivar = l_i_unbound[iel]
						l_bindings = l_var_vals[ivar]
						var_binding = l_phrase_found[iel]
						if var_binding in l_bindings:
							ivar_val = l_bindings.index(var_binding)
						else:
							ivar_val = len(l_bindings)
							l_bindings.append(var_binding)
						# l_match_bindings[-1].append(ivar_val)
						l_match_bindings[-1][1+l_stage_ivars[istage].index(ivar)] = ivar_val

		# end loop over stages
		# ctime = timeit.default_timer()
		# btime_tot += ctime - btime
		utils.profile_end('find_var_opts b')
		utils.profile_start('find_var_opts c')

		# In the following block, the goal is to add match phrases that bind some of the variables
		# but perhaps not all. These new phrases are extensions of the null phrase (that binds none
		# of the variables). However, we check that the phrase is not actually already in the
		# matched phrases.
		# N.B. When I speak of unbound variables, I do not refer to the variables that MUST be bound.
		# These are the var loc vars that come from the goal external to the function and the internal
		# vars that have cd of 1. that must have an exact value
		for i_null_phrase in l_i_null_phrases:
			null_match_phrase = l_match_phrases[i_null_phrase]
			istage = null_match_phrase.istage
			l_iopts, l_iel_of_binding, ll_bindings, l_stage_ivar_of_pos = [], [], [], []
			for iel in range(self.__l_phrases_len[istage]):
				iopt = d_var_opts.get((istage, iel), -1)
				if iopt == -1 or l_vars[iopt].b_bound: continue
				l_iopts.append(iopt)
				ll_bindings.append([(i,v) for i,v in enumerate(l_var_vals[iopt])])
				l_iel_of_binding.append(iel)
				l_stage_ivar_of_pos.append(l_stage_ivars[istage].index(iopt))
			# null_match_phrase = l_match_phrases[l_i_null_phrases[istage]]
			for comb in itertools.product(*ll_bindings):
				new_match_phrase = copy.deepcopy(null_match_phrase.phrase)
				b_change_made, b_change_missed, b_trouble = False, False, False
				l_new_match_bindings = [istage] + [-1 for _ in l_stage_ivars[istage]]
				for ico, comb_opt in enumerate(comb):
					if comb_opt[1] == []:
						# l_new_match_bindings.append(comb_opt[0])
						l_new_match_bindings[1+l_stage_ivar_of_pos[ico]] = comb_opt[0]
						b_change_missed = True
						continue
					# 6666 Here is where the check for el repeat should happen
					new_match_phrase[l_iel_of_binding[ico]] = [rec_def_type.obj, comb_opt[1]]
					if self.test_for_unexpected_double(	[new_match_phrase], d_var_opts,
														l_var_all_locs, [istage]):
						b_trouble = True
						break
					# l_new_match_bindings.append(comb_opt[0])
					l_new_match_bindings[1 + l_stage_ivar_of_pos[ico]] = comb_opt[0]
					b_change_made = True
				if b_trouble or not b_change_made: continue
				cand_match_phrase = null_match_phrase._replace(b_matched=not b_change_missed, phrase=new_match_phrase)
				if cand_match_phrase in l_match_phrases: continue
				l_match_phrases.append(cand_match_phrase._replace(b_matched=False))
				l_match_bindings.append(l_new_match_bindings)

		# end of i_null_phr

		# this block just cleans l_match_bindings of duplicates
		l_imatch_remove = []
		for imatch1, match_bind1 in enumerate(l_match_bindings):
			if imatch1 in l_imatch_remove: continue
			for imatch2, match_bind2 in enumerate(l_match_bindings):
				if imatch1 >= imatch2 or imatch2 in l_imatch_remove: continue
				if match_bind1 == match_bind2:
					if not l_match_phrases[imatch1].b_matched and l_match_phrases[imatch2].b_matched:
						l_imatch_remove.append(imatch1)
					else:
						l_imatch_remove.append(imatch2)

		for imatch_remove in reversed(l_imatch_remove):
			del l_match_bindings[imatch_remove]
			del l_match_phrases[imatch_remove]




		# In the following block, I create the table of possible combinations (by index) of
		# the match phrases. First I create a mapping from the general var index to the unbound var index

		l_unbound_ivars = [ivar for ivar, var in enumerate(l_vars) if not var.b_bound]
		l_ivar_unbound = [-1 for _ in l_vars]
		for iunbound, unbound_ivar in enumerate(l_unbound_ivars):
			l_ivar_unbound[unbound_ivar] = iunbound
		# l_ivar_unbound = [-1 if var.b_bound else ivar for ivar, var in enumerate(l_vars)]

		# print('TBD: You must make sure no var combo creates an el repeat othe that the var repeat itself')
		l_comb_ivals = [range(len(vals)) for vals, var in zip(l_var_vals, l_vars) if not var.b_bound]
		ll_match_iphrase_combos = []
		for comb_ivals in itertools.product(*l_comb_ivals):
			l_phrases_found, l_match_iphrase_combo, btrouble = [], [], False
			for istage in range(len(self.__l_phrases_len)):
				stage_ivars = l_stage_ivars[istage]
				search_key = [istage]
				if stage_ivars == []:
					l_stage_match_iphrase = \
						[match_iphrase for match_iphrase, match_bindings in enumerate(l_match_bindings)
								if match_bindings[0] == search_key[0]]
					assert len(l_stage_match_iphrase) == 1, 'There should only be one stage match if stage_ivars == []'
					stage_match_iphrase = l_stage_match_iphrase[0]
				else:
					for ivar in stage_ivars:
						search_key += [comb_ivals[l_ivar_unbound[ivar]]]
					# assert search_key in l_match_bindings, 'Error. Missing search key in l_match_bindings'
					if search_key not in l_match_bindings:
						btrouble = True
						break
					stage_match_iphrase = l_match_bindings.index(search_key)
				l_phrases_found.append(l_match_phrases[stage_match_iphrase].phrase)
				l_match_iphrase_combo += [stage_match_iphrase]
				if self.test_for_unexpected_double(l_phrases_found, d_var_opts,
												   l_var_all_locs, range(istage+1)):
					btrouble = True
					break
			if btrouble: continue
			ll_match_iphrase_combos += [l_match_iphrase_combo]

		# ctime_tot += timeit.default_timer()- ctime
		utils.profile_end('find_var_opts c')

		# Finally create the scores for combos of match phrases
		# l_match_phrase_scores = []
		# best_score = 0.
		# for l_match_iphrase_combo in ll_match_iphrase_combos:
		# 	score, frac = 0., 1. / len(l_match_iphrase_combo)
		# 	for iphrase in l_match_iphrase_combo:
		# 		if l_match_phrases[iphrase].b_matched: score += frac
		# 	if score > best_score: best_score = score
		# 	l_match_phrase_scores.append(score)

		# return [l_matches], [l_b_phrases_matched]


		# if l_match_phrases_che != []:
		# 	assert l_match_phrases_che == l_match_phrases and ll_match_iphrase_combos_che == ll_match_iphrase_combos, 'cache strategy failed'
		self.__d_db_arg_cache[(tuple(l_var_opts), db_name)] = (l_match_phrases, ll_match_iphrase_combos)
		return rules2.cl_var_match_opts(self, l_match_phrases, ll_match_iphrase_combos,
										var_obj_parent, calc_level+1)

	def is_a_match_one_stage(self, ilen, iphrase):
		if ilen != self.__ilen:
			return False
		len_phrase_bin_db = self.__mgr.get_phrase_bin_db(self.__ilen)
		phrase_bin = len_phrase_bin_db[iphrase]
		for iel in range(self.__phrase_len):
			phrase_el_bins = phrase_bin[iel * self.bitvec_size:(iel + 1) * self.bitvec_size]
			hd = np.sum(np.not_equal(phrase_el_bins, self.__l_els_rep[iel]))
			if hd > self.__l_hd_max[iel]:
				return False
		return True

	def is_a_match(self, ilen, iphrase):
		if self.__num_stages == 1:
			return self.is_a_match_one_stage(ilen, iphrase)
		return False

	def set_match_hits(self, match_bins, match_hits):
		if self.__match_bins == []:
			self.__match_bins = match_bins
		else:
			self.__match_bins = np.concatenate((self.__match_bins, match_bins), axis=0)
		self.__match_hits += match_hits.tolist()
		pass

	# assumes match has aaybeen confirmed. Justcheck the result
	def update_stats(self, phrase, l_results):
		self.__num_stats += 1
		if l_results == [] or l_results[0] == []:
			return
		_, new_result = rules2.replace_with_vars_in_wlist([phrase], l_results)
		if self.__result == new_result:
			self.__num_hits += 1
		if not self.__b_tested:
			if self.__num_stats > c_bitvec_gg_stats_min:
				self.__b_tested = True

	class cl_unused_mrk(object):
		d_len_to_idx = dict()
		l_story_lens = []
		eltype = None
		def __init__(self, another=None, len=-1, imatch=-1):
			self.__l_nd_unused = []
			if another == None:
				for klen, vidx in self.d_len_to_idx.iteritems():
					self.__l_nd_unused.append(np.ones(self.l_story_lens[vidx], dtype=self.eltype))
			else:
				for nd in another.__l_nd_unused:
					self.__l_nd_unused.append(np.copy(nd))
				idx = self.d_len_to_idx[len]
				self.__l_nd_unused[idx][imatch] = self.eltype(0)

		def get_unused(self, len):
			return self.__l_nd_unused[self.d_len_to_idx[len]]


	def find_matches(self, phrase, phrase_bin, mpdb_mgr, idb):
		cl_bitvec_gg.find_matches_num_calls += 1
		# start = timeit.default_timer()
		# a lot of work just ot get the type
		eltype = None
		for els_rep in self.__l_els_rep:
			if els_rep != []:
				eltype = type(els_rep[0])
				break
		assert eltype != None, 'Can\'t work with rule that has not one element preset'
		assert self.__num_stages > 1, 'function find_matches should only be called for stage 2+ rules'

		# d_story_len_refs = mpdb_mgr.get_d_story_len_refs(idb)
		nd_story_bins = self.__mgr.get_mpdb_bins()
		l_story_rphrases = mpdb_mgr.get_rphrases()
		nd_default_idb_mrk = mpdb_mgr.get_nd_idb_mrk(idb)
		l_srphrases_text = mpdb_mgr.get_srphrases_text()
		# match_pat = list(self.__l_els_rep)
		# l_hd_max = list(self.__l_hd_max)
		l_stagelens = [0] #, self.__phrase_len, self.__phrase_len + self.__phrase2_len]
		for stg_len in self.__l_phrases_len:
			l_stagelens.append(stg_len+l_stagelens[-1])

		r_num_stages = range(self.__num_stages)
		l_wlist_vars_stgs = [[] for _ in r_num_stages]
		l_l_wlist_var_dest_stgs  = [[] for _ in r_num_stages]
		l_l_src_phrase_bin_stgs = [[] for _ in r_num_stages]
		l_l_mat_pat_stgs = [[] for _ in r_num_stages]
		l_l_hd_max_stgs = [[] for _ in r_num_stages]
		l_l_src_stg = [[] for _ in r_num_stages]
		# l_l_story_refs = [[] for _ in r_num_stages]
		l_l_phrases_stgs = [[] for _ in r_num_stages]
		l_l_obj_unused_stgs = [[] for _ in r_num_stages]
		l_l_obj_imatch_stgs = [[] for _ in r_num_stages]
		d_len_to_idx, l_story_lens = dict(), []
		# for stg in r_num_stages[1:]:
		# 	stg_ilen, stg_len = self.__l_phrases_ilen[stg], self.__l_phrases_len[stg]
		# 	story_refs = d_story_len_refs.get(stg_ilen, [])
		# 	unused_idx = d_len_to_idx.get(stg_len, -1)
		# 	if unused_idx == -1:
		# 		d_len_to_idx[stg_len] = len(l_story_lens)
		# 		l_story_lens.append(len(story_refs))
		# self.cl_unused_mrk.l_story_lens = l_story_lens
		# self.cl_unused_mrk.d_len_to_idx = d_len_to_idx
		# self.cl_unused_mrk.eltype = eltype


		# 	if story_bin == []: return []
		# 	l_nd_used_stgs.append(np.ones(story_bin.shape[0], dtype=eltype))
		for src_istage, src_iel, dest_istage, dest_iel  in self.__l_wlist_vars:
			l_wlist_vars_stgs[src_istage] += [[src_iel, dest_istage, dest_iel]]
			for rem_dest_stage in range(dest_istage, self.__num_stages):
				l_l_wlist_var_dest_stgs[rem_dest_stage].append((src_istage, src_iel, dest_istage, dest_iel))

		l_l_src_phrase_bin_stgs[0] = [phrase_bin]
		l_l_mat_pat_stgs[0] = [list(self.__l_els_rep)]
		l_l_hd_max_stgs[0] = [list(self.__l_hd_max)]
		l_l_phrases_stgs[0] = [phrase]
		l_l_obj_unused_stgs[0] = [np.ones(nd_story_bins.shape[0], dtype=np.bool)] # [self.cl_unused_mrk()]
		l_match_paths, b_some_found = [], False
		for stg in r_num_stages[:-1]:
			stg_ilen = self.__l_phrases_ilen[stg+1]
			# story_refs = d_story_len_refs.get(stg_ilen, [])
			# nd_story_bins, l_story_rphrases, nd_default_idb_mrk
			nd_ilen_mrk = np.array([ilen == stg_ilen for ilen, _ in l_story_rphrases], dtype=np.bool)
			if not np.any(nd_ilen_mrk): break
			# bin_dn = self.__mgr.get_phrase_bin_db(stg_ilen)
			# story_bin = bin_dn[story_refs]

			for i_stg_phrase, stg_phrase in enumerate(l_l_src_phrase_bin_stgs[stg]):

				l_back_match_root = [l_l_phrases_stgs[stg][i_stg_phrase]]
				if stg > 0:
					src_stg = l_l_src_stg[stg][i_stg_phrase]
					for stg2 in reversed(range(stg)):
						l_back_match_root += [l_l_phrases_stgs[stg2][src_stg]]
						if stg2 > 0: src_stg = l_l_src_stg[stg2][src_stg]
				l_back_match_root.reverse()

				exdb_ref = self.__d_exdb.get(stg+1, ())
				if exdb_ref == ():
					idb_mrk = nd_default_idb_mrk
				else:
					ex_db_name = l_back_match_root[exdb_ref[0]][exdb_ref[1]]
					ex_idb = mpdb_mgr.get_idb_from_db_name(ex_db_name)
					idb_mrk = mpdb_mgr.get_nd_idb_mrk(ex_idb)

					# exdb_story_refs = self.__mgr.get_story_refs(ex_db_name, stg_ilen)
					# story_bin = bin_dn[story_refs]

				for src_iel, dest_istage, dest_iel in l_wlist_vars_stgs[stg]:
				# src_base_len = l_stagelens[dest_istage]
					dest_base_len = l_stagelens[dest_istage]
					src_pat = stg_phrase[src_iel*self.bitvec_size:(src_iel+1)*self.bitvec_size].astype(eltype)
					# if src_istage == 0:
					# else:
					# assert False, 'Not coded yet phrases that depend on earlier els in phrase or earlier phrases'
					l_l_mat_pat_stgs[stg][i_stg_phrase][dest_base_len+dest_iel] = src_pat
					l_l_hd_max_stgs[stg][i_stg_phrase][dest_base_len+dest_iel] = 0

				# obj_unused = l_l_obj_unused_stgs[stg][i_stg_phrase]
				m_unused = np.copy(l_l_obj_unused_stgs[stg][i_stg_phrase])
				m_match = np.ones(nd_story_bins.shape[0], dtype=np.bool)
				for iel in range(self.__l_phrases_len[stg+1]):
					src_bin = l_l_mat_pat_stgs[stg][i_stg_phrase][l_stagelens[stg+1] + iel]
					el_story_bins = nd_story_bins[:, iel*self.bitvec_size:(iel+1)*self.bitvec_size]
					nd_el_diffs = np.not_equal(src_bin, el_story_bins)
					m_el_match = np.sum(nd_el_diffs, axis=1) <= l_l_hd_max_stgs[stg][i_stg_phrase][l_stagelens[stg+1] + iel]
					m_match = np.logical_and(m_match, m_el_match)

				m_mrks = np.logical_and(np.logical_and(idb_mrk, nd_ilen_mrk), m_unused)
				# m_match = np.logical_and(obj_unused.get_unused(self.__l_phrases_len[stg+1]), m_match)
				m_match = np.logical_and(m_mrks, m_match)

				for imatch, bmatch in enumerate(m_match.tolist()):
					if not bmatch: continue
					# if exdb_ref != () and story_refs[imatch] not in exdb_story_refs:
					# 	m_match[imatch] = False
					# 	continue
					l_match_path_phrases = l_back_match_root + [self.__mgr.get_phrase(*l_story_rphrases[imatch])] # reversed(l_back_match)
					l_wlist_vars, _ = rules2.replace_with_vars_in_wlist(l_match_path_phrases, [])
					if l_wlist_vars != l_l_wlist_var_dest_stgs[stg+1]:
						m_match[imatch] = False
						continue
					m_unused[imatch] = False
					match_bin = nd_story_bins[imatch]
					l_l_src_stg[stg+1].append(i_stg_phrase)
					l_l_src_phrase_bin_stgs[stg+1].append(match_bin)
					l_l_mat_pat_stgs[stg+1].append(l_l_mat_pat_stgs[stg][i_stg_phrase])
					l_l_hd_max_stgs[stg+1].append(l_l_hd_max_stgs[stg][i_stg_phrase])
					# l_l_story_refs[stg+1].append(l_story_rphrases[imatch][1])
					l_l_phrases_stgs[stg+1].append(l_match_path_phrases[-1])
					# l_l_obj_unused_stgs[stg + 1].append(self.cl_unused_mrk(obj_unused, self.__l_phrases_len[stg+1], imatch))
					l_l_obj_unused_stgs[stg + 1].append(m_unused)
					l_l_obj_imatch_stgs[stg+1].append(imatch)

		stg, l_imatches = r_num_stages[-1], []
		# m_match_last_stage = np.zeros(story_bin.shape[0], dtype=bool)
		for isrc, src_stg in  enumerate(l_l_src_stg[stg]):
			b_some_found = True
			match_path = [l_l_phrases_stgs[stg][isrc]]
			for stg2 in reversed(r_num_stages[:-1]):
				match_path += [l_l_phrases_stgs[stg2][src_stg]]
				if stg2 > 0: src_stg = l_l_src_stg[stg2][src_stg]
			l_match_paths.append(match_path[::-1]) # reverses the list and returns it in the same step
			# m_match_last_stage[l_l_obj_imatch_stgs[stg]] = True
			l_imatches.append(l_l_obj_imatch_stgs[stg][isrc])

		# cl_bitvec_gg.find_matches_time_sum += (timeit.default_timer() - start)
		# cl_bitvec_gg.find_matches_time_count += 1
		# time_now = (timeit.default_timer() - cl_bitvec_gg.test_start_time)
		return l_match_paths, l_imatches



	def make_result(self, phrase_arr):
		def get_var_src(var_src):
			len_so_far = 0
			for irphrase, rphrase in enumerate(phrase_arr):
				if var_src < len_so_far + len(rphrase):
					ipos = var_src - len_so_far
					src_word = rphrase[ipos]
					break
				len_so_far += len(rphrase)
			return src_word

		result = []
		for irel, rel in enumerate(self.__result):
			if rel[0] == rec_def_type.var:
				src_word = get_var_src(rel[1])
				result += [[rec_def_type.obj, src_word]]
				if len(rel) > 2:
					result[-1].append(rel[2])
			elif rel[0] == rec_def_type.conn \
					and rel[1] in [conn_type.Insert, conn_type.Modify, conn_type.Unique, conn_type.Broadcast, conn_type.Remove] \
					and len(rel) > 2:
				result += [rel[:2] + [get_var_src(e) for e in rel[2:]]]
			else:
				result.append(rel)
		return result

	def filter_overmatch(self, phrase, story_refs, m_matches):
		for imatch, bmatch in enumerate(m_matches.tolist()):
			if not bmatch:
				continue
			match_phrase = self.__mgr.get_phrase(self.__phrase2_ilen, story_refs[imatch])
			l_wlist_vars, new_result = rules2.replace_with_vars_in_wlist([phrase, match_phrase], [])
			if l_wlist_vars != self.__l_wlist_vars:
				m_matches[imatch] = False
				continue
		# return m_matches

	def update_stats_stage_2(self, l_match_paths, l_imatches, num_story_refs, l_results):
		m_matches, m_hits = np.zeros(num_story_refs, dtype=bool), np.zeros(num_story_refs, dtype=bool)
		for imatch, match_path in zip(l_imatches, l_match_paths):
			self.__num_stats += 1
			m_matches[imatch] = True
			_, new_result = rules2.replace_with_vars_in_wlist(match_path, l_results)
			if self.__result == new_result:
				self.__num_hits += 1
				m_hits[imatch] = True
		if not self.__b_tested:
			if self.__num_stats > c_bitvec_gg_stats_min:
				self.__b_tested = True
		return m_matches, m_hits


	def update_stats_stage_2_old(self, phrase, story_refs, m_matches, l_results):
		m_hits = np.zeros(m_matches.shape[0], dtype=bool)
		for imatch, bmatch in enumerate(m_matches.tolist()):
			if not bmatch:
				continue
			match_phrase = self.__mgr.get_phrase(self.__phrase2_ilen, story_refs[imatch])
			l_wlist_vars, new_result = rules2.replace_with_vars_in_wlist([phrase, match_phrase], l_results)
			if l_wlist_vars != self.__l_wlist_vars:
				m_matches[imatch] = False
				continue
			self.__num_stats += 1
			if l_results == [] or l_results[0] == []:
				x = 2
				continue
			if self.__result == new_result:
				self.__num_hits += 1
				m_hits[imatch] = True
			else:
				x = 1
				pass

		if not self.__b_tested:
			if self.__num_stats > c_bitvec_gg_stats_min:
				self.__b_tested = True
		return m_hits

	def update_bin_for_word(self, iword, el_bin):
		self.__l_els_rep[iword] = el_bin


