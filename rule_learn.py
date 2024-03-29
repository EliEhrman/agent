from __future__ import print_function
import math
import sys
import csv
import os
from os.path import expanduser
from shutil import copyfile
import itertools
from bitvecdb import bitvecdb

ltotup = lambda l: tuple([tuple(li) for li in l])

c_print_every = 500


def convert_charvec_to_arr(bin, size=-1):
	if size == -1:
		size = len(bin)
	bin_arr = bitvecdb.charArray(size)
	for ib in range(size): bin_arr[ib] = chr(bin[ib])
	return bin_arr


def convert_intvec_to_arr(bin, size=-1):
	if size == -1:
		size = len(bin)
	bin_arr = bitvecdb.intArray(size)
	for ib in range(size): bin_arr[ib] = int(bin[ib])
	return bin_arr


class cl_rule_event(object):
	def __init__(self, ts, rphrase, rphrase_result, ll_rphrases_close, ll_hits):
		self.__ts = ts
		self.__rphrase = rphrase
		self.__rphrase_result = rphrase_result
		self.__ll_rphrases_close = ll_rphrases_close
		self.__ll_hits = ll_hits

	def ts(self):
		return self.__ts

	def rphrase(self):
		return self.__rphrase

	def rphrase_result(self):
		return self.__rphrase_result

	def ll_rphrases_close(self):
		return self.__ll_rphrases_close

	def ll_hits(self):
		return self.__ll_hits

class cl_lrule(object):
	def __init__(self, mgr, rsg, rpg, result_rcent, var_list, creation_ts):
		self.__mgr = mgr
		self.__rsg = rsg
		self.__rpg = rpg
		self.__result_rcent = result_rcent
		self.__var_list = var_list
		self.__creation_ts = creation_ts
		self.__l_ts_hits = [creation_ts]
		self.__cdb_irec = -1
		self.__mgr_irec = -1
		self.__rpg_pct_hit = 0.
		if self.__rpg.get_b_written(): self.write_rec_new()

	def get_cdb_irec(self):
		return self.__cdb_irec

	def get_mgr_irec(self):
		return self.__mgr_irec

	def get_var_list(self):
		return self.__var_list

	def get_result_rcent(self):
		return self.__result_rcent

	def write_rec_new(self):
		self.write_rec(self.__mgr.get_hcdb(), self.__rsg.get_src_rcent(), self.__rpg.get_l_close_rcent())

	def write_rec(self, hcdb, src_rcent, l_close_rcent):
		if self.__cdb_irec != -1:
			return
		cluster_mgr = self.__mgr.get_cluster_mgr()
		bitvec_size = self.__mgr.get_bitvec_size()
		phrase_bitvec = []; cent_offsets = []; l_cent_hds = []
		plen = 0
		ll_centroids = []; ll_el_hds = []
		print('write rec:')
		# self.__rsg.print_rsg()
		self.print_lrule()
		for rcent in [src_rcent] + l_close_rcent + [self.__result_rcent]:
			if rcent < 0:
				continue
			l_centroid = cluster_mgr.get_centroid(rcent)
			ll_centroids.append(l_centroid)
			cent_len = len(l_centroid) / bitvec_size
			cent_offsets.append(plen)
			plen += cent_len
			phrase_bitvec += l_centroid
			ll_el_hds.append(cluster_mgr.get_cent_hd(rcent))
			l_cent_hds += cluster_mgr.get_cent_hd(rcent) # make one long list of all hds
		self.__cdb_irec, self.__mgr_irec = \
				self.__mgr.register_write_rec(	self.__rsg, self.__rpg, self, list(self.__var_list), ll_el_hds,
												ll_centroids, (self.__result_rcent != -1), self.__rsg.get_cid())
		# bitvecdb.add_rec(hcdb, plen, convert_charvec_to_arr(phrase_bitvec))
		# bitvecdb.set_rule_data(	hcdb, self.__cdb_irec, len(cent_offsets), convert_intvec_to_arr(cent_offsets),
		# 						convert_intvec_to_arr(l_cent_hds), len(self.__var_list),
		# 						convert_intvec_to_arr([vv for var_def in self.__var_list for vv in var_def]),
		# 						int(self.__result_rcent != -1), self.__rsg.get_cid(), -1, True)

	def is_match(self, result_rcent, var_list, ts):
		if result_rcent == self.__result_rcent and var_list == self.__var_list:
			if ts not in self.__l_ts_hits:
				self.__l_ts_hits.append(ts)
			return True
		return False

	def get_num_hits(self):
		return len(self.__l_ts_hits)

	def print_lrule(self):
		print(	'lrule: c#', self.__cdb_irec, 'mgr #',  self.__mgr_irec, 'rpg#', self.__rpg.get_irpg(), 'with', len(self.__l_ts_hits), 'hits. vars:',
				self.__var_list, 'no result' if self.__result_rcent == -1 else 'result cent:')
		self.__mgr.get_phraseperms().print_cluster(self.__result_rcent)

	def calc_rule_pct_hits(self, rpg_tot):
		if rpg_tot == 0: return
		self.__rpg_pct_hit = float(self.get_num_hits())/rpg_tot

	def get_rpg_pct_hit(self):
		return self.__rpg_pct_hit

	def load_rpg_pct_hit(self, pct_hit):
		self.__rpg_pct_hit = pct_hit

