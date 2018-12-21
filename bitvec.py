"""
Descended from phrases.py

THis module seeks to add to the dictionary bitvec as new words come in

The skip representation will be replaced by a mask on the input for the unknown word

"""
from __future__ import print_function
import csv
import random
import os
from os.path import expanduser
import sys
# sys.path.append('/home/eli/testpy')
from shutil import copyfile
import itertools
import timeit
import collections

import numpy as np
# from py.builtin import enumerate

from utils import profile_decor
import rules2
from rules2 import conn_type
from rules2 import rec_def_type
# import els
# import makerecs as mr
# import bitvec_rf
import gg
from varopts import varopts

# fnt = 'orders_success.txt'
# fnt = '~/tmp/adv_phrase_freq.txt'
# fnt_dict = '~/tmp/adv_bin_dict.txt'
# fnt_bitvec_saved_phrases = '~/tmp/saved_phrases_small.txt'

class Enum(set):
	def __getattr__(self, name):
		if name in self:
			return name
		raise AttributeError


c_bitvec_size = 16 # 50 # 16
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




tdown = lambda l: tuple([tuple(li) for li in l])

total_time = 0

# def bv_time_decor(fn):
# 	def wr(*args, **kwargs):
# 		global total_time
# 		s = timeit.default_timer()
# 		r = fn(*args, **kwargs)
# 		total_time += timeit.default_timer() - s
# 		return r
# 	return wr
#
#
# atime_tot, btime_tot, ctime_tot = 0, 0, 0


