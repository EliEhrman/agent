"""
Descended from phrases.py

THis module seeks to add to the dictionary bitvec as new words come in

The skip representation will be replaced by a mask on the input for the unknown word

"""
from __future__ import print_function
import csv
import random
import sys
import copy
import os
from os.path import expanduser
from shutil import copyfile
import itertools
import timeit
import collections

import numpy as np

import rules2
from rules2 import conn_type
from rules2 import rec_def_type
from rules2 import nt_vars
from rules2 import nt_match_phrases
# import els
# import makerecs as mr
# import bitvec_rf


# fnt = 'orders_success.txt'
# fnt = '~/tmp/adv_phrase_freq.txt'
# fnt_dict = '~/tmp/adv_bin_dict.txt'


class Enum(set):
	def __getattr__(self, name):
		if name in self:
			return name
		raise AttributeError


rule_status = Enum([	'untried', 'initial', 'perfect', 'expands', 'perfect_block', 'blocks',
						'partial_expand', 'partial_block', 'irrelevant', 'mutant', 'endpoint'])

c_bitvec_size = 16
# c_min_bits = 3
# c_max_bits = 20
# c_num_replicate_missing = 5
c_bitvec_ham_winners_fraction = 32
# c_num_iters = 10000 # 300000
# c_num_skip_phrases_fraction = 0.1
# c_init_len = 4000
c_bitvec_move_rnd = 0.5
c_bitvec_move_rnd_change = 0.02
c_bitvec_min_frctn_change  = 0.001
c_bitvec_max_frctn_change  = 0.01
# c_b_init_db = False
# c_save_init_db_every = 100
c_bitvec_neibr_divider_offset = 5 # Closeness of neighbours factor
# c_add_batch = 400
# c_add_fix_iter = 20
c_bitvec_min_len_before_learn = 100

c_bitvec_gg_learn_min = 30 #100 # must be even
c_bitvec_gg_stats_min = 30 # 100
c_bitvec_gg_initial_valid = 0.3
c_bitvec_gg_delta_on_parent = .2
c_bitvec_learn_min_unusual = 9 # 23
c_bitvec_finetune_num_rnds = 10  # type: int
c_bitvec_rnd_hd_max = 3


assert c_bitvec_gg_learn_min % 2 == 0, 'c_bitvec_gg_learn_min must be even'

tdown = lambda l: tuple([tuple(li) for li in l])

total_time = 0

def bv_time_decor(fn):
	def wr(*args, **kwargs):
		global total_time
		s = timeit.default_timer()
		r = fn(*args, **kwargs)
		total_time += timeit.default_timer() - s
		return r
	return wr