class cl_rule_phrase_grp(object):
	def __init__(self, mgr, rsg, l_rcents_close, grp_vars, l_parent_rpgs, irpg, ts):
		self.__mgr = mgr
		self.__rsg = rsg
		self.__irpg = irpg # index into rsg's list of rpgs
		self.__l_rcents_close =  l_rcents_close
		self.__grp_vars = grp_vars # vars that define the group excluding result vars
		self.__l_rules = [] #  [cl_lrule(mgr, self, -1, (), cl_rule_phrase_grp.ts)]
		self.__ll_ihits = [] # list of lists of event timestamps, top list indexed by l_rules
		self.__creation_ts = ts
		self.__tot_hits = 0 # not quite the number of hits because events that hit n l_irules, add n to this
		self.__entropy = -1.
		self.__l_base_events = []
		self.__base_entropy = -1.
		self.__l_ts_some_result = []
		self.__l_ts_no_result = []
		self.__result_entropy = -1
		self.__b_go_further = False
		self.__b_terminal = False
		self.__b_save = False
		self.__l_parent_rpgs = l_parent_rpgs # All the rpgs with one missing in l_rcents_close. None for the rpg with no close cent
		self.__b_written = False
		self.__num_test_hits_good = 0
		self.__num_test_hits_bad = 0
		self.__test_pct_hit_good = 0.
		self.__test_pct_hit_bad = 0.

	def get_irpg(self):
		return self.__irpg

	def get_l_close_rcent(self):
		return self.__l_rcents_close

	def get_result_entropy(self):
		return self.__result_entropy

	def get_l_rules(self):
		return self.__l_rules

	def assign_base_events(self, base_event_hits, b_no_result, ts):
		if base_event_hits != []:
			max_event_id = max(base_event_hits)
			grow = max_event_id + 1 - len(self.__l_base_events)
			self.__l_base_events += [[] for _ in range(grow)]
			for hit in base_event_hits:
				if ts not in self.__l_base_events[hit]: self.__l_base_events[hit].append(ts)
		if b_no_result:
			if ts not in self.__l_ts_no_result: self.__l_ts_no_result.append(ts)
		else:
			if ts not in self.__l_ts_some_result: self.__l_ts_some_result.append(ts)
		self.calc_base_entroy()

	def calc_base_entroy(self):
		e = 0.; tot = 0;
		for l_base_event in self.__l_base_events:
			tot += len(l_base_event)
		for l_base_event in self.__l_base_events:
			if l_base_event == []: continue
			n = float(len(l_base_event)) / tot
			e -= n * math.log(n, 2.0)
		self.__base_entropy = e
		del e, tot, n
		if self.__l_ts_no_result == [] or self.__l_ts_some_result == []:
			self.__result_entropy = 0
		else:
			totb = len(self.__l_ts_no_result) + len(self.__l_ts_some_result)
			n1 = float(len(self.__l_ts_no_result)) / totb
			n2 = float(len(self.__l_ts_some_result)) / totb
			self.__result_entropy = -(n1 * math.log(n1, 2.0)) - (n2 * math.log(n2, 2.0))

	def calc_rule_pct_hits(self):
		tot = 0
		for lrule in self.__l_rules:
			tot += lrule.get_num_hits()
		for lrule in self.__l_rules:
			lrule.calc_rule_pct_hits(tot)


	def is_match(self, l_rcents_close, grp_vars):
		return l_rcents_close == self.__l_rcents_close and grp_vars == self.__grp_vars

	def calc_entropy(self):
		e = 0.; tot = 0
		for lrule in self.__l_rules:
			tot += lrule.get_num_hits()
		self.__tot_hits = tot
		for lrule in self.__l_rules:
			n = float(lrule.get_num_hits())/tot
			e -= n*math.log(n, 2.0)
		self.__entropy = e

	def get_tot_hits(self):
		return self.__tot_hits

	def get_grp_vars(self):
		return self.__grp_vars

	def print_rpg(self):
		print(	'rpg. tot hits:', self.__tot_hits, '. entropy', self.__entropy,
				'. base entropy', self.__base_entropy, '. result entropy', self.__result_entropy,
				'. no close clusters' if self.__l_rcents_close == [] else '. close clusters:')
		for rcent in self.__l_rcents_close:
			self.__mgr.get_phraseperms().print_cluster(rcent)
		for lrule in self.__l_rules:
			lrule.print_lrule()

	def add_event(self, result_rcent, l_rphrases, ts):
		# if not any(lrule.is_match(result_rcent, var_list) for lrule in self.__l_rules):
		# 	self.__l_rules.append(cl_lrule(self.__mgr, self, result_rcent, var_list, cl_rule_phrase_grp.ts))

		# for rphrase_close, var_list in zip(l_rphrases_close, l_t_vars):
		# l_event_hits = []
		phrases_wlist = [self.__mgr.get_phraseperms().get_phrase(r) for r in l_rphrases]
		var_list = self.__mgr.make_var_list(phrases_wlist)

		l_ilrules = [ilrule for ilrule, lrule in enumerate(self.get_l_rules()) if lrule.is_match(result_rcent, var_list, ts)]
		if l_ilrules == []:
			l_ilrules = [len(self.__l_rules)]
			self.__l_rules.append(cl_lrule(self.__mgr, self.__rsg, self, result_rcent, var_list, ts))

		# self.__tot_hits += len(l_ilrules)
		self.calc_entropy()


		# l_event_hits.append(l_ilrules)
		return l_ilrules

	def get_b_terminal(self):
		return self.__b_terminal

	def get_b_written(self):
		return self.__b_written

	def write_lrules(self):
		for lrule in self.__l_rules:
			lrule.write_rec(self.__mgr.get_hcdb(), self.__rsg.get_src_rcent(), self.__l_rcents_close)

	def calc_status(self):
		self.__b_go_further = False
		self.__b_save = False
		self.__b_terminal = False
		if self.get_tot_hits() < c_perf_config_learn_rpg_hits:
			return
		if self.__result_entropy < 0.1:
			self.__b_go_further = False
			self.__b_terminal = True
			if self.get_tot_hits() > c_perf_config_learn_rpg_hits * 2:
				print('calc_status: get_parent_b_save')
				if not False: # self.get_parent_b_save(): # Won't hit myself 'cos we just disabled __b_save. Later. Don't think this comment is corrent
					self.__b_save = True
					if not self.__b_written:
						self.write_lrules()
						self.__b_written = True
			return
		if len(self.__l_rcents_close) <= c_perf_config_learn_min_close:
			self.__b_go_further = True
		else:
			best_parent_entropy = sys.float_info.max
			for parent_rpg in self.__l_parent_rpgs:
				parent_result_entroy = parent_rpg.get_result_entropy()
				if parent_result_entroy < best_parent_entropy:
					best_parent_entropy = parent_result_entroy
			if self.__result_entropy < best_parent_entropy * c_perf_config_learn_entropy_factor:
				self.__b_go_further = True
		# mplement parent list checking
		"""
		if len(self.__l_rcents_close) <= c_perf_config_learn_min_close or
		if len(self.__l_rcents_close) > c_perf_config_learn_min_close:
			if self.__parent_rpg != None:
				parent_result_entroy = self.__parent_rpg.get_result_entropy()
				if self.__result_entropy > parent_result_entroy * c_perf_config_learn_entropy_factor:
					return
				self.__b_save = True
				if self.__result_entropy > 0.:
					self.__b_go_further = True
		else:
			if self.__result_entropy > 0.:
				self.__b_go_further = True
			if self.__parent_rpg == None:
				if self.__result_entropy < c_perf_config_learn_entropy_abs:
					self.__b_save = True
			else:
				parent_result_entroy = self.__parent_rpg.get_result_entropy()
				if self.__result_entropy < parent_result_entroy * c_perf_config_learn_entropy_factor:
					self.__b_save = True
		"""

	def get_b_go_further(self, b_dont_calc=False):
		if not b_dont_calc:
			self.calc_status()
		return self.__b_go_further

	def get_b_save(self, b_dont_calc=False):
		if not b_dont_calc:
			self.calc_status()
		return self.__b_save

	def get_parent_b_save(self):
		if self.__b_save:
			return True
		l_rcent_close_sorted = sorted(self.__l_rcents_close)
		assert False, 'Shouldno longer need to check parent save'
		l_parent_rpgs = self.__rsg.find_parent_rpgs(l_rcent_close_sorted, self.__grp_vars)
		assert l_parent_rpgs == self.__l_parent_rpgs, 'Why arent parent lists equal?'
		for parent_rpg in self.__l_parent_rpgs:
			if parent_rpg.get_parent_b_save():
				return True
		return False

	def load_rules(self, result_rcent, var_list, rpg_pct_hit):
		self.__l_rules.append(cl_lrule(self.__mgr, self.__rsg, self, result_rcent, var_list, -1))
		self.__l_rules[-1].load_rpg_pct_hit(rpg_pct_hit)
		if self.__mgr.get_b_learn():
			self.__l_rules[-1].write_rec_new()

	def test_rule(self, mpdbs, src_rperm, idb):
		bitvec_size = self.__mgr.get_bitvec_size()
		ll_rperms_src, ll_rperms = [[src_rperm]], []
		for iclose, rcent_close in enumerate(self.__l_rcents_close):
			# plen = self.__mgr.get_phraseperms().get_cent_len(rcent_close) / bitvec_size
			cent_thresh = self.__mgr.get_phraseperms().get_cent_hd(rcent_close)
			l_cent_bits = self.__mgr.get_phraseperms().get_centroid(rcent_close)
			# num_cands, cands_arr = mpdbs.get_bdb_story().get_plen_irecs(plen, idb)
			num_cands, cands_arr = mpdbs.get_bdb_story().get_close_recs(idb, len(l_cent_bits) / bitvec_size,
																		cent_thresh, l_cent_bits)
			for rperm_combo in ll_rperms_src:
				# TBD. Do the same for the src cluster. Is anyone checking its length
				ll_eids = [self.__mgr.get_phraseperms().get_perm_eids(rperm1) for rperm1 in rperm_combo]
				iclose_vars = filter(lambda l: l[2] == (iclose + 1), self.__grp_vars)
				num_match, match_arr = num_cands, cands_arr
				for one_var in iclose_vars:
					src_eid = ll_eids[one_var[0]][one_var[1]]
					num_match, match_arr = \
						mpdbs.get_bdb_story().get_rperms_with_eid_at(idb, src_eid, one_var[3], num_match, match_arr)
				for imatch in range(num_match):
					ll_rperms.append(rperm_combo + [match_arr[imatch]])
					pass
			if ll_rperms == []: return []
			ll_rperms_src = list(ll_rperms)
			ll_rperms = []

		return ll_rperms_src

	def add_test_stat(self, bcorrect, lrule_pct_hit):
		if bcorrect:
			self.__num_test_hits_good += 1
			self.__test_pct_hit_good += lrule_pct_hit
		else:
			self.__num_test_hits_bad += 1
			self.__test_pct_hit_bad += lrule_pct_hit