class cl_bitvec_mgr(object):
	def __init__(self, phrase_freq_fnt, bitvec_dict_fnt, bitvec_saved_phrases_fnt, rule_grp_fnt):
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
		self.__l_saved_phrases = []

		self.__bitvec_saved_phrases_fnt = bitvec_saved_phrases_fnt
		self.__rule_grp_fnt = rule_grp_fnt

		self.__d_rule_grps = dict() # map from rule name to an int unique to group
		self.__l_fixed_rules = []
		self.__l_rule_names = []
		self.__d_word_in_fixed_rule = dict()
		self.__d_fr_categories = dict()
		self.__mpdb_mgr = None
		self.__mpdb_bins = [] # np.zeros(shape=(0, 0),dtype=np.uint8)  # 2D np array holding all bitvecs for all phrases in story held by mpdb
		gg.cl_bitvec_gg.bitvec_size = c_bitvec_size
		self.__hcvo = varopts.init_capp()
		varopts.set_el_bitvec_size(self.__hcvo, c_bitvec_size)
		varopts.init_el_bin_db(self.__hcvo, len(self.__nd_el_bin_db), len(self.__d_words) * 2);
		for iel, (el_bin, el_word) in enumerate(zip(self.__nd_el_bin_db, self.__l_els)):
			bin_arr = self.convert_charvec_to_arr(el_bin, c_bitvec_size)
			varopts.set_el_bin(self.__hcvo, iel, el_word, bin_arr)
			# test_bin_arr = varopts.check_el_bin(self.__hcvo, el_word);

		self.load_rule_grps()
		self.load_save_phrases()

	def get_saved_phrases(self):
		return self.__l_saved_phrases

	def get_hcvo(self):
		return self.__hcvo

	def get_d_rule_grps(self):
		return self.__d_rule_grps

	def load_rule_grps(self):
		fn = self.__rule_grp_fnt
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				for irow, row in enumerate(csvr):
					for rname in row:
						self.__d_rule_grps[rname] = irow

		except IOError:
			print('Cannot open or read ', fn)

	def flush_saved_phrases(self):
		fn = expanduser(self.__bitvec_saved_phrases_fnt)

		if os.path.isfile(fn):
			copyfile(fn, fn + '.bak')
		fh = open(fn, 'wb')
		csvw = csv.writer(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
		csvw.writerow(['Bitvec Saved Phrases', 'Version', '1'])
		csvw.writerow(['Num Phrases:', len(self.__l_saved_phrases)])
		for row in self.__l_saved_phrases:
			csvw.writerow(row)

		fh.close()

	def load_save_phrases(self):
		fn = expanduser(self.__bitvec_saved_phrases_fnt)
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				_, snum_els = next(csvr)
				version, num_els = int(version_str), int(snum_els)
				if version != 1:
					raise IOError
				for irow, row in enumerate(csvr):
					self.__l_saved_phrases.append(row)

		except IOError:
			print('Cannot open or read ', fn)


	def save_phrase(self, rule_name, phrase):
		self.__l_saved_phrases.append([rule_name, ' '.join(phrase)])

	def convert_charvec_to_arr(self, bin, size=-1):
		if size==-1:
			size = len(bin)
		bin_arr = varopts.charArray(size)
		for ib in range(size): bin_arr[ib] = chr(bin[ib])
		return bin_arr

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
			iel, itel = self.__d_words.get(el, -1), self.__d_words.get(tel, -1)
			if iel == -1 or itel == -1: return []
			el_bin = self.__nd_el_bin_db[iel]
			tel_bin = self.__nd_el_bin_db[itel]
			if np.sum(np.not_equal(el_bin, tel_bin)) <= hd_max:
				ret.append(el)

		return ret

	def mpdb_bins_to_c(self):
		varopts.app_mpdb_bin_init(self.__hcvo, self.__mpdb_bins.shape[0], self.__mpdb_bins.shape[1])
		for irec, rec in enumerate(self.__mpdb_bins):
			varopts.app_mpdb_bin_rec_set(self.__hcvo, irec, self.convert_charvec_to_arr(rec, rec.shape[0]))

	def add_mpdb_bins(self, ilen, iphrase):
		# self.debug_test_mpdb_bins()
		bin_db = self.get_phrase_bin_db(ilen)
		bins = bin_db[iphrase]
		b_c_reset = False
		if self.__mpdb_bins == []:
			self.__mpdb_bins = np.expand_dims(bins,axis=0)
			self.mpdb_bins_to_c()
			return
		if bins.shape[0] > self.__mpdb_bins.shape[1]:
			grow = bins.shape[0] - self.__mpdb_bins.shape[1]
			self.__mpdb_bins  = np.pad(self.__mpdb_bins, ((0,0), (0, grow)), 'constant')
			varopts.app_mpdb_bin_free(self.__hcvo)
			b_c_reset = True
		elif bins.shape[0] < self.__mpdb_bins.shape[1]:
			grow = self.__mpdb_bins.shape[1] - bins.shape[0]
			bins = np.pad(bins, (0, grow), 'constant')
		self.__mpdb_bins = np.vstack((self.__mpdb_bins, bins))
		if b_c_reset:
			self.mpdb_bins_to_c()
		else:
			varopts.app_mpdb_bin_rec_add(self.__hcvo, self.convert_charvec_to_arr(bins, bins.shape[0]))
		self.debug_test_mpdb_bins()

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
		varopts.app_mpdb_bin_free(self.__hcvo)
		self.mpdb_bins_to_c()
		self.debug_test_mpdb_bins()


	def update_mpdb_bins(self, iupdate, rphrase):
		new_bin = self.get_phrase_bin(*rphrase)
		b_c_reset = False
		# if new_bin.shape[0] < self.__mpdb_bins.shape[1]:
		# 	grow = self.__mpdb_bins.shape[1] - new_bin.shape[0]
		# 	self.__mpdb_bins[iupdate] = np.pad(new_bin, (0, grow), 'constant')
		if new_bin.shape[0] > self.__mpdb_bins.shape[1]:
			grow = new_bin.shape[0] - self.__mpdb_bins.shape[1]
			self.__mpdb_bins  = np.pad(self.__mpdb_bins, ((0,0), (0, grow)), 'constant')
			varopts.app_mpdb_bin_free(self.__hcvo)
			b_c_reset = True
		elif new_bin.shape[0] < self.__mpdb_bins.shape[1]:
			grow = self.__mpdb_bins.shape[1] - new_bin.shape[0]
			new_bin = np.pad(new_bin, (0, grow), 'constant')
		self.__mpdb_bins[iupdate] = new_bin
		if b_c_reset:
			self.mpdb_bins_to_c()
		else:
			varopts.app_mpdb_bin_rec_set(self.__hcvo, iupdate, self.convert_charvec_to_arr(new_bin, new_bin.shape[0]))



	def clear_mpdb_bins(self):
		self.__mpdb_bins = []
		varopts.app_mpdb_bin_free(self.__hcvo)

	def clear_all_db_arg_caches(self):
		for gg in self.__l_fixed_rules:
			gg.clr_db_arg_cache()

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
				varopts.ll_phrases_add_ilen(self.__hcvo)
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
		fixed_rule = gg.cl_bitvec_gg(	self, phrase_ilen, phrase_len, result, num_stages=len(rule_arr),
									l_wlist_vars=l_wlist_vars, phrase2_ilen=phrase2_ilen, phrase2_len=phrase2_len,
									parent_irule=-1, l_phrases_len=l_phrases_len, l_phrases_ilen=l_phrases_ilen)
		fixed_rule.set_els_rep(l_els_rep, l_hd_max)
		fixed_rule.set_formed_and_tested(bformed=True, btested=True)
		fixed_rule.set_rule_rec(rule_rec)
		fixed_rule.set_exdb(d_exdb)
		fixed_rule.set_name(rule_name)
		fixed_rule.create_vo_hgg()
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

	def get_el_id(self, word):
		return self.__d_words.get(word, -1)

	def get_bin_by_id(self, id):
		return self.__nd_el_bin_db[id]

	def get_word_by_id(self, iel):
		return self.__l_els[iel]

	def get_s_word_bit_db(self):
		return self.__s_word_bit_db

	def add_unique_bits_ext(self, new_bits):
		self.__s_word_bit_db.add(tuple(new_bits))

	def remove_unique_bits_ext(self, bits):
		self.__s_word_bit_db.remove(tuple(bits))

	def match_el_to_like(self, el, like_rep, cosine_dist):
		hd_max = c_bitvec_size * (1.0 - cosine_dist)
		el_bin, rep_bin = self.get_el_bin(el), self.get_el_bin(like_rep)
		return np.sum(np.not_equal(el_bin, rep_bin)) <= hd_max

	def add_phrase(self, phrase, phase_data):
		ilen, iphrase = self.__add_phrase(phrase, phase_data)
		# self.__l_all_phrases.append((phase_data, ilen, iphrase))
		return ilen, iphrase

	def __add_phrase(self, phrase, phase_data):
		story_id, story_time, story_loop_stage, eid = phase_data
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
		gg_child = gg.cl_bitvec_gg(self, phrase_ilen, phrase_len, result, num_stages=num_stages,
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
			self.__l_ggs.append(gg.cl_bitvec_gg(self, ilen, len(phrase), result_rec))
		self.__l_ggs[igg].add_phrase(iphrase)
		return igg, ilen, iphrase


	def learn_rule_two_stages(self, phrase, l_results, phase_data, idb):
		l_story_db_rphrases = self.__mpdb_mgr.get_idb_rphrases(idb)
		igg1, ilen, iphrase = self.learn_rule_one_stage(phrase, l_results, phase_data)
		if igg1 == -1:
			return phrase, igg1, ilen, iphrase
		gg1 = self.__l_ggs[igg1]
		if not gg1.is_tested() or gg1.get_status() == gg.rule_status.irrelevant:
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
							gg2 = gg.cl_bitvec_gg(self, ilen, len(phrase), new_result, num_stages=2,
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
	def apply_rule(self, phrase, ilen, iphrase, idb, l_rule_cats, l_result_rule_names=None):
		return self._run_rule(phrase, ilen, iphrase, idb, l_rule_cats, [], l_result_rule_names)

	# @bv_time_decor
	def run_rule(self, stmt, phase_data, idb, l_rule_cats, l_rule_names=[], l_result_rule_names=[]):
		phrase = stmt # els.convert_phrase_to_word_list([stmt])[0]
		ilen, iphrase = self.__add_phrase(phrase, phase_data)
		return self._run_rule(	phrase, ilen, iphrase, idb,
								l_rule_cats, l_rule_names, l_result_rule_names)

	def get_rules_by_cat(self, l_rule_cats):
		l_use_rules_ids = []
		for rule_cat in l_rule_cats:
			l_use_rules_ids += self.__d_fr_categories.get(rule_cat, [])
		l_use_rules = [self.__l_fixed_rules[ir] for ir in l_use_rules_ids]
		l_rule_names = [self.__l_rule_names[ir] for ir in l_use_rules_ids]
		return l_use_rules, l_rule_names

	@profile_decor
	def _run_rule(	self, phrase, ilen, iphrase, idb, l_rule_cats, l_rule_names=[], l_result_rule_names=None):
		# d_story_len_refs = self.__mpdb_mgr.get_d_story_len_refs(idb)
		if l_result_rule_names == None:
			l_result_rule_names = []
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
				if one_result != []:
					results.append(one_result)
					l_result_rule_names.append(gg.get_name())
				continue

			l_match_paths, _ = gg.find_matches(phrase, phrase_bin, self.__mpdb_mgr, idb)
			# l_match_paths2, t2 = gg.find_matches2(phrase, phrase_bin, self.__mpdb_mgr, idb)
			# assert sorted(l_match_paths) == sorted(l_match_paths2), 'new find match differs from old'
			if l_match_paths == []:
				continue
			for match_path in l_match_paths:
				one_result = gg.make_result(match_path)
				if one_result != []:
					results.append(one_result)
					l_result_rule_names.append(gg.get_name())


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
				# if np.sum(m_hits) < np.sum(m_matches) and gg2._cl_bitvec_gg__rule_rec[8][0] == rec_def_type.var:
				# 	pass
				# story_bin = self.get_phrase_bin_db(gg2.get_last_phrase_ilen())[story_refs]
				# The following is removed for now as we are not doing gg improvement
				#gg2.set_match_hits(self.__mpdb_bins[m_matches], match_hits = m_hits[m_matches])

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
		print('adding', word)
		cnum = varopts.add_el_bin(self.__hcvo, word, self.convert_charvec_to_arr(word_binvec))
		print('added', word)
		assert cnum == len(self.__d_words), 'Error. c version of el db misaligned with base code.'
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

	keep_going_num_calls = 0
	keep_going_num_words_changed = 0

	def keep_going(self, phrase):
		phrase_bin_db, d_words, s_word_bit_db, d_lens, l_phrases, l_word_counts, l_word_phrase_ids =\
			self.__phrase_bin_db, self.__d_words, self.__s_word_bit_db, \
			self.__d_lens, self.__l_phrases, self.__l_word_counts, self.__l_word_phrase_ids
		# phrase_bin_db = build_phrase_bin_db(s_phrase_lens, l_phrases, nd_el_bin_db, d_words)
		# l_change_db = [[[0.0 for _ in xrange(c_bitvec_size)], 0.0] for _ in l_word_counts]
		cl_bitvec_mgr.keep_going_num_calls += 1
		num_changed = 0
		phrase_len = len(phrase)
		ilen = d_lens.get(phrase_len, -1)
		if ilen == -1:
			ilen = len(d_lens)
			d_lens[phrase_len] = ilen
			l_phrases.append([])
			varopts.ll_phrases_add_ilen(self.__hcvo)
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
		str_arr = varopts.str_list_create(len(phrase))
		for phrase_iel, phrase_el in enumerate(phrase): varopts.str_list_set(str_arr, phrase_iel, phrase_el)
		varopts.ll_phrases_add_val(self.__hcvo, ilen, str_arr)
		varopts.str_list_delete(str_arr)
		self.__map_phrase_to_rphrase[tuple(phrase)] = (ilen, iphrase)
		if phrase_bin_db[ilen] == []:
			phrase_bin_db[ilen] = np.expand_dims(input_bits, axis=0)
		else:
			phrase_bin_db[ilen] = np.concatenate((phrase_bin_db[ilen], np.expand_dims(input_bits, axis=0)), axis=0)

		l_rphrase_changed = []
		for word_changed in changed_words:
			cl_bitvec_mgr.keep_going_num_words_changed += 1
			iword = d_words[word_changed]
			l_rphrase_changed = self.change_phrase_bin_db(l_phrases, self.__nd_el_bin_db,
													d_words, iword, l_word_phrase_ids, l_rphrase_changed)
			l_fixed_rule_pos_data = self.__d_word_in_fixed_rule.get(word_changed, [])
			for i_fixed_rule, word_pos in l_fixed_rule_pos_data:
				self.__l_fixed_rules[i_fixed_rule].update_bin_for_word(word_pos, self.__nd_el_bin_db[iword])
			# varopts.set_el_bin(self.__hcvo, iword, word_changed, self.convert_bitvec_to_arr(self.__nd_el_bin_db[iword]))
			varopts.change_el_bin(self.__hcvo, iword, self.convert_charvec_to_arr(self.__nd_el_bin_db[iword], c_bitvec_size))

		if l_rphrase_changed != []:
			self.__mpdb_mgr.apply_bin_db_changes(l_rphrase_changed)
			self.debug_test_mpdb_bins()

		return self.__nd_el_bin_db, ilen, iphrase

	def change_phrase_bin_db(self, l_phrases, nd_el_bin_db, d_words, iword, l_word_phrase_ids, l_rphrase_changed):
		phrase_bits_db = self.__phrase_bin_db
		# l_rphrase_changed = []
		for ilen, iphrase in l_word_phrase_ids[iword]:
			phrase = l_phrases[ilen][iphrase]
			input_bits = create_input_bits(nd_el_bin_db, d_words, phrase)
			phrase_bits_db[ilen][iphrase, :] = input_bits
			l_rphrase_changed.append((ilen, iphrase))
		return l_rphrase_changed


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
				s_word_bit_db.add(tuple(bits)) # if asserts here check bitvec.bitvec_size

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