class cl_bitvec_gg(object):
	find_matches_num_calls = 0
	find_matches_time_sum = 0.
	find_matches_time_count = 0.
	test_start_time = timeit.default_timer()


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
		self.__l_hd_max = [c_bitvec_size for _ in range(phrase_len)]
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
			self.__l_hd_max += [c_bitvec_size for _ in range(self.__l_phrases_len[stg])]


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
			phrase_len = gg_bin_db.shape[1] / c_bitvec_size
			m_match = np.ones(len(len_phrase_bin_db), dtype=bool)
			for iel in range(phrase_len):
				var_pos_dict[(istage, iel)] = len(rule_phrase)
				if (istage, iel) in l_dest_var_pos: # this is a var dest and so not compared on
					ivar = l_dest_var_pos.index((istage, iel))
					src_istage, src_ipos, _, _ = self.__l_wlist_vars[ivar]
					rule_phrase += [[rec_def_type.var, var_pos_dict[(src_istage, src_ipos)]]]
					continue
				el_bins = gg_bin_db[:, iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
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
			l_els_rep[riel] = phrase_bins[riphrase, riel * c_bitvec_size:(riel + 1) * c_bitvec_size].astype(np.float)
			l_hd_max[riel] = random.randint(0, c_bitvec_rnd_hd_max)

			for iel in range(phrase_len):
				if l_els_rep[iel] == []:
					continue
				el_bins = phrase_bins[:, iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
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
		# 		el_bins = match_bins[:, iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
		# 		el_bins_other = match_bins_other[:, iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
		# 		# figure out if odd, figure out if 1
		# 		els_rep = np.median(el_bins, axis=0)
		# 		nd_diffs = np.sum(np.not_equal(els_rep, el_bins), axis=1)
		# 		hd_max = np.max(nd_diffs)
		# 		nd_diffs_other = np.sum(np.not_equal(els_rep, el_bins_other), axis=1)
		# 		m_other = nd_diffs_other <= hd_max
		# 		del el_bins, el_bins_other, els_rep,

		# m_outside_miss = np.zeros(match_bin_hits.shape[0], dtype=np.bool)
		# for iel in range(self.__phrase2_len):
		# 	el_bins_hits = match_bin_hits[:, iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
		# 	nd_diffs_hits = np.sum(np.not_equal(l_els_rep_miss[iel], el_bins_hits), axis=1)
		# 	m_outside_miss = np.logical_or(m_outside_miss, (nd_diffs_hits > l_hd_max_miss[iel]))

		def create_reps(phrase_bins, phrase_len):
			if phrase_bins.shape[0] % 2 == 0:
				phrase_bins = phrase_bins[:-1, :]
			l_els_rep, l_hd_max = [], []
			for iel in range(phrase_len):
				el_bins = phrase_bins[:, iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
				l_els_rep.append(np.median(el_bins, axis=0))
				nd_diffs = np.sum(np.not_equal(l_els_rep[-1], el_bins), axis=1)
				l_hd_max.append(np.max(nd_diffs))
			return l_els_rep, l_hd_max

		def create_match_arr(l_els_rep, l_hd_max, phrase_bins, phrase_len):
			m_matches = np.ones(phrase_bins.shape[0], dtype=np.bool)
			for iel in range(phrase_len):
				el_bins = phrase_bins[:, iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
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
				el_bins = gg_bin_db[:, iel*c_bitvec_size:(iel+1)*c_bitvec_size]
				els_rep = np.median(el_bins, axis=0)
				nd_diffs = np.not_equal(els_rep, el_bins)
				# nd_diffs = np.where(nd_diffs, np.ones_like(nd_phrase_bits_db), np.zeros_like(nd_phrase_bits_db))
				hd_max =  np.max(np.sum(nd_diffs, axis=1))
				self.__l_els_rep[iel] = els_rep
				self.__l_hd_max[iel] = hd_max
				hd_rep = np.sum(np.not_equal(self.__mgr.get_el_db(), els_rep), axis=1)
				rep_word = self.__mgr.get_word_by_id(np.argmin(hd_rep))
				rule_phrase += [[rec_def_type.like, rep_word, hd_max]]
				# el_phrase_bins = len_phrase_bin_db[:, iel*c_bitvec_size:(iel+1)*c_bitvec_size]
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

	def find_var_opts(self, l_var_opts, db_name, var_obj_parent, calc_level):
		mpdb_mgr = self.__mgr.get_mpdb_mgr()
		idb = mpdb_mgr.get_idb_from_db_name(db_name)
		nd_story_bins = self.__mgr.get_mpdb_bins()
		l_story_rphrases = mpdb_mgr.get_rphrases()

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
			var_opt = l_vars[iopt]
			if not var_opt.b_resolved:
				b_set_by_int = True
				int_els_rep, int_hd_max = ll_src_pat[src_istage][src_iel], ll_hd_max[src_istage][src_iel]
				if var_opt.iext_var != -1:
					ext_var_opt = l_var_opts[var_opt.iext_var]
					ext_els_rep = self.__mgr.get_el_bin(ext_var_opt[2])
					ext_hd_max = 0 if len(ext_var_opt) <= 3 else c_bitvec_size * (1. - ext_var_opt[3])
					max_of_max_hd = max(int_hd_max, ext_hd_max)
					bin_diff = np.sum(np.not_equal(int_els_rep, ext_els_rep))
					if bin_diff > max_of_max_hd:
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
															cd=1.-(float(ll_hd_max[src_istage][src_iel]) / c_bitvec_size))
					if b_exact: l_var_vals[iopt] = [el_word]
			# end if not b_resolved
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
				ll_hd_max[src_istage][src_iel] = int(c_bitvec_size * (1. - ext_var_opt[3]))
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
										cd=1. - (float(ll_hd_max[istage][iel]) / c_bitvec_size)))
				l_var_all_locs.append([(istage, iel)])
				l_var_vals.append([[]])



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
					l_phrase_found[iel] = [rec_def_type.like, el_word, 1. - float(hd_max) / c_bitvec_size]
					l_b_unbound[iel], l_i_unbound[iel] = iopt != -1, iopt

				# Check for the phrase of the rule being longer than the size of the vector in the db
				# Certainly there will noth be any matches in this case
				if (iel+1)*c_bitvec_size > nd_story_bins.shape[1]:
					m_match = np.zeros(nd_story_bins.shape[0], dtype=np.bool)
					continue
				# Build the actual matches
				el_story_bins = nd_story_bins[:, iel*c_bitvec_size:(iel+1)*c_bitvec_size]
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
				l_match_bindings.append([istage]) # + [0 for _ in l_stage_ivars[istage]])
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
						l_match_bindings[-1].append(ivar_val)
		# end loop over stages
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
			l_iopts, l_iel_of_binding, ll_bindings = [], [], []
			for iel in range(self.__l_phrases_len[istage]):
				iopt = d_var_opts.get((istage, iel), -1)
				if iopt == -1 or l_vars[iopt].b_bound: continue
				l_iopts.append(iopt)
				ll_bindings.append([(i,v) for i,v in enumerate(l_var_vals[iopt])])
				l_iel_of_binding.append(iel)
			# null_match_phrase = l_match_phrases[l_i_null_phrases[istage]]
			for comb in itertools.product(*ll_bindings):
				new_match_phrase = copy.deepcopy(null_match_phrase.phrase)
				b_change_made, b_change_missed, l_new_match_bindings, b_trouble = False, False, [istage], False
				for ico, comb_opt in enumerate(comb):
					if comb_opt[1] == []:
						l_new_match_bindings.append(comb_opt[0])
						b_change_missed = True
						continue
					# 6666 Here is where the check for el repeat should happen
					new_match_phrase[l_iel_of_binding[ico]] = [rec_def_type.obj, comb_opt[1]]
					if self.test_for_unexpected_double(	[new_match_phrase], d_var_opts,
														l_var_all_locs, [istage]):
						b_trouble = True
						break
					l_new_match_bindings.append(comb_opt[0])
					b_change_made = True
				if b_trouble or not b_change_made: continue
				cand_match_phrase = null_match_phrase._replace(b_matched=not b_change_missed, phrase=new_match_phrase)
				if cand_match_phrase in l_match_phrases: continue
				l_match_phrases.append(cand_match_phrase._replace(b_matched=False))
				l_match_bindings.append(l_new_match_bindings)

		# end of i_null_phr

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
		return rules2.cl_var_match_opts(self, l_match_phrases, ll_match_iphrase_combos,
										var_obj_parent, calc_level+1)

	def is_a_match_one_stage(self, ilen, iphrase):
		if ilen != self.__ilen:
			return False
		len_phrase_bin_db = self.__mgr.get_phrase_bin_db(self.__ilen)
		phrase_bin = len_phrase_bin_db[iphrase]
		for iel in range(self.__phrase_len):
			phrase_el_bins = phrase_bin[iel * c_bitvec_size:(iel + 1) * c_bitvec_size]
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
					src_pat = stg_phrase[src_iel*c_bitvec_size:(src_iel+1)*c_bitvec_size].astype(eltype)
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
					el_story_bins = nd_story_bins[:, iel*c_bitvec_size:(iel+1)*c_bitvec_size]
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


class cl_bitvec_mgr(object):
	def __init__(self, phrase_freq_fnt, bitvec_dict_fnt):
		d_words, nd_bit_db, s_word_bit_db, l_els = load_word_db(bitvec_dict_fnt)
		# freq_tbl, s_phrase_lens = load_order_freq_tbl(fnt)
		# init_len = c_init_len  # len(freq_tbl) / 2
		# d_words, l_word_counts, l_word_phrase_ids = create_word_dict(freq_tbl, init_len)
		num_ham_winners = len(d_words) / c_bitvec_ham_winners_fraction
		score_hd_output_bits.num_ham_winners = num_ham_winners
		num_uniques = len(d_words)
		# nd_bit_db = np.zeros((num_uniques, c_bitvec_size), dtype=np.uint8)
		# s_word_bit_db = set()
		# self.__s_phrase_lens= s_phrase_lens
		self.__l_word_counts = [0 for _ in xrange(num_uniques)] # l_word_counts
		self.__l_word_phrase_ids = [[] for _ in xrange(num_uniques)]
		self.__l_word_change_db = [[[0.0 for _ in xrange(c_bitvec_size)], 0.0] for _ in self.__l_word_counts]
		self.__l_word_fix_num = [-1 for _ in xrange(num_uniques)]
		self.__d_lens = dict() # {phrase_len: ilen for ilen, phrase_len in enumerate(s_phrase_lens)}

		self.__l_phrases = [] # list of len lists for each ilen there is a list containing the phrase all ilen, iphrase in program ref this list. Also called rphrase# [[] for _ in s_phrase_lens]
		self.__map_phrase_to_rphrase = dict()
		self.__d_words = d_words
		self.__phrase_bin_db = []
		self.__nd_el_bin_db = nd_bit_db
		self.__s_word_bit_db = s_word_bit_db
		self.__l_all_phrases = []
		self.__l_results = [] # alligned to all_phrases
		self.__d_gg = dict()
		self.__l_ggs = []
		self.__rule_stages = 1
		self.__d_gg2 = dict() # for two stage rules
		self.__l_els = l_els

		self.__l_fixed_rules = []
		self.__l_rule_names = []
		self.__d_word_in_fixed_rule = dict()
		self.__d_fr_categories = dict()
		self.__mpdb_mgr = None
		self.__mpdb_bins = [] # np.zeros(shape=(0, 0),dtype=np.uint8)  # 2D np array holding all bitvecs for all phrases in story held by mpdb

	def combine_templates(self, templ1, templ2):
		if len(templ2) != len(templ2): return []
		ret = []
		for el1, el2 in zip(templ1, templ2):
			if el1[0] not in [rec_def_type.obj, rec_def_type.like]: return []
			if el2[0] not in [rec_def_type.obj, rec_def_type.like]: return []
			if el1[0] == el2[0] and el1[0] == rec_def_type.like: return []
			if el1[0] == el2[0] and el1[0] == rec_def_type.obj:
				if el1[1] != el2[1]:
					return []
				ret.append(el1[1])
				continue

			if el1[0] == rec_def_type.like:
				tel, el, cd_max = el1[1], el2[1], el1[2]
			else:
				tel, el, cd_max = el2[1], el1[1], el2[2]

			hd_max = int(c_bitvec_size * (1. - cd_max))

			el_bin = self.__nd_el_bin_db[self.__d_words[el]]
			tel_bin = self.__nd_el_bin_db[self.__d_words[tel]]
			if np.sum(np.not_equal(el_bin, tel_bin)) <= hd_max:
				ret.append(el)

		return ret


	def add_mpdb_bins(self, ilen, iphrase):
		bin_db = self.get_phrase_bin_db(ilen)
		bins = bin_db[iphrase]
		if self.__mpdb_bins == []:
			self.__mpdb_bins = np.expand_dims(bins,axis=0)
			return
		if bins.shape[0] > self.__mpdb_bins.shape[1]:
			grow = bins.shape[0] - self.__mpdb_bins.shape[1]
			self.__mpdb_bins  = np.pad(self.__mpdb_bins, ((0,0), (0, grow)), 'constant')
		elif bins.shape[0] < self.__mpdb_bins.shape[1]:
			grow = self.__mpdb_bins.shape[1] - bins.shape[0]
			bins = np.pad(bins, (0, grow), 'constant')
		self.__mpdb_bins = np.vstack((self.__mpdb_bins, bins))
		# self.debug_test_mpdb_bins()

		pass


	def debug_test_mpdb_bins(self):
		l_rphrases = self.__mpdb_mgr.get_rphrases()
		for irphrase, rphrase in enumerate(l_rphrases):
			ilen, iphrase = rphrase
			bin_db = self.get_phrase_bin_db(ilen)
			bins = bin_db[iphrase]
			assert np.array_equal(self.__mpdb_bins[irphrase][:bins.shape[0]], bins), 'self.__mpdb_bins does not match src'


	def cleanup_mpdb_bins(self, l_keep):
		# l_keep is the indexes of the current version to keep
		self.__mpdb_bins = self.__mpdb_bins[l_keep]
		self.debug_test_mpdb_bins()


	def update_mpdb_bins(self, iupdate, rphrase):
		new_bin = self.get_phrase_bin(*rphrase)
		if new_bin.shape[0] < self.__mpdb_bins.shape[1]:
			grow = self.__mpdb_bins.shape[1] - new_bin.shape[0]
			self.__mpdb_bins[iupdate] = np.pad(new_bin, (0, grow), 'constant')


	def clear_mpdb_bins(self):
		self.__mpdb_bins = []


	def get_mpdb_bins(self):
		return self.__mpdb_bins

	def set_mpdb_mgr(self, mpdb_mgr):
		self.__mpdb_mgr = mpdb_mgr

	def get_mpdb_mgr(self):
		return self.__mpdb_mgr

	def add_fixed_rule(self, rule_rec, rule_category, rule_name):
		if rule_rec == [] or rule_rec[0] == [] or rule_rec[0][1] != conn_type.IF:
			raise ValueError('Error. Trying to add ill-formed rule to bitvec mgr')
		then_el = [rec_def_type.conn, conn_type.THEN]
		if then_el not in rule_rec:
			raise ValueError('Error. Trying to add ill-formed rule to bitvec mgr')
		then_idx = rule_rec.index(then_el)
		rule_arr = rules2.make_rule_arr(rule_rec[1:then_idx])
		# if len(rule_arr) > 2:
		# 	print('testing')
		# 	# raise ValueError('Error. For now, no longer than 2-stage rules may be added to bitvec mgr')

		def get_ilen(phrase_len):
			ilen = self.__d_lens.get(phrase_len, -1)
			if ilen == -1:
				ilen = len(self.__l_phrases)
				self.__d_lens[phrase_len] = ilen
				self.__l_phrases.append([])
				self.__phrase_bin_db.append([])
			return ilen

		phrase_len  = len(rule_arr[0]) - 1
		phrase_ilen = get_ilen(phrase_len)
		l_phrases_len, l_phrases_ilen = [phrase_len], [phrase_ilen]
		l_rrec_len = [0, phrase_len]
		l_wlist_vars, l_els_rep,  = [], [[] for _ in xrange(phrase_len)]
		if len(rule_arr) > 1:
			phrase2_len = len(rule_arr[1]) - 1
			phrase2_ilen = get_ilen(phrase2_len)
			for rarr in rule_arr[1:]:
				plen = len(rarr)-1
				l_phrases_len.append(plen)
				l_phrases_ilen.append(get_ilen(plen))
				l_rrec_len += [l_rrec_len[-1]+plen]
				l_els_rep += [[] for _ in xrange(plen)]
			pos_counter_start = 1
		else:
			phrase2_len, phrase2_ilen, parent_irule, pos_counter_start = -1, -1, -1, 0

		rule_arr_pos, counter = [], pos_counter_start
		map_rec_to_list_pos = dict()
		for irrec, rrec in enumerate(rule_arr):
			rule_arr_pos.append(2 if irrec == 0 else rule_arr_pos[-1] + len(rule_arr[irrec])+1)
			for iel, el in enumerate(rrec):
				counter += 1
				map_rec_to_list_pos[counter] = (irrec, iel-1)
			counter += 1

		d_exdb = dict()
		for iarr, rarr in enumerate(rule_arr[1:]):
			if len(rarr[0]) > 2:
				src_var = map_rec_to_list_pos.get(rarr[0][2], ())
				if src_var != ():
					d_exdb[iarr+1] = src_var

		l_hd_max = [c_bitvec_size for _ in l_els_rep]
		result = []
		for iel, el in enumerate(rule_rec):
			if iel >= then_idx:
				if el[0] == rec_def_type.var:
					istage, ipos = map_rec_to_list_pos[el[1]]
					result.append([el[0], l_rrec_len[istage] + ipos])
					if len(el) > 2 and el[2] == conn_type.replace_with_next:
						result[-1].append(True)
				elif el[0] == rec_def_type.conn \
						and el[1] in [conn_type.Insert, conn_type.Modify, conn_type.Broadcast,
									  conn_type.Unique, conn_type.Remove, conn_type.start] \
						and len(el) > 2:
					result.append(el[0:2])
					for e in el[2:]:
						istage, ipos = map_rec_to_list_pos[e]
						result[-1] += [l_rrec_len[istage] + ipos]
				elif el[0] == rec_def_type.obj:
					result.append(el[0:2])
					if len(el) > 2 and el[2] == conn_type.replace_with_next:
						result[-1].append(True)
				elif el[1] != conn_type.THEN:
					result.append(el)
			elif el[0] == rec_def_type.var:
				istage, ipos = map_rec_to_list_pos[iel]
				l_wlist_vars.append(map_rec_to_list_pos[el[1]] + (istage, ipos))
				l_els_rep[l_rrec_len[istage] + ipos] = [0 for _ in xrange(c_bitvec_size)]
			elif el[0] == rec_def_type.like:
				istage, ipos = map_rec_to_list_pos[iel]
				word = el[1]
				word_idx = self.check_or_add_word(word)
				el_pos = l_rrec_len[istage] + ipos
				word_idx_data = (len(self.__l_fixed_rules), el_pos)
				l_pos_data = self.__d_word_in_fixed_rule.get(word, [])
				l_pos_data.append(word_idx_data)
				self.__d_word_in_fixed_rule[word] = l_pos_data
				l_els_rep[el_pos] = self.__nd_el_bin_db[self.__d_words[word]]
				l_hd_max[el_pos] = int(c_bitvec_size * (1. - el[2]))
				# pass

		# pass
		fixed_rule = cl_bitvec_gg(	self, phrase_ilen, phrase_len, result, num_stages=len(rule_arr),
									l_wlist_vars=l_wlist_vars, phrase2_ilen=phrase2_ilen, phrase2_len=phrase2_len,
									parent_irule=-1, l_phrases_len=l_phrases_len, l_phrases_ilen=l_phrases_ilen)
		fixed_rule.set_els_rep(l_els_rep, l_hd_max)
		fixed_rule.set_formed_and_tested(bformed=True, btested=True)
		fixed_rule.set_rule_rec(rule_rec)
		fixed_rule.set_exdb(d_exdb)
		fixed_rule.set_name(rule_name)
		l_cat_rules = self.__d_fr_categories.get(rule_category, [])
		l_cat_rules.append(len(self.__l_fixed_rules))
		self.__d_fr_categories[rule_category] = l_cat_rules
		self.__l_fixed_rules.append(fixed_rule)
		self.__l_rule_names.append(rule_name)



	def increase_rule_stages(self):
		self.__rule_stages += 1

	def get_phrase_bin(self, ilen, iphrase):
		return self.__phrase_bin_db[ilen][iphrase]

	def get_phrase_bin_db(self, ilen):
		return self.__phrase_bin_db[ilen]

	def get_phrase(self, ilen, iphrase):
		return self.__l_phrases[ilen][iphrase]

	def get_el_db(self):
		return self.__nd_el_bin_db

	def get_el_bin(self, word):
		return self.__nd_el_bin_db[self.__d_words[word]]

	def get_word_by_id(self, iel):
		return self.__l_els[iel]

	def match_el_to_like(self, el, like_rep, cosine_dist):
		hd_max = c_bitvec_size * (1.0 - cosine_dist)
		el_bin, rep_bin = self.get_el_bin(el), self.get_el_bin(like_rep)
		return np.sum(np.not_equal(el_bin, rep_bin)) <= hd_max

	def add_phrase(self, phrase, phase_data):
		ilen, iphrase = self.__add_phrase(phrase, phase_data)
		# self.__l_all_phrases.append((phase_data, ilen, iphrase))
		return ilen, iphrase

	def __add_phrase(self, phrase, phase_data):
		story_id, story_loop_stage, eid = phase_data
		bfound = False
		rphrase = self.__map_phrase_to_rphrase.get(tuple(phrase), ())
		if rphrase != ():
			return rphrase

		# for iiphrase, phrase_data in reversed(list(enumerate(self.__l_all_phrases))):
		# 	phase_data2, ilen2, iphrase2 = phrase_data
		# 	if phase_data2 != phase_data:
		# 		break
		# 	phrase2 = self.__l_phrases[ilen2][iphrase2]
		# 	if phrase2 == phrase:
		# 		ilen, iphrase = ilen2, iphrase2
		# 		bfound = True
		# 		break
		# if not  bfound:

		self.__nd_el_bin_db, ilen, iphrase = \
			self.keep_going(phrase)
		# N.B! Despite our earlier plans, we are not
		self.__l_all_phrases.append((phase_data, ilen, iphrase))

		return ilen, iphrase

	def get_story_refs(self, ex_db_name, stg_ilen):
		assert False, 'deprecated?'
		return self.__mpdb_mgr.get_story_refs(ex_db_name, stg_ilen)

	def get_rule(self, irule):
		return self.__l_ggs[irule]

	def add_new_rule(self, phrase_ilen, phrase_len, result, num_stages, l_wlist_vars, phrase2_ilen,
					 phrase2_len, parent_irule):
		gg_child = cl_bitvec_gg(self, phrase_ilen, phrase_len, result, num_stages=num_stages,
						   l_wlist_vars=l_wlist_vars, phrase2_ilen=phrase2_ilen,
						   phrase2_len=phrase2_len, parent_irule=parent_irule)
		# gg1.add_child_rule_id(len(self.__l_ggs))
		igg_child = len(self.__l_ggs)
		self.__l_ggs.append((gg_child))
		return igg_child, gg_child

	def learn_rule_one_stage(self, phrase, l_results, phase_data):
		# phrase = rules2.convert_phrase_to_word_list([stmt])[0]
		ilen, iphrase =  self.__add_phrase(phrase, phase_data)
		if l_results == []:
			return -1, ilen, iphrase
		_, vars_dict = rules2.build_vars_dict(rules2.convert_wlist_to_phrases([phrase])[0])
		result = l_results[0]
		result_rec = rules2.place_vars_in_phrase(vars_dict, result)
		self.__l_results.append(result_rec)
		tresult = (ilen, tdown(result_rec))
		igg = self.__d_gg.get(tresult, -1)
		if igg == -1:
			igg = len(self.__l_ggs)
			self.__d_gg[tresult] = igg
			self.__l_ggs.append(cl_bitvec_gg(self, ilen, len(phrase), result_rec))
		self.__l_ggs[igg].add_phrase(iphrase)
		return igg, ilen, iphrase


	def learn_rule_two_stages(self, phrase, l_results, phase_data, idb):
		l_story_db_rphrases = self.__mpdb_mgr.get_idb_rphrases(idb)
		igg1, ilen, iphrase = self.learn_rule_one_stage(phrase, l_results, phase_data)
		if igg1 == -1:
			return phrase, igg1, ilen, iphrase
		gg1 = self.__l_ggs[igg1]
		if not gg1.is_tested() or gg1.get_status() == rule_status.irrelevant:
			return phrase, igg1, ilen, iphrase
		l_child_rule_ids = gg1.get_child_rule_ids()
		l_story_bins, l_story_refs = [], []
		for klen, vilen in self.__d_lens.iteritems():
			bin_dn = self.get_phrase_bin_db(vilen)
			story_refs = [tref[1] for tref in l_story_db_rphrases if tref[0] == vilen]
			if story_refs != []:
				l_story_bins.append(bin_dn[story_refs])
				l_story_refs.append((vilen, story_refs))
		# ilen, iphrase =  self.__add_phrase(phrase, phase_data)
		for iel, el in enumerate(phrase):
			el_bin = self.__nd_el_bin_db[self.__d_words[el]]
			for i_story_len, story_bin in enumerate(l_story_bins):
				db_len = story_bin.shape[1] / c_bitvec_size
				for iel2 in range(db_len):
					db_el_bin = story_bin[:, iel2*c_bitvec_size:(iel2+1)*c_bitvec_size]
					m_db = np.all(db_el_bin == el_bin, axis=1)
					if not np.any(m_db):
						continue
					for iref, bmatch in enumerate(m_db.tolist()):
						if not bmatch:
							continue
						phrase2_ilen, iphrase2 = l_story_refs[i_story_len][0], l_story_refs[i_story_len][1][iref]
						match_phrase = self.__l_phrases[phrase2_ilen][iphrase2]
						l_wlist_vars, new_result = rules2.replace_with_vars_in_wlist([phrase, match_phrase], l_results)
						# now create a rule with this information
						b_gg2_found = False
						for irule in l_child_rule_ids:
							gg2 = self.__l_ggs[irule]
							if gg2.test_rule_match(l_wlist_vars, new_result, phrase2_ilen):
								b_gg2_found = True
								break
						if not b_gg2_found:
							gg2 = cl_bitvec_gg(self, ilen, len(phrase), new_result, num_stages=2,
											   l_wlist_vars=l_wlist_vars, phrase2_ilen=phrase2_ilen,
											   phrase2_len=len(match_phrase), parent_irule=igg1)
							gg1.add_child_rule_id(len(self.__l_ggs))
							self.__l_ggs.append((gg2))
						gg2.add_phrase_stage2(iphrase, iphrase2)

					pass


		return phrase, igg1, ilen, iphrase

	# learn_rule_fns = [learn_rule_one_stage, learn_rule_two_stages]

	def learn_rule(self, stmt, l_results, phase_data, idb):
		# self.__l_dbs[idb], self.__l_d_story_len_refs[idb]
		# l_story_db_rphrases, d_len_bins = self.__mpdb_mgr.get_story_refs(idb)
		# self.learn_rule_fns[self.__rule_stages - 1](self, stmt, l_results, phase_data, l_story_db_event_refs)
		_, _, ilen, iphrase = self.learn_rule_two_stages(stmt, l_results, phase_data, idb)
		expect_results, expect_score = self.try_rule(stmt, ilen, iphrase, idb)
		self.update_rule_stats(stmt, ilen, iphrase, l_results, idb)


	def try_rule(self, phrase, ilen, iphrase, idb):
		# d_story_len_refs = self.__mpdb_mgr.get_d_story_len_refs(idb)
		# phrase = rules2.convert_phrase_to_word_list([stmt])[0]
		# ilen, iphrase =  self.__add_phrase(phrase, phase_data)
		len_phrase_bin_db = self.get_phrase_bin_db(ilen)
		phrase_bin = len_phrase_bin_db[iphrase]

		# _, vars_dict = rules2.build_vars_dict(stmt)
		results, scores = [], []
		l_curr_stage_ggs = []
		for igg, gg in enumerate(self.__l_ggs):
			if not gg.is_formed() or  gg.get_num_stages() != 1 or not gg.is_tested() or not gg.is_scored():
				continue
			if not gg.is_a_match(ilen, iphrase):
				continue
			results.append(gg.make_result([phrase]))
			scores.append(gg.get_score())
			l_curr_stage_ggs.append(gg)

		if l_curr_stage_ggs == []:
			return results, scores

		# d_story_bins = dict()
		# for klen, vilen in self.__d_lens.iteritems():
		# 	bin_dn = self.get_phrase_bin_db(vilen)
		# 	story_refs = [tref[1] for tref in l_story_db_event_refs if tref[0] == vilen]
		# 	if story_refs != []:
		# 		d_story_bins[vilen] = (bin_dn[story_refs], story_refs)

		len_phrase_bin_db = self.get_phrase_bin_db(ilen)
		phrase_bin = len_phrase_bin_db[iphrase]

		while l_curr_stage_ggs != []:
			l_prev_stage_ggs = list(l_curr_stage_ggs)
			l_curr_stage_ggs = []
			for gg in l_prev_stage_ggs:

				l_child_rule_ids = gg.get_child_rule_ids()
				for irule in l_child_rule_ids:
					gg2 = self.__l_ggs[irule]
					if not gg2.is_formed() or not gg2.is_tested() or not gg2.is_scored():
						continue
					l_match_paths, l_imatches = gg2.find_matches(phrase, phrase_bin, self.__mpdb_mgr, idb)
					if l_match_paths == []:
						continue
					l_curr_stage_ggs.append(gg2)
					gg_results, gg_indxs, gg_scores = [], [], []
					main_gg_score = gg2.get_score()
					for imatch, match_path in zip(l_imatches, l_match_paths):
						one_result = gg2.make_result(match_path)
						# if one_result != []:
						gg_results.append(one_result)
						gg_scores.append(main_gg_score)
						gg_indxs.append(imatch)

					gg_rev = gg2.get_gg_rev_impr()
					if gg_rev != []:
						rev_gg_score = gg_rev.get_score()
						if gg2._cl_bitvec_gg__rule_rec[8][0] == rec_def_type.var: # debug
							pass
						_, l_rev_imatches = gg_rev.find_matches(phrase, phrase_bin, self.__mpdb_mgr, idb)
						for iresult, imatch in enumerate(l_imatches):
							if imatch not in l_rev_imatches:
								gg_scores[iresult] = rev_gg_score
					l_gg_rnd_impr = gg2.get_gg_rnd_impr()
					if l_gg_rnd_impr != []:
						for gg_impr in l_gg_rnd_impr:
							impr_gg_score = gg_impr.get_score()
							_, l_impr_imatches = gg_impr.find_matches(phrase, phrase_bin, self.__mpdb_mgr, idb)
							for impr_imatch in l_rev_imatches:
								if impr_imatch in l_imatches:
									impr_indx = gg_indxs.index(impr_imatch)
									gg_scores[impr_indx] = impr_gg_score

					results += gg_results
					scores += gg_scores

		return results, scores


	# @bv_time_decor
	def apply_rule(self, phrase, ilen, iphrase, idb, l_rule_cats):
		return self._run_rule(phrase, ilen, iphrase, idb, l_rule_cats)

	# @bv_time_decor
	def run_rule(self, stmt, phase_data, idb, l_rule_cats, l_rule_names=[]):
		phrase = stmt # els.convert_phrase_to_word_list([stmt])[0]
		ilen, iphrase = self.__add_phrase(phrase, phase_data)
		return self._run_rule(	phrase, ilen, iphrase, idb,
								l_rule_cats, l_rule_names)

	def get_rules_by_cat(self, l_rule_cats):
		l_use_rules_ids = []
		for rule_cat in l_rule_cats:
			l_use_rules_ids += self.__d_fr_categories.get(rule_cat, [])
		l_use_rules = [self.__l_fixed_rules[ir] for ir in l_use_rules_ids]
		l_rule_names = [self.__l_rule_names[ir] for ir in l_use_rules_ids]
		return l_use_rules, l_rule_names


	def _run_rule(	self, phrase, ilen, iphrase, idb, l_rule_cats, l_rule_names=[]):
		# d_story_len_refs = self.__mpdb_mgr.get_d_story_len_refs(idb)
		len_phrase_bin_db = self.get_phrase_bin_db(ilen)
		phrase_bin = len_phrase_bin_db[iphrase]

		# l_story_bins, l_story_refs = [], []
		# d_story_bins = dict()
		# for klen, vilen in self.__d_lens.iteritems():
		# 	bin_dn = self.get_phrase_bin_db(vilen)
		# 	story_refs = [tref[1] for tref in l_story_db_event_refs if tref[0] == vilen]
		# 	if story_refs != []:
		# 		d_story_bins[vilen] = (bin_dn[story_refs], story_refs)

		results, l_use_rules_ids = [], []
		for rule_cat in l_rule_cats:
			l_use_rules_ids += self.__d_fr_categories.get(rule_cat, [])
		l_use_rules = [self.__l_fixed_rules[ir] for ir in l_use_rules_ids]
		for rule_name in l_rule_names:
			if rule_name not in self.__l_rule_names:
				print('Error. Unknown rule name requested for run rule:', rule_name)
				exit(1)
			l_use_rules.append(self.__l_fixed_rules[self.__l_rule_names.index(rule_name)])

		for igg, gg in enumerate(l_use_rules):
			if not gg.is_formed() or not gg.is_tested():
				continue
			if not gg.is_a_match_one_stage(ilen, iphrase):
				continue
			# gg.update_stats(phrase, l_results)
			if gg.get_num_stages() == 1:
				one_result = gg.make_result([phrase])
				results.append(one_result) if one_result != [] else None
				continue

			l_match_paths, _ = gg.find_matches(phrase, phrase_bin, self.__mpdb_mgr, idb)
			# l_match_paths2, t2 = gg.find_matches2(phrase, phrase_bin, self.__mpdb_mgr, idb)
			# assert sorted(l_match_paths) == sorted(l_match_paths2), 'new find match differs from old'
			if l_match_paths == []:
				continue
			for match_path in l_match_paths:
				one_result = gg.make_result(match_path)
				if one_result != []: results.append(one_result)


		return results

	def update_rule_stats(self, phrase, ilen, iphrase, l_results, idb):
		# l_story_db_rphrases = self.__mpdb_mgr.get_idb_rphrases(idb)
		# d_story_len_refs = self.__mpdb_mgr.get_d_story_len_refs(idb)
		# phrase = rules2.convert_phrase_to_word_list([stmt])[0]
		# ilen, iphrase =  self.__add_phrase(phrase, phase_data)
		# self.__l_all_phrases.append((phase_data, ilen, iphrase))
		# _, vars_dict = rules2.build_vars_dict(stmt)
		l_first_stage_ggs = []
		for igg, gg in enumerate(self.__l_ggs):
			if not gg.is_formed() or  gg.get_num_stages() != 1:
				continue
			if not gg.is_a_match(ilen, iphrase):
				continue
			gg.update_stats(phrase, l_results)
			if not gg.is_tested():
				continue
			l_first_stage_ggs.append(gg)

		if l_first_stage_ggs == []:
			return

		len_phrase_bin_db = self.get_phrase_bin_db(ilen)
		phrase_bin = len_phrase_bin_db[iphrase]

		# d_story_len_refs = dict()
		# for klen, vilen in self.__d_lens.iteritems():
		# 	# bin_dn = self.get_phrase_bin_db(vilen)
		# 	story_refs = [tref[1] for tref in l_story_db_rphrases if tref[0] == vilen]
		# 	if story_refs != []:
		# 		d_story_len_refs[vilen] = story_refs # (bin_dn[story_refs], story_refs)

		for gg in l_first_stage_ggs:

			l_child_rule_ids = gg.get_child_rule_ids()
			for irule in l_child_rule_ids:
				gg2 = self.__l_ggs[irule]
				if not gg2.is_formed():
					continue
				# story_refs = d_story_len_refs.get(gg2.get_last_phrase_ilen(), [])
				l_srphrases= self.__mpdb_mgr.get_rphrases()
				# if story_refs == []:
				# 	continue
				l_match_paths, l_imatches = gg2.find_matches(phrase, phrase_bin, self.__mpdb_mgr, idb)
				if l_match_paths == []:
					continue
				m_matches, m_hits = gg2.update_stats_stage_2(l_match_paths, l_imatches, len(l_srphrases), l_results)
				if np.sum(m_hits) < np.sum(m_matches) and gg2._cl_bitvec_gg__rule_rec[8][0] == rec_def_type.var:
					pass
				# story_bin = self.get_phrase_bin_db(gg2.get_last_phrase_ilen())[story_refs]
				gg2.set_match_hits(self.__mpdb_bins[m_matches], match_hits = m_hits[m_matches])

			pass



	def add_new_word(self, word, word_binvec):
		word_id = len(self.__d_words)
		self.__nd_el_bin_db = np.concatenate((self.__nd_el_bin_db, np.expand_dims(word_binvec, axis=0)), axis=0)
		self.__d_words[word] = word_id
		self.__l_word_change_db += [[[0.0 for ibit in xrange(c_bitvec_size)], 0.0]]
		self.__l_word_counts.append(1)
		self.__l_word_phrase_ids.append([])
		self.__l_els.append(word)
		# self.__nd_el_bin_db[word_id, :] = word_binvec
		self.__s_word_bit_db.add(tuple(word_binvec))
		self.__l_word_fix_num.append(0)
		return word_id

	def check_or_add_word(self, word):
		word_id = self.__d_words.get(word, -1)
		if word_id == -1:
			# l_b_known[iword] = False
			while True:
				proposal = np.random.choice(a=[0, 1], size=(c_bitvec_size))
				tproposal = tuple(proposal.tolist())
				if tproposal in self.__s_word_bit_db:
					continue
				break

			word_id = self.add_new_word(word, proposal)
		return word_id

	def keep_going(self, phrase):
		phrase_bin_db, d_words, s_word_bit_db, d_lens, l_phrases, l_word_counts, l_word_phrase_ids =\
			self.__phrase_bin_db, self.__d_words, self.__s_word_bit_db, \
			self.__d_lens, self.__l_phrases, self.__l_word_counts, self.__l_word_phrase_ids
		# phrase_bin_db = build_phrase_bin_db(s_phrase_lens, l_phrases, nd_el_bin_db, d_words)
		# l_change_db = [[[0.0 for _ in xrange(c_bitvec_size)], 0.0] for _ in l_word_counts]
		num_changed = 0
		phrase_len = len(phrase)
		ilen = d_lens.get(phrase_len, -1)
		if ilen == -1:
			ilen = len(d_lens)
			d_lens[phrase_len] = ilen
			l_phrases.append([])
			phrase_bin_db.append([])
		iphrase = len(l_phrases[ilen])
		l_b_known = [True for _ in phrase]
		for iword, word in enumerate(phrase):
			word_id = self.check_or_add_word(word)

		l_mbits = build_a_bit_mask(phrase_len)  # mask bits
		input_bits = create_input_bits(self.__nd_el_bin_db, d_words, phrase)
		changed_words = []
		for iskip in range(phrase_len):
			iword = d_words[phrase[iskip]]
			if iphrase > c_bitvec_min_len_before_learn:
				if self.__l_word_fix_num[iword] == 0:
					self.__nd_el_bin_db = add_new_words(self.__nd_el_bin_db, d_words, phrase_bin_db[ilen], phrase, input_bits,
												 s_word_bit_db, iskip)
					self.__l_word_fix_num[iword] = 1
					changed_words.append(phrase[iskip])
				else:
					# Following adds change pressure to self.__l_word_change_db[iword]
					score_hd_output_bits(	phrase_bin_db[ilen], input_bits,
										l_mbits[iskip], iskip, iword,
										self.__l_word_change_db, bscore=False)
					(l_bits_avg, num_hits), word_count = self.__l_word_change_db[iword], l_word_counts[iword]

					if num_hits * 2 > word_count:
						bchanged = change_bit(self.__nd_el_bin_db, s_word_bit_db, self.__nd_el_bin_db[iword], l_bits_avg, iword)
						if bchanged == 1:
							num_changed += 1
							changed_words.append(phrase[iskip])
						self.__l_word_change_db[iword] = [[0.0 for ibit in xrange(c_bitvec_size)], 0.0]
						if self.__l_word_fix_num[iword] != -1:
							self.__l_word_fix_num[iword] += 1
			l_word_counts[iword] += 1
			l_word_phrase_ids[iword].append((ilen, iphrase))

		l_phrases[ilen].append(phrase)
		self.__map_phrase_to_rphrase[tuple(phrase)] = (ilen, iphrase)
		if phrase_bin_db[ilen] == []:
			phrase_bin_db[ilen] = np.expand_dims(input_bits, axis=0)
		else:
			phrase_bin_db[ilen] = np.concatenate((phrase_bin_db[ilen], np.expand_dims(input_bits, axis=0)), axis=0)

		l_rphrase_changed = []
		for word_changed in changed_words:
			iword = d_words[word_changed]
			l_rphrase_changed = change_phrase_bin_db(phrase_bin_db, l_phrases, self.__nd_el_bin_db,
													d_words, iword, l_word_phrase_ids, l_rphrase_changed)
			l_fixed_rule_pos_data = self.__d_word_in_fixed_rule.get(word_changed, [])
			for i_fixed_rule, word_pos in l_fixed_rule_pos_data:
				self.__l_fixed_rules[i_fixed_rule].update_bin_for_word(word_pos, self.__nd_el_bin_db[iword])
		if l_rphrase_changed != []: self.__mpdb_mgr.apply_bin_db_changes(l_rphrase_changed)
		return self.__nd_el_bin_db, ilen, iphrase

def create_word_dict(phrase_list, max_process):
	d_els, l_presence, l_phrase_ids = dict(), [], []
	for iphrase, phrase in enumerate(phrase_list):
		if iphrase > max_process:
			break
		for iel, el, in enumerate(phrase):
			id = d_els.get(el, -1)
			if id == -1:
				d_els[el] = len(d_els)
				l_presence.append(1)
				l_phrase_ids.append([])
			else:
				l_presence[id] += 1
				# l_phrase_ids[id].append(iphrase)


	return d_els, l_presence, l_phrase_ids

def save_word_db(d_words, nd_bit_db, fnt_dict):
	fn = expanduser(fnt_dict)

	if os.path.isfile(fn):
		copyfile(fn, fn + '.bak')
	fh = open(fn, 'wb')
	csvw = csv.writer(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
	csvw.writerow(['Adv Dict', 'Version', '1'])
	csvw.writerow(['Num Els:', len(d_words)])
	for kword, virow in d_words.iteritems():
		csvw.writerow([kword, virow] + nd_bit_db[virow].tolist())

	fh.close()

def load_word_db(bitvec_dict_fnt):
	fn = expanduser(bitvec_dict_fnt)
	# try:
	if True:
		with open(fn, 'rb') as o_fhr:
			csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
			_, _, version_str = next(csvr)
			_, snum_els = next(csvr)
			version, num_els = int(version_str), int(snum_els)
			if version != 1:
				raise IOError
			d_words, s_word_bit_db, nd_bit_db = dict(), set(), np.zeros((num_els, c_bitvec_size), dtype=np.uint8)
			l_els = ['' for _ in xrange(num_els)]
			for irow, row in enumerate(csvr):
				word, iel, sbits = row[0], row[1], row[2:]
				d_words[word] = int(iel)
				l_els[int(iel)] = word
				bits = map(int, sbits)
				nd_bit_db[int(iel)] = np.array(bits, dtype=np.uint8)
				s_word_bit_db.add(tuple(bits))

	# except IOError:
	# 	raise ValueError('Cannot open or read ', fn)

	return d_words, nd_bit_db, s_word_bit_db, l_els

def load_order_freq_tbl(fnt):
	fn = expanduser(fnt)

	freq_tbl, d_words, s_phrase_lens = [], dict(), set()
	try:
		with open(fn, 'rb') as o_fhr:
			o_csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
			_, _, version_str, _, snum_orders = next(o_csvr)
			version = int(version_str)
			if version != 1:
				raise IOError
			for iorder in range(int(snum_orders)):
				row = next(o_csvr)
				l_co_oids = next(o_csvr)
				phrase = row[2:]
				s_phrase_lens.add(len(phrase))
				# freq_tbl[tuple(phrase)] = row[0]
				freq_tbl.append(phrase)
				# for word in phrase:
				# 	id = d_words.get(word, -1)
				# 	if id == -1:
				# 		d_words[word] = len(d_words)
	except IOError:
		raise ValueError('Cannot open or read ', fn)

	# num_uniques = len(d_words)

	# return freq_tbl, num_uniques, d_words, s_phrase_lens
	# random.shuffle(freq_tbl)
	return freq_tbl, s_phrase_lens


def create_input_bits(nd_bit_db, d_words, phrase, l_b_known=[]):
	phrase_len = len(phrase)
	input_bits = np.zeros(phrase_len * c_bitvec_size, dtype=np.uint8)
	loc = 0
	for iword, word in enumerate(phrase):
		if l_b_known != [] and not l_b_known[iword]:
			input_bits[loc:loc + c_bitvec_size] = np.zeros(c_bitvec_size, dtype=np.uint8)
		else:
			input_bits[loc:loc + c_bitvec_size] = nd_bit_db[d_words[word]]
		loc += c_bitvec_size
	# missing_loc = phrase[1] * c_num_replicate_missing
	# input_bits[loc + missing_loc:loc + missing_loc + c_num_replicate_missing] = [1] * c_num_replicate_missing
	return np.array(input_bits)


def create_output_bits(sel_mat, input_bits):
	nd_bits = np.zeros(c_bitvec_size, dtype=np.int)

	for iobit in range(c_bitvec_size):
		sum = 0
		for iibit in sel_mat[iobit][0]:
			sum += input_bits[iibit]
		nd_bits[iobit] = 1 if sum >= sel_mat[iobit][1] else 0

	return nd_bits


def score_hd_output_bits(nd_phrase_bits_db, qbits, mbits, iskip, iword, change_db, bscore=True):
	numrecs = nd_phrase_bits_db.shape[0]
	hd_divider = np.array(range(c_bitvec_neibr_divider_offset, score_hd_output_bits.num_ham_winners + c_bitvec_neibr_divider_offset),
						  np.float32)
	hd_divider_sum = np.sum(1. / hd_divider)

	def calc_score(outputs):
		odiffs = np.logical_and(np.not_equal(qbits, outputs), np.logical_not(mbits))
		nd_diffs = np.where(odiffs, np.ones_like(outputs), np.zeros_like(outputs))
		divider = np.array(range(1, nd_diffs.shape[0] + 1), np.float32)
		return np.sum(np.divide(np.sum(nd_diffs, axis=1), divider))

	# nd_diffs = np.absolute(np.subtract(qbits, nd_phrase_bits_db))
	nd_diffs = np.logical_and(np.not_equal(qbits, nd_phrase_bits_db), mbits)
	nd_diffs = np.where(nd_diffs, np.ones_like(nd_phrase_bits_db), np.zeros_like(nd_phrase_bits_db))
	hd = np.sum(nd_diffs, axis=1)
	hd_winners = np.argpartition(hd, score_hd_output_bits.num_ham_winners)[:score_hd_output_bits.num_ham_winners]
	hd_of_winners = hd[hd_winners]
	iwinners = np.argsort(hd_of_winners)
	hd_idx_sorted = hd_winners[iwinners]
	winner_outputs = nd_phrase_bits_db[hd_idx_sorted]
	avg_outputs = nd_phrase_bits_db[np.random.randint(numrecs, size=hd_idx_sorted.shape[0])]
	obits = winner_outputs[:, iskip*c_bitvec_size:(iskip+1)*c_bitvec_size]
	bad_obits = avg_outputs[:, iskip*c_bitvec_size:(iskip+1)*c_bitvec_size]
	# ibits = qbits[iskip*c_bitvec_size:(iskip+1)*c_bitvec_size].astype(float)
	# obits_goal = np.where(np.average(obits, axis=0) > 0.5, np.ones_like(ibits), np.zeros_like(ibits))
	obits_goal = np.sum(obits.transpose() / hd_divider, axis=1) / hd_divider_sum
	obits_keep_away = np.average(bad_obits, axis=0)
	new_obits_goal = ((obits_goal + (np.ones(c_bitvec_size) - obits_keep_away)) / 2.0).tolist()
	if change_db[iword][1] == 0.0:
		change_db[iword][0] = new_obits_goal
	else:
		change_db[iword][0] = ((np.array(change_db[iword][0]) * change_db[iword][1]) + new_obits_goal) / (change_db[iword][1] + 1.0)
	change_db[iword][1] += 1.0
	if not bscore:
		return
	close_score, avg_score = calc_score(winner_outputs), calc_score(avg_outputs)
	return avg_score / (close_score + 10.0)


score_hd_output_bits.num_ham_winners = 0

def build_a_bit_mask(phrase_len):
	l_mbits = []
	for iskip in range(phrase_len):
		mbits = np.ones(phrase_len * c_bitvec_size, np.uint8)
		mbits[iskip*c_bitvec_size:(iskip+1)*c_bitvec_size] = np.zeros(c_bitvec_size, np.uint8)
		l_mbits.append(mbits)
	return l_mbits


def build_bit_masks(d_lens):
	l_l_mbits = [] # mask bits
	for phrase_len, ilen in d_lens.iteritems():
		l_mbits = []
		for iskip in range(phrase_len):
			mbits = np.ones(phrase_len * c_bitvec_size, np.uint8)
			mbits[iskip*c_bitvec_size:(iskip+1)*c_bitvec_size] = np.zeros(c_bitvec_size, np.uint8)
			l_mbits.append(mbits)
		l_l_mbits.append(l_mbits)
	return l_l_mbits

def change_bit(nd_bit_db, s_word_bit_db, l_bits_now, l_bits_avg, iword):
	# if random.random() < score_and_change_db.move_rnd:
	bchanged = False
	ibit = random.randint(0, c_bitvec_size - 1)
	bit_now, bit_goal = l_bits_now[ibit], l_bits_avg[ibit]
	proposal = np.copy(nd_bit_db[iword])
	if bit_now == 0 and bit_goal > 0.5:
		if random.random() < (bit_goal - 0.5):
			proposal[ibit] = 1
			bchanged = True
	elif bit_now == 1 and bit_goal < 0.5:
		if random.random() < (0.5 - bit_goal):
			proposal[ibit] = 0
			bchanged = True
	if bchanged:
		tproposal = tuple(proposal.tolist())
		if tproposal not in s_word_bit_db:
			tremove = tuple(nd_bit_db[iword].tolist())
			nd_bit_db[iword, :] = proposal
			s_word_bit_db.remove(tremove)
			s_word_bit_db.add(tproposal)
			return 1
	return 0

def score_and_change_db(s_phrase_lens, d_words, l_phrases, nd_bit_db, s_word_bit_db):
	num_uniques = len(d_words)
	l_change_db = [[[0.0 for ibit in xrange(c_bitvec_size)], 0.0] for _ in xrange(num_uniques)]
	bitvec_size = nd_bit_db.shape[1]
	num_scored = 0
	num_hits = 0
	l_l_mbits = build_bit_masks(s_phrase_lens) # mask bits

	phrase_bits_db = [np.zeros((len(l_len_phrases), bitvec_size * list(s_phrase_lens)[ilen]), dtype=np.int)
					  for ilen, l_len_phrases in enumerate(l_phrases)]
	score = 0.0
	for ilen, phrase_len in enumerate(s_phrase_lens):
		num_scored += len(l_phrases[ilen]) * phrase_len
		# sel_mat = d_phrase_sel_mats[phrase_len]
		for iphrase, phrase in enumerate(l_phrases[ilen]):
			# nd_bits = np.zeros(c_bitvec_size, dtype=np.int)
			input_bits = create_input_bits(nd_bit_db, d_words, phrase)
			phrase_bits_db[ilen][iphrase, :] = input_bits

		for iphrase, phrase in enumerate(l_phrases[ilen]):
			for iskip in range(phrase_len):
				score += score_hd_output_bits(	phrase_bits_db[ilen], phrase_bits_db[ilen][iphrase],
												l_l_mbits[ilen][iskip], iskip, d_words[phrase[iskip]],
												l_change_db)
	score /= num_scored

	num_changed = 0
	for iunique, bits_data in enumerate(l_change_db):
		l_bits_avg, _ = bits_data
		l_bits_now = nd_bit_db[iunique]
		num_changed += change_bit(nd_bit_db, s_word_bit_db, l_bits_now, l_bits_avg, iunique)
		# if random.random() < score_and_change_db.move_rnd:
		# 	bchanged = False
		# 	ibit = random.randint(0, c_bitvec_size-1)
		# 	bit_now, bit_goal = l_bits_now[ibit], l_bits_avg[ibit]
		# 	proposal = np.copy(nd_bit_db[iunique])
		# 	if bit_now == 0 and bit_goal > 0.5:
		# 		if random.random() < (bit_goal - 0.5):
		# 			proposal[ibit] = 1
		# 			bchanged = True
		# 	elif bit_now == 1 and bit_goal < 0.5:
		# 		if random.random() < (0.5 - bit_goal):
		# 			proposal[ibit] = 0
		# 			bchanged = True
		# 	if bchanged:
		# 		tproposal = tuple(proposal.tolist())
		# 		if tproposal not in s_word_bit_db:
		# 			tremove = tuple(nd_bit_db[iunique].tolist())
		# 			nd_bit_db[iunique, :] = proposal
		# 			s_word_bit_db.remove(tremove)
		# 			s_word_bit_db.add(tproposal)
		# 			num_changed += 1
	frctn_change = float(num_changed) / float(num_uniques * c_bitvec_size)
	if frctn_change < c_bitvec_min_frctn_change:
		score_and_change_db.move_rnd += c_bitvec_move_rnd_change
	elif frctn_change > c_bitvec_max_frctn_change:
		score_and_change_db.move_rnd -= c_bitvec_move_rnd_change
	print(num_changed, 'bits changed out of', num_uniques * c_bitvec_size, 'fraction:',
		  frctn_change, 'move_rnd = ', score_and_change_db.move_rnd)
	return score



score_and_change_db.move_rnd = c_bitvec_move_rnd

# def select_best(s_phrase_lens, d_words, l_phrases, l_objs, iiter, l_record_scores, l_record_objs, best_other, b_do_dbs):
# 	min_score, max_score = sys.float_info.max, -sys.float_info.max
# 	num_objs = len(l_objs)
# 	l_scores = []
# 	for iobj in range(num_objs):
# 		if b_do_dbs:
# 			nd_bit_db = l_objs[iobj]
# 			d_phrase_sel_mats = best_other
# 		else:
# 			nd_bit_db = best_other
# 			d_phrase_sel_mats = l_objs[iobj]
# 		score = score_db_and_sel_mat(s_phrase_lens, d_words, l_phrases, nd_bit_db, d_phrase_sel_mats)
# 		l_scores.append(score)
# 		if score > max_score:
# 			max_score = score
# 		if score < min_score:
# 			min_score = score
#
# 	# print('avg score:', np.mean(l_scores)) # , 'list', l_scores)
# 	print('iiter', iiter, 'avg score:', np.mean(l_scores), 'max score:', np.max(l_scores)) # , 'list', l_scores)
# 	if l_record_scores == [] or max_score > l_record_scores[0]:
# 		l_record_scores.insert(0, max_score)
# 		l_record_objs.insert(0, l_objs[l_scores.index(max_score)])
# 	else:
# 		l_objs[l_scores.index(min_score)] = l_record_objs[0]
# 		l_scores[l_scores.index(min_score)] = l_record_scores[0]
# 	# mid_score = (max_score + min_score) / 2.0
# 	mid_score = l_scores[np.array(l_scores).argsort()[c_mid_score]]
# 	if max_score == min_score:
# 			range_scores = max_score
# 			l_obj_scores = np.ones(len(l_scores), dtype=np.float32)
# 	elif mid_score == max_score:
# 		range_scores = max_score - min_score
# 		l_obj_scores = np.array([(score - min_score) / range_scores for score in l_scores])
# 	else:
# 		range_scores = max_score - mid_score
# 		l_obj_scores = np.array([(score - mid_score) / range_scores for score in l_scores])
# 	l_obj_scores = np.where(l_obj_scores > 0.0, l_obj_scores, np.zeros_like(l_obj_scores))
# 	sel_prob = l_obj_scores/np.sum(l_obj_scores)
# 	l_sel_dbs = np.random.choice(num_objs, size=num_objs, p=sel_prob)
# 	l_objs[:] = [copy.deepcopy(l_objs[isel]) for isel in l_sel_dbs]

# def mutate_dbs(l_dbs, num_uniques):
# 	num_flip_muts = int(c_db_num_flip_muts * num_uniques)
#
# 	for idb, nd_bit_db in enumerate(l_dbs):
# 		if random.random() < c_db_rnd_asex:
# 			for imut in range(num_flip_muts):
# 				allele, target = random.randint(0, c_bitvec_size - 1), random.randint(0, num_uniques-1)
# 				nd_bit_db[target][allele] = 1 if (nd_bit_db[target][allele] == 0) else 0
# 		elif random.random() < c_db_rnd_sex:
# 			partner_db = copy.deepcopy(random.choice(l_dbs))  # not the numpy function
# 			for allele in range(c_bitvec_size):
# 				for iun in range(num_uniques):
# 					if random.random() < 0.5:
# 						nd_bit_db[iun,:] = partner_db[iun,:]
#
# def mutate_sel_mats(l_d_phrase_sel_mats, s_phrase_lens):
# 	for isel, d_phrase_sel_mats in enumerate(l_d_phrase_sel_mats):
# 		for ilen, phrase_len in enumerate(s_phrase_lens):
# 			num_input_bits = ((phrase_len - 1) * c_bitvec_size) + (c_num_replicate_missing * phrase_len)
# 			sel_mat = d_phrase_sel_mats[phrase_len]
# 			if random.random() < c_rnd_asex:
# 				for imut in range(c_num_incr_muts):
# 					allele = random.randint(0, c_bitvec_size-1)
# 					num_bits = len(sel_mat[allele][0])
# 					if sel_mat[allele][1] < num_bits-2:
# 						sel_mat[allele][1] += 1
# 				for imut in range(c_num_incr_muts):
# 					allele = random.randint(0, c_bitvec_size-1)
# 					if sel_mat[allele][1] > 1:
# 						sel_mat[allele][1] -= 1
# 				for icmut in range(c_num_change_muts):
# 					allele = random.randint(0, c_bitvec_size-1)
# 					bit_list = sel_mat[allele][0]
# 					if random.random() < c_change_mut_prob_change_len:
# 						if len(bit_list) < c_max_bits:
# 							bit_list.append(random.randint(0, num_input_bits - 1))
# 					elif random.random() < c_change_mut_prob_change_len:
# 						if len(bit_list) > c_min_bits:
# 							bit_list.pop(random.randrange(len(bit_list)))
# 							if sel_mat[allele][1] >= len(bit_list) - 1:
# 								sel_mat[allele][1] -= 1
# 					else:
# 						for ichange in range(c_change_mut_num_change):
# 							bit_list[random.randint(0, len(bit_list)-1)] = random.randint(0, num_input_bits - 1)
# 			elif random.random() < c_rnd_sex:
# 				partner_sel_mat = copy.deepcopy(random.choice(l_d_phrase_sel_mats)[phrase_len]) # not the numpy function
# 				for allele in range(c_bitvec_size):
# 					if random.random() < 0.5:
# 						sel_mat[allele] = list(partner_sel_mat[allele])

def build_phrase_bin_db(s_phrase_lens, l_phrases, nd_el_bin_db, d_words):
	phrase_bits_db = [np.zeros((len(l_len_phrases), c_bitvec_size * list(s_phrase_lens)[ilen]), dtype=np.int)
					  for ilen, l_len_phrases in enumerate(l_phrases)]
	score = 0.0
	for ilen, phrase_len in enumerate(s_phrase_lens):
		for iphrase, phrase in enumerate(l_phrases[ilen]):
			# nd_bits = np.zeros(c_bitvec_size, dtype=np.int)
			input_bits = create_input_bits(nd_el_bin_db, d_words, phrase)
			phrase_bits_db[ilen][iphrase, :] = input_bits

	return phrase_bits_db

def change_phrase_bin_db(phrase_bits_db, l_phrases, nd_el_bin_db, d_words, iword, l_word_phrase_ids, l_rphrase_changed):
	# l_rphrase_changed = []
	for ilen, iphrase in l_word_phrase_ids[iword]:
		phrase = l_phrases[ilen][iphrase]
		input_bits = create_input_bits(nd_el_bin_db, d_words, phrase)
		phrase_bits_db[ilen][iphrase, :] = input_bits
		l_rphrase_changed.append((ilen, iphrase))
	return l_rphrase_changed




# ilen is the index number of the list of phrase grouped by phrase len (not the length of the phrase)
# iphrase is index in that list of phrases of that length
def add_new_words(	nd_bit_db, d_words, nd_phrase_bits_db, phrase, phrase_bits, s_word_bit_db,
					iword):
	divider = np.array(range(c_bitvec_neibr_divider_offset, score_hd_output_bits.num_ham_winners + c_bitvec_neibr_divider_offset),
					   np.float32)
	divider_sum = np.sum(1. / divider)
	phrase_len = len(phrase)
	mbits = np.ones(phrase_len * c_bitvec_size, np.uint8)
	mbits[iword * c_bitvec_size:(iword + 1) * c_bitvec_size] = np.zeros(c_bitvec_size, np.uint8)

	nd_diffs = np.logical_and(np.not_equal(phrase_bits, nd_phrase_bits_db), mbits)
	nd_diffs = np.where(nd_diffs, np.ones_like(nd_phrase_bits_db), np.zeros_like(nd_phrase_bits_db))
	hd = np.sum(nd_diffs, axis=1)
	hd_winners = np.argpartition(hd, score_hd_output_bits.num_ham_winners)[:score_hd_output_bits.num_ham_winners]
	hd_of_winners = hd[hd_winners]
	iwinners = np.argsort(hd_of_winners)
	hd_idx_sorted = hd_winners[iwinners]
	winner_outputs = nd_phrase_bits_db[hd_idx_sorted]
	word_id = d_words[phrase[iword]]
	obits = winner_outputs[:, iword*c_bitvec_size:(iword+1)*c_bitvec_size]
	new_vals = np.sum(obits.transpose() / divider, axis=1) / divider_sum
	# round them all and if the pattern is already there switch the closest to 0.5
	new_bits = np.round_(new_vals).astype(np.uint8)
	s_word_bit_db.remove(tuple(nd_bit_db[word_id]))
	if tuple(new_bits) in s_word_bit_db:
		bfound = False
		while True:
			can_flip = np.argsort(np.square(new_vals - 0.5))
			for num_flip in range(1, c_bitvec_size):
				try_flip = can_flip[:num_flip]
				l = [list(itertools.combinations(try_flip, r)) for r in range(num_flip+1)]
				lp = [item for sublist in l for item in sublist]
				for p in lp:
					pbits = list(new_bits)
					for itf in try_flip:
						pbits[itf] = 1 if itf in p else 0
					if tuple(pbits) not in s_word_bit_db:
						new_bits = pbits
						bfound = True
						break
				if bfound:
					break
			if bfound:
				break

	s_word_bit_db.add(tuple(new_bits))
	nd_bit_db[word_id] = new_bits
	return nd_bit_db



def main():
	raise ValueError('why here')
	# success_orders_freq = dict()
	freq_tbl, s_phrase_lens = load_order_freq_tbl(fnt)
	init_len = c_init_len # len(freq_tbl) / 2
	d_words, l_word_counts, l_word_phrase_ids = create_word_dict(freq_tbl, init_len)
	num_ham_winners = len(d_words) / c_bitvec_ham_winners_fraction
	score_hd_output_bits.num_ham_winners= num_ham_winners
	num_uniques = len(d_words)
	nd_bit_db = np.zeros((num_uniques, c_bitvec_size), dtype=np.uint8)
	s_word_bit_db = set()
	for iunique in range(num_uniques):
		while True:
			proposal = np.random.choice(a=[0, 1], size=(c_bitvec_size))
			tproposal = tuple(proposal.tolist())
			if tproposal in s_word_bit_db:
				continue
			nd_bit_db[iunique, :] = proposal
			s_word_bit_db.add(tproposal)
			break
	l_change_db = [[[0.0 for ibit in xrange(c_bitvec_size)], 0.0] for _ in xrange(num_uniques)]
	# d_phrase_sel_mats, d_lens = dict(), dict()
	# for ilen, phrase_len in enumerate(s_phrase_lens):
	# 	num_input_bits = phrase_len * c_bitvec_size
	# 	sel_mat = []
	# 	for ibit in range(c_bitvec_size):
	# 		num_bits = random.randint(c_min_bits, c_max_bits)
	# 		l_sels = []
	# 		for isel in range(num_bits):
	# 			l_sels.append(random.randint(0, num_input_bits-1))
	# 		sel_mat.append([l_sels, random.randint(1, num_bits)])
	# 	d_phrase_sel_mats[phrase_len] = sel_mat
	# 	d_lens[phrase_len] = ilen
	d_lens = {phrase_len:ilen for ilen, phrase_len in enumerate(s_phrase_lens)}

	l_phrases = [[] for _ in s_phrase_lens]
	for iphrase, phrase in enumerate(freq_tbl):
		if iphrase >= init_len:
			break
		plen = len(phrase)
		l_phrases[d_lens[plen]].append(phrase)

	for ilen, phrases in enumerate(l_phrases):
		for iphrase, phrase in enumerate(phrases):
			for iel, el in enumerate(phrase):
				id = d_words[el]
				l_word_phrase_ids[id].append((ilen, iphrase))

	if c_b_init_db:
		for iiter in range(c_num_iters):
			score = score_and_change_db(s_phrase_lens, d_words, l_phrases, nd_bit_db, s_word_bit_db)
			print('iiter', iiter, 'score:', score)  # , 'list', l_scores)
			if iiter % c_save_init_db_every == 0:
				save_word_db(d_words, nd_bit_db, fnt_dict)
		return
	else:
		d_words, nd_bit_db, s_word_bit_db, _ = load_word_db()

	add_start = c_init_len
	while (add_start < len(freq_tbl)):
		nd_bit_db = keep_going(	freq_tbl, d_words, nd_bit_db, s_word_bit_db, s_phrase_lens,
								l_phrases, l_word_counts, l_word_phrase_ids, add_start, c_add_batch)
		print('Added', c_add_batch, 'phrases after', add_start)
		add_start += c_add_batch
		for iiter in range(c_add_fix_iter):
			score = score_and_change_db(s_phrase_lens, d_words, l_phrases, nd_bit_db, s_word_bit_db)
			print('iiter', iiter, 'score:', score)  # , 'list', l_scores)