c_perf_config_learn_rpg_hits = 5 # 10
c_perf_config_learn_entropy_factor = .9
c_perf_config_learn_entropy_abs = .8
c_perf_config_learn_max_close = 3
c_perf_config_learn_min_close = 1 # rpg's with <= num of close cents (phrases beside the first) go further as soon as they have enough hits without entropy drop requirements

class cl_rule_src_grp(object):

	def __init__(self, mgr, phrase_rcent, ts, cid):
		self.__mgr = mgr
		self.__phrase_rcent = phrase_rcent
		self.__l_rpgs = []
		self.__l_rpg_var_lists = []  # indexed as l_rpgs
		self.__l_events = []
		self.__creation_ts = ts
		self.__num_hits = 0
		self.__cid = cid

	def get_cid(self):
		return self.__cid

	def get_src_rcent(self):
		return self.__phrase_rcent

	def print_rsg(self):
		print('---------------> rsg cluster hit', self.__num_hits, 'times. src centroid:')
		print('rsg for ')
		self.__mgr.get_phraseperms().print_cluster(self.__phrase_rcent)
		for rpg in self.__l_rpgs:
			if not rpg.get_b_save(): continue
			rpg.print_rpg()

	def get_num_hits(self):
		return self.__num_hits

	def find_rpg(self, l_rcent_close, t_vars):
		rpg = None; irpg = -1
		for irpg_test, rpg_test in enumerate(self.__l_rpgs):
			if rpg_test.is_match(l_rcent_close, t_vars):
				rpg = rpg_test; irpg = irpg_test
				break
		return irpg, rpg

	def find_removed_rpg(self, l_parent_rpgs, l_imm, src_rphrase, l_rphrase_close, l_rcent_close, bimm):
		for irphrase, rphrase in enumerate(l_rphrase_close):
			l_rphrase_copy = list(l_rphrase_close)
			l_rcent_copy = list(l_rcent_close)
			del l_rphrase_copy[irphrase]; del l_rcent_copy[irphrase]
			phrases_wlist = [self.__mgr.get_phraseperms().get_phrase(r) for r in [src_rphrase] + l_rphrase_copy]
			t_vars_grp, canon_iorder = self.__mgr.make_canon_var_list(phrases_wlist)
			l_rcent_close_canon = [l_rcent_copy[i-1] for i in canon_iorder if i > 0]
			_, parent_rpg = self.find_rpg(l_rcent_close_canon, t_vars_grp)
			if parent_rpg != None:
				if parent_rpg not in l_parent_rpgs:
					l_parent_rpgs.append(parent_rpg)
					l_imm.append(bimm)
			if l_rphrase_copy != []:
				self.find_removed_rpg(l_parent_rpgs, l_imm, src_rphrase, l_rphrase_copy, l_rcent_copy, False)

	def find_parent_rpg_by_phrase(self, src_rphrase, l_rphrase_close, l_rcent_close):
		l_parent_rpgs= []; l_immediate = []
		self.find_removed_rpg(l_parent_rpgs, l_immediate, src_rphrase, l_rphrase_close, l_rcent_close, True)
		return l_parent_rpgs, l_immediate

	def find_parent_rpgs(self, l_rcent_close_sorted, t_vars_grp):
		l_parent_rpgs= []
		for ircent_close, rcent_close in enumerate(l_rcent_close_sorted):
			l_copy = list(l_rcent_close_sorted)
			del l_copy[ircent_close]
			# parents must be a list.
			parent_vars = ()
			vpos = ircent_close + 1  # in vars, src is 0 and the first close is 1
			for avar in t_vars_grp:
				if avar[0] == vpos or avar[2] == vpos: continue
				spos = avar[0] if avar[0] < vpos else avar[0] - 1
				dpos = avar[2] if avar[2] < vpos else avar[2] - 1
				parent_vars = parent_vars + ((spos, avar[1], dpos, avar[3]),)
			_, parent_rpg = self.find_rpg(l_copy, parent_vars)
			if parent_rpg != None:
				if parent_rpg not in l_parent_rpgs: l_parent_rpgs.append(parent_rpg)
		return l_parent_rpgs

	def add_event(	self, rphrase, rphrase_result, result_rcent, l_rphrases_close, l_rcent_close, t_vars, canon_iorder,
					base_event_hits_src, ts):
		self.__num_hits += 1
		l_event_hits = []
		# l_rpgs = []
		base_event_hits = []
		# t_vars_grp = filter(lambda l: l[2] != result_idx, t_vars)
		# l_rphrases_close_sorted = [x for x,y in sorted(zip(l_rphrases_close, l_rcent_close), key = lambda x: x[1])]
		# l_rcent_close_sorted = sorted(l_rcent_close)
		grp_rphrases = [rphrase]+l_rphrases_close
		phrases_wlist = [self.__mgr.get_phraseperms().get_phrase(r) for r in grp_rphrases]
		t_vars_grp, canon_grp_iorder = self.__mgr.make_canon_var_list(phrases_wlist)
		l_rphrases_close_canon = [l_rphrases_close[i-1] for i in canon_grp_iorder if i > 0]
		l_rcent_close_canon = [l_rcent_close[i-1] for i in canon_grp_iorder if i > 0]
		l_parent_rpgs, l_bimm_parent = self.find_parent_rpg_by_phrase(rphrase, l_rphrases_close_canon, l_rcent_close_canon)
		b_parent_wants_further = False
		# check that one of the parents actually wants to move further and this is not just because some other guy's parent added to the list
		for parent_rpg, bimm in zip(l_parent_rpgs, l_bimm_parent):
			if bimm and parent_rpg.get_b_go_further(b_dont_calc=True): b_parent_wants_further = True
			if parent_rpg.get_b_terminal():
				return None, [], False
			del parent_rpg
		if l_rcent_close == []: b_parent_wants_further = True
		if not b_parent_wants_further: return None, [], False

		# t_vars_grp = self.__mgr.get_grp_vars([rphrase]+l_rphrases_close_sorted) # sorted(l_rcent_close))
		# irpg, rpg = self.find_rpg(l_rcent_close_sorted, t_vars_grp)
		irpg, rpg = self.find_rpg(l_rcent_close_canon, t_vars_grp)
		if irpg == 111:
			print('irpg', irpg,  'result: phrases:', phrases_wlist, '\n vars', rpg.get_grp_vars(), 'hits:', rpg.get_tot_hits())
			rpg.print_rpg()

		if rpg == None:
			# l_parent_rpgs = []
			# b_parent_wants_further = False
			# l_parent_rpgs = self.find_parent_rpgs(l_rcent_close_sorted, t_vars_grp)
			# for parent_rpg in l_parent_rpgs:
			# 	if parent_rpg.get_b_go_further(b_dont_calc=True): b_parent_wants_further = True
			# 	del parent_rpg

			# if l_rcent_close == []: b_parent_wants_further = True
			# assert b_parent_wants_further, 'Warning. Strange that got here without parental approval'
			# if not b_parent_wants_further:
			# 	return None, [], False
			assert not (l_rcent_close != [] and l_parent_rpgs == []), 'error'
			# rpg = cl_rule_phrase_grp(self.__mgr, self, l_rcent_close_sorted, t_vars_grp, l_parent_rpgs, ts)
			irpg = len(self.__l_rpgs)
			rpg = cl_rule_phrase_grp(self.__mgr, self, l_rcent_close_canon, t_vars_grp, l_parent_rpgs, irpg, ts)
			self.__l_rpgs.append(rpg)
		# event_hits =  rpg.add_event(result_rcent, t_vars, ts)
		l_all_rphrases = [rphrase] + l_rphrases_close_canon + ([] if result_rcent == -1 else [rphrase_result])
		event_hits =  rpg.add_event(result_rcent, l_all_rphrases, ts)
		l_event_hits.append([irpg, event_hits])
		if l_rcent_close == []:
			base_event_hits = event_hits
		else:
			base_event_hits = base_event_hits_src
		# if rpg not in l_rpgs: l_rpgs.append(rpg)
		# del rpg
		# for rpg in l_rpgs:
		rpg.assign_base_events(base_event_hits, result_rcent == -1, ts)
		# self.__l_events.append(cl_rule_event(ts, rphrase, rphrase_result, ll_rphrases_close, l_event_hits))
		return rpg, event_hits, rpg.get_b_go_further()


	def load_rpgs(self, l_rcent_close, result_rcent, t_vars, rpg_pct_hit):
		result_idx = len(l_rcent_close) + 1
		# l_rcent_close_sorted = sorted(l_rcent_close)
		t_vars_grp = filter(lambda l: l[2] != result_idx, t_vars)
		irpg, rpg = self.find_rpg(l_rcent_close, t_vars_grp)
		if rpg == None:
			# assert False, 'Why are we losing the parent information?'
			irpg = len(self.__l_rpgs)
			rpg = cl_rule_phrase_grp(self.__mgr, self, l_rcent_close, t_vars_grp, [], irpg, 0)
			self.__l_rpgs.append(rpg)
		rpg.load_rules(result_rcent, t_vars, rpg_pct_hit)



class cl_lrule_mgr(object):
	ts = 0
	max_combos = 0

	def __init__(self, phrase_mgr, phraseperms, rules_fnt, lrn_rule_fn, rule_mgr):
		self.__rules_fnt = rules_fnt
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms
		self.__d_rsgs = dict() # keyed by (cid, src_rcent) points to rsg object
		self.__last_print = c_print_every
		self.__l_write_recs = []
		self.__b_learn = (lrn_rule_fn == 'learn')
		self.__hcdb_rules = rule_mgr.get_hcdb_rules() #  bitvecdb.init_capp()
		self.__test_stat_num_rules_found = 0
		self.__test_stat_num_rules_not_found = 0
		self.__s_special_eids = set() # Set of eids important enough to define close phrases
		self.__rule_mgr = rule_mgr # overall rule mgr that includes both external rules and references to the lrules learned here
		self.__l_flat_rules = [] # a way of storing rules using their rcents and var list without the native rsg, rpg, lrule tree
		# bitvecdb.set_name(self.__hcdb_rules, 'rules')
		# bitvecdb.set_b_rules(self.__hcdb_rules)
		self.__bitvec_size = self.__phraseperms.get_nlb_mgr().get_bitvec_size()
		# bitvecdb.set_el_bitvec_size(self.__hcdb_rules, self.__bitvec_size)
		rule_mgr.register_rule_learner(self)
		# if not self.__b_learn:
		if lrn_rule_fn == 'load':
			self.load_rules()
		pass

	# def get_hcdb_rules(self):
	def get_b_learn(self):
		return self.__b_learn

	def set_special_words(self, l_special_words, nlb_el_mgr):
		for word in l_special_words:
			self.__s_special_eids.add(nlb_el_mgr.get_el_id(word))


	def get_phraseperms(self):
		return self.__phraseperms

	def get_hcdb(self):
		return self.__hcdb_rules

	def get_cluster_mgr(self):
		return self.__phraseperms.get_cluster_mgr()

	def get_bitvec_size(self):
		return self.__bitvec_size

	def convert_phrase_to_word_list(self, stmt):
		return [el[1] for el in stmt]

	def full_split(self, stmt):
		return [w for lw in [el.split() for el in stmt] for w in lw]

	def make_var_list(self, l_phrases):
		l_vars = ()
		vars_dict = dict()
		for iphrase, phrase in enumerate(l_phrases):
			for iel, el in enumerate(phrase):
				src_pos = vars_dict.get(el, ())
				if src_pos == ():
					vars_dict[el] = (iphrase, iel)
				else:
					src_iphrase, src_iel = src_pos
					l_vars += (src_iphrase, src_iel, iphrase, iel),
		return l_vars

	def make_canon_var_list(self, l_src_phrases):
		def cmp_quads(q1, q2):
			if q1[0] > q2[0]:
				return 1
			if q1[0] < q2[0]:
				return -1
			if q1[1] > q2[1]:
				return 1
			if q1[1] < q2[1]:
				return -1
			if q1[3] > q2[3]:
				return 1
			if q1[3] < q2[3]:
				return -1
			return 0

		l_iorder = range(len(l_src_phrases))
		b_keep_going = True
		isanity = 100
		swap_set = set()
		while b_keep_going:
			if isanity <= 0:
				print('make_canon_var_list in endless loop.')
				return l_vars, l_iorder
			l_phrases = [l_src_phrases[i] for i in l_iorder]
			l_vars = self.make_var_list(l_phrases)
			l_vars = sorted(l_vars, cmp=cmp_quads)
			l_bmentioned = [False for _ in l_phrases]
			l_bmentioned[0] = True
			highest_mentioned = 0
			b_keep_going = False
			for one_var in l_vars:
				i_dest_phrase = one_var[2]
				if i_dest_phrase == 0: continue  # don't move the first phrase
				if not l_bmentioned[i_dest_phrase]:
					if highest_mentioned > i_dest_phrase:
						assert highest_mentioned != 0
						swap_pair = (i_dest_phrase, highest_mentioned)
						if swap_pair in swap_set:
							print('looping badly.')
							return l_vars, l_iorder
						swap_set.add(swap_pair)
						t = l_iorder[i_dest_phrase]
						l_iorder[i_dest_phrase] = l_iorder[highest_mentioned]
						l_iorder[highest_mentioned] = t
						b_keep_going = True
						break
					highest_mentioned = i_dest_phrase
					l_bmentioned[i_dest_phrase] = True

		return l_vars, l_iorder


	# def test_rule(self, mpdbs, stmt, l_results, idb):
	# 	phrase = self.full_split(stmt)
	# 	result_words = ''
	# 	if l_results != []:
	# 		result_words = ' '.join(self.full_split(self.convert_phrase_to_word_list(l_results[0][1:]))).lower()
	# 	print('Testing rules for', phrase)
	# 	rphrase = self.__phrase_mgr.get_rphrase(phrase)
	# 	l_rperms = self.__phraseperms.get_perms(rphrase)
	# 	# The maximum theoretical returns is the num of rules * the number of source perms
	# 	num_poss_ret = len(self.__l_write_recs) * len(l_rperms)
	# 	irule_arr = bitvecdb.intArray(num_poss_ret); rperms_ret_arr = bitvecdb.intArray(num_poss_ret)
	# 	rperms_arr = convert_intvec_to_arr(l_rperms)
	# 	num_rules_found = bitvecdb.find_matching_rules(	self.__hcdb_rules, irule_arr, rperms_ret_arr,
	# 													self.__phraseperms.get_bdb_all_hcdb(), len(l_rperms), rperms_arr, b_hd_per_el = False)
	# 	for iret in range(num_rules_found):
	# 		rsg, rpg, lrule = self.__l_write_recs[irule_arr[iret]]
	# 		rperm_ret = rperms_ret_arr[iret]
	# 		ll_rperms = rpg.test_rule(mpdbs, rperm_ret, idb)
	# 		if ll_rperms == []: continue
	# 		result_rcent = lrule.get_result_rcent()
	# 		if result_rcent == -1:
	# 			print('no result')
	# 			rpg.add_test_stat(result_words == '', lrule.get_rpg_pct_hit())
	# 			continue
	# 		result_cent_stmt = self.__phraseperms.get_cluster_mgr().get_cluster_words(result_rcent)
	# 		for l_rperms in ll_rperms:
	# 			result_stmt = list(result_cent_stmt)
	# 			ll_eids = [self.get_phraseperms().get_perm_eids(rperm) for rperm in l_rperms]
	# 			iclose_vars = filter(lambda l: l[2] == len(l_rperms), lrule.get_var_list())
	# 			for one_var in iclose_vars:
	# 				result_stmt[one_var[3]] = self.__phraseperms.get_nlb_mgr().get_el_by_eid(ll_eids[one_var[0]][one_var[1]])
	# 			print('result:', result_stmt)
	# 			rpg.add_test_stat(' '.join(result_stmt).lower() == result_words, lrule.get_rpg_pct_hit())
	# 			# join to space. Add up all the results for the rpg
	# 	if num_rules_found > 0:
	# 		self.__test_stat_num_rules_found += 1
	# 	else:
	# 		self.__test_stat_num_rules_not_found += 1
	# 	pass

	def test_rule(self, irule, rperm_ret, result_words, mpdbs, idb):
			rsg, rpg, lrule = self.__l_write_recs[irule]
			ll_rperms = rpg.test_rule(mpdbs, rperm_ret, idb)
			if ll_rperms == []: return False
			result_rcent = lrule.get_result_rcent()
			if result_rcent == -1:
				print('no result')
				rpg.add_test_stat(result_words == '', lrule.get_rpg_pct_hit())
				return False
			result_cent_stmt = self.__phraseperms.get_cluster_mgr().get_cluster_words(result_rcent)
			for l_rperms in ll_rperms:
				result_stmt = list(result_cent_stmt)
				ll_eids = [self.get_phraseperms().get_perm_eids(rperm) for rperm in l_rperms]
				iclose_vars = filter(lambda l: l[2] == len(l_rperms), lrule.get_var_list())
				for one_var in iclose_vars:
					result_stmt[one_var[3]] = self.__phraseperms.get_nlb_mgr().get_el_by_eid(ll_eids[one_var[0]][one_var[1]])
				print('result:', result_stmt)
				rpg.add_test_stat(' '.join(result_stmt).lower() == result_words, lrule.get_rpg_pct_hit())
			return True
				# join to space. Add up all the results for the rpg

	def learn_rule(self, mpdbs, stmt, l_results, phase_data, idb, rule_cat):
		cid = self.__rule_mgr.get_cid(rule_cat)
		if not self.__b_learn:
			assert False, ('Error Must call rules3 test_rule!!!!!!!!!!!!!!!!!')
			self.test_rule(mpdbs, stmt, l_results, idb, )
			return
		map_rphrase_to_s_rcents = dict()
		type(self).ts += 1
		phrase = self.full_split(stmt)
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		s_src_rcents = set(self.__phraseperms.get_cluster(rphrase))
		map_rphrase_to_s_rcents[rphrase] = s_src_rcents
		if s_src_rcents == set():
			return

		if l_results == []:
			result = []
			result_rphrase = -1
			s_result_rcents = set([-1])
		else:
			result = self.full_split(self.convert_phrase_to_word_list(l_results[0][1:]))
			result_rphrase = self.__phrase_mgr.get_rphrase(result)
			s_result_rcents = set(self.__phraseperms.get_cluster(result_rphrase))
			if s_src_rcents == set():
				return
			map_rphrase_to_s_rcents[result_rphrase] = s_result_rcents

		t_vars = self.make_var_list([phrase] + [result])
		ll_rphrases_close = [[]]; l_t_vars = [t_vars]; l_canon_iorder = [[]]
		num_phrase_combos = 1; curr_combo = 0
		base_event_hits = []
		while curr_combo < len(ll_rphrases_close):
			if curr_combo > type(self).max_combos:
				type(self).max_combos = curr_combo
				print('type(self).max_combos', type(self).max_combos)

			for src_rcent in s_src_rcents:
				rsg = self.__d_rsgs.get((cid, src_rcent), None)
				if rsg == None:
					rsg = cl_rule_src_grp(self, src_rcent, type(self).ts, cid)
					self.__d_rsgs[(cid, src_rcent)] = rsg
				for result_rcent in s_result_rcents:
					l_rphrases_close = ll_rphrases_close[curr_combo]
					if l_rphrases_close == []:
						l_combos = [[]]
					else:
						ll_cents = []
						for rp1 in l_rphrases_close:
							s_rc1 = map_rphrase_to_s_rcents.get(rp1, None)
							if s_rc1 == None:
								s_rc1 = set(self.__phraseperms.get_cluster(rp1))
								map_rphrase_to_s_rcents[rp1] = s_rc1
							ll_cents.append(list(s_rc1))
						l_combos = itertools.product(*ll_cents)
						# l = list(l_combos)
					for cent_combo in l_combos:
						event_rpg, event_hits, bfurther = \
							rsg.add_event(	rphrase, result_rphrase, result_rcent, l_rphrases_close, list(cent_combo),
											l_t_vars[curr_combo], l_canon_iorder[curr_combo],
											base_event_hits, type(self).ts)
						if l_rphrases_close == []: base_event_hits = event_hits
						if bfurther:
							all_rphrases = [rphrase] + l_rphrases_close
							s_rphrases_close_new \
									= mpdbs.get_bdb_story().get_matching_rphrases(	idb, all_rphrases[-1],
																					all_rphrases[:-1], self.__s_special_eids)
							# add one of the close and check against the list to see if its there already
							for rphrase_close_new in s_rphrases_close_new:
								l_rphrases_close_new = sorted(l_rphrases_close + [rphrase_close_new])
								if l_rphrases_close_new in ll_rphrases_close:
									continue
								ll_rphrases_close.append(l_rphrases_close_new)
								phrases_list = [phrase] + [self.__phraseperms.get_phrase(r) for r in l_rphrases_close_new] \
												+ [result]
								canon_vars, l_iorder = self.make_canon_var_list(phrases_list)
								l_t_vars.append(canon_vars)
								l_canon_iorder.append(l_iorder)
			# end loop over src_rcent
			curr_combo += 1

		if type(self).ts > self.__last_print and self.__b_learn:
			print('---> start rules learned at timestamp:', type(self).ts)
			for (cid, src_rcent), rsg in self.__d_rsgs.iteritems():
				if rsg.get_num_hits() < 10: continue
				rsg.print_rsg()
			self.__last_print += c_print_every
			print('---> end rules learned at timestamp:', type(self).ts)
			self.save_rules()
			exit()
		pass

	def get_grp_vars(self, l_rphrases):
		phrases_list = [self.__phraseperms.get_phrase(r) for r in l_rphrases]
		return self.make_var_list(phrases_list)

	def register_write_rec(self, rsg, rpg, lrule, ll_var_list, ll_thresh_hds, ll_centroids, b_has_result, cid):
		mgr_irec = len(self.__l_write_recs)
		self.__l_write_recs.append((rsg, rpg, lrule),)
		ll_phrase_data = []
		d_vars = dict()
		for l_vars in ll_var_list:
			d_vars[(l_vars[2:4])] = l_vars[:2]
		s_words_used = set()
		for iphrase, l_centroid in enumerate(ll_centroids):
			phrase_data = []
			cent_len = len(l_centroid) / self.__bitvec_size
			for iel in range(cent_len):
				t_src = d_vars.get((iphrase, iel), ())
				if t_src == ():
					el_bits = l_centroid[iel * self.__bitvec_size:(iel + 1) * self.__bitvec_size]
					word = self.__phraseperms.get_nlb_mgr().dbg_closest_word(el_bits, s_words_used)
					s_words_used.add(word)
					phrase_data.append(word)
				else:
					if t_src[0] == iphrase:
						phrase_data.append(phrase_data[t_src[1]])
					else:
						try:
							phrase_data.append(ll_phrase_data[t_src[0]][t_src[1]])
						except:
							print('Crashing. len(ll_phrase_data)', len(ll_phrase_data), 't_src', t_src, 'len(ll_phrase_data[t_src[0]])', len(ll_phrase_data[t_src[0]]))
							print('ll_var_list', ll_var_list)
							print('ll_phrase_data', ll_phrase_data)
							exit(1)
			ll_phrase_data.append(phrase_data)
		rule_name = 'lrule'+str(mgr_irec)
		cdb_irec = self.__rule_mgr.register_lrule(	mgr_irec, ll_var_list, ll_thresh_hds, ll_phrase_data, b_has_result,
													cid, rule_name, d_vars)
		return cdb_irec, mgr_irec

	def save_rules(self):
		fn = expanduser(self.__rules_fnt)

		write_pct_thresh = self.__rule_mgr.get_play_mod().c_write_pct_thresh
		num_rules_to_write = 0
		for irec, write_rec in enumerate(self.__l_write_recs):
			rsg, rpg, lrule = write_rec
			rpg.calc_rule_pct_hits()
			if lrule.get_rpg_pct_hit() > write_pct_thresh:
				num_rules_to_write += 1


		if os.path.isfile(fn):
			copyfile(fn, fn + '.bak')
		fh = open(fn, 'wb')
		csvw = csv.writer(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
		csvw.writerow(['nlbitvec rules', 'Version', '3'])
		csvw.writerow(['Num Rules:', num_rules_to_write])
		csvw.writerow(['cat name', 'Num Close', 'src cent', 'list close cents', 'rpg pct hit', 'result cent', 'num vars', 'var list'])
		for irec, write_rec in enumerate(self.__l_write_recs):
			rsg, rpg, lrule = write_rec
			if lrule.get_rpg_pct_hit() <= write_pct_thresh: continue
			# rpg.calc_rule_pct_hits()
			src_rcent = rsg.get_src_rcent()
			l_close_rcent = rpg.get_l_close_rcent()
			var_list, result_rcent = lrule.get_var_list(), lrule.get_result_rcent()
			l_var_ints = [vv for var_def in var_list for vv in var_def]
			cat_name = self.__rule_mgr.get_cid_name(rsg.get_cid())
			csvw.writerow([cat_name, len(l_close_rcent), src_rcent]+l_close_rcent + [lrule.get_rpg_pct_hit()] + [result_rcent] + [len(var_list)] + l_var_ints )

		fh.close()

	class cl_flat_rule(object):
		def __init__(self, cat_name, src_rcent, l_close_rcent, result_rcent, var_list):
			self.__cat_name = cat_name
			self.__src_rcent = src_rcent
			self.__l_close_rcents = l_close_rcent
			self.__result_rcent = result_rcent
			self.__var_list = var_list

		def create_rule_like_fixed(self, phraseperms_mgr):
			ll_phrase_data = []; ll_el_hds = []
			l_cluster_mgr = phraseperms_mgr.get_cluster_mgr()
			ll_phrase_data.append(l_cluster_mgr.get_cluster_words(self.__src_rcent))
			ll_el_hds.append(l_cluster_mgr.get_cent_hd(self.__src_rcent))
			for close_rcent in self.__l_close_rcents:
				ll_phrase_data.append(l_cluster_mgr.get_cluster_words(close_rcent))
				ll_el_hds.append(l_cluster_mgr.get_cent_hd(close_rcent))
			if self.__result_rcent != -1:
				ll_phrase_data.append(l_cluster_mgr.get_cluster_words(self.__result_rcent))
				ll_el_hds.append(l_cluster_mgr.get_cent_hd(self.__result_rcent))
			# a cosmetic clean-up
			for one_var in self.__var_list:
				ll_phrase_data[one_var[2]][one_var[3]] = ll_phrase_data[one_var[0]][one_var[1]]
			return self.__cat_name, None, ll_phrase_data, [], self.__var_list, ll_el_hds, (self.__result_rcent != -1)

	def get_flat_rules(self):
		if self.__b_learn:
			return [] # currently we add rules loaded to the ext_rule_mgr only if we are not learning
		return self.__l_flat_rules

	def load_rules(self):
		fn = expanduser(self.__rules_fnt)
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				assert version_str == '3', 'cl_rule_mgr load rules. Wrong version'
				_, snum_rules = next(csvr)
				next(csvr)
				for irow, row in enumerate(csvr):
					cat_name = row[0]
					num_close, src_rcent = map(int, row[1:3])
					l_close_rcent = map(int, row[3:num_close+3]) if num_close > 0 else []
					rpg_pct_hit = float(row[num_close+3])
					result_rcent, num_vars = map(int, row[num_close+4:num_close+6])
					l_var_int = map(int, row[num_close+6:])
					assert len(l_var_int) == num_vars * 4, 'load_rules: bad num vars'
					var_list = tuple([tuple(l_var_int[i:i+4]) for i in range(0,num_vars*4,4)])
					cid = self.__rule_mgr.get_cid(cat_name)
					rsg = self.__d_rsgs.get((cid, src_rcent), None)
					if rsg == None:
						rsg = cl_rule_src_grp(self, src_rcent, type(self).ts, cid)
						self.__d_rsgs[(cid, src_rcent)] = rsg
					rsg.load_rpgs(l_close_rcent, result_rcent, var_list, rpg_pct_hit)
					self.__l_flat_rules.append(self.cl_flat_rule(cat_name, src_rcent, l_close_rcent, result_rcent, var_list))
		except IOError:
			print('Cannot open or read ', fn)
