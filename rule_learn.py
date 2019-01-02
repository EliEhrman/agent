from __future__ import print_function
import math
import sys
import itertools
import rules2

ltotup = lambda l: tuple([tuple(li) for li in l])

c_print_every = 500

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

	def is_match(self, result_rcent, var_list, ts):
		if result_rcent == self.__result_rcent and var_list == self.__var_list:
			if ts not in self.__l_ts_hits:
				self.__l_ts_hits.append(ts)
			return True
		return False

	def get_num_hits(self):
		return len(self.__l_ts_hits)

	def print_lrule(self):
		print(	'lrule: with', len(self.__l_ts_hits), 'hits. vars:', self.__var_list,
				'no result' if self.__result_rcent == -1 else 'result cent:')
		self.__mgr.get_phraseperms().print_cluster(self.__result_rcent)

class cl_rule_phrase_grp(object):
	def __init__(self, mgr, rsg, l_rcents_close, grp_vars, l_parent_rpgs, ts):
		self.__mgr = mgr
		self.__rsg = rsg
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
		self.__b_save = False
		self.__l_parent_rpgs = l_parent_rpgs # All the rpgs with one missing in l_rcents_close. None for the rpg with no close cent

	def get_result_entropy(self):
		return self.__result_entropy

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

	def print_rpg(self):
		print(	'rpg. tot hits:', self.__tot_hits, '. entropy', self.__entropy,
				'. base entropy', self.__base_entropy, '. result entropy', self.__result_entropy,
				'. no close clusters' if self.__l_rcents_close == [] else '. close clusters:')
		for rcent in self.__l_rcents_close:
			self.__mgr.get_phraseperms().print_cluster(rcent)
		for lrule in self.__l_rules:
			lrule.print_lrule()

	def add_event(self, result_rcent, var_list, ts):
		# if not any(lrule.is_match(result_rcent, var_list) for lrule in self.__l_rules):
		# 	self.__l_rules.append(cl_lrule(self.__mgr, self, result_rcent, var_list, cl_rule_phrase_grp.ts))

		# for rphrase_close, var_list in zip(l_rphrases_close, l_t_vars):
		# l_event_hits = []
		l_ilrules = [ilrule for ilrule, lrule in enumerate(self.__l_rules) if lrule.is_match(result_rcent, var_list, ts)]
		if l_ilrules == []:
			l_ilrules = [len(self.__l_rules)]
			self.__l_rules.append(cl_lrule(self.__mgr, self.__rsg, self, result_rcent, var_list, ts))

		# self.__tot_hits += len(l_ilrules)
		self.calc_entropy()


		# l_event_hits.append(l_ilrules)
		return l_ilrules



	def calc_status(self):
		self.__b_go_further = False
		self.__b_save = False
		if self.get_tot_hits() < c_perf_config_learn_rpg_hits:
			return
		if self.__result_entropy < 0.1:
			self.__b_go_further = False
			if self.get_tot_hits() > c_perf_config_learn_rpg_hits * 3:
				if not self.get_parent_b_save(): # Won't hit myself 'cos we just disabled __b_save
					self.__b_save = True
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
		for parent_rpg in self.__l_parent_rpgs:
			if parent_rpg.get_parent_b_save():
				return True
		return False

c_perf_config_learn_rpg_hits = 10
c_perf_config_learn_entropy_factor = .9
c_perf_config_learn_entropy_abs = .8
c_perf_config_learn_max_close = 3
c_perf_config_learn_min_close = 1

class cl_rule_src_grp(object):

	def __init__(self, mgr, phrase_rcent, ts):
		self.__mgr = mgr
		self.__phrase_rcent = phrase_rcent
		self.__l_rpgs = []
		self.__l_rpg_var_lists = [] # indexed as l_rpgs
		self.__l_events = []
		self.__creation_ts = ts
		self.__num_hits = 0

	def print_rsg(self):
		print('---------------> rsg cluster hit', self.__num_hits, 'times. src centroid:')
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

	def add_event(	self, rphrase, rphrase_result, result_rcent, l_rphrases_close, l_rcent_close, t_vars,
					base_event_hits_src, ts):
		self.__num_hits += 1
		l_event_hits = []
		# l_rpgs = []
		base_event_hits = []
		# t_vars_grp = filter(lambda l: l[2] != result_idx, t_vars)
		l_rphrases_close_sorted = [x for x,y in sorted(zip(l_rphrases_close, l_rcent_close), key = lambda x: x[1])]
		l_rcent_close_sorted = sorted(l_rcent_close)
		t_vars_grp = self.__mgr.get_grp_vars([rphrase]+l_rphrases_close_sorted) # sorted(l_rcent_close))
		irpg, rpg = self.find_rpg(l_rcent_close_sorted, t_vars_grp)
		# remove soon
		# rpg = None; irpg = -1
		# for irpg_test, rpg_test in enumerate(self.__l_rpgs):
		# 	if rpg_test.is_match(l_rcent_close_sorted, t_vars_grp):
		# 		rpg = rpg_test; irpg = irpg_test
		# 		break
		# end remove soon
		if rpg == None:
			last_close_idx = len(l_rcent_close)
			l_parent_rpgs = []
			b_parent_wants_further = False
			for ircent_close, rcent_close in enumerate(l_rcent_close_sorted):
				l_copy = list(l_rcent_close_sorted)
				del l_copy[ircent_close]
				# parents must be a list.
				parent_vars = (); vpos = ircent_close + 1 # in vars, src is 0 and the first close is 1
				for avar in t_vars_grp:
					if avar[0] == vpos or avar[2] == vpos: continue
					spos = avar[0] if avar[0] < vpos else avar[0] - 1
					dpos = avar[2] if avar[2] < vpos else avar[2] - 1
					parent_vars = parent_vars + ((spos, avar[1], dpos, avar[3]),)
				_, parent_rpg = self.find_rpg(l_copy, parent_vars)
				if parent_rpg != None:
					if parent_rpg.get_b_go_further(b_dont_calc=True): b_parent_wants_further = True
					if parent_rpg not in l_parent_rpgs: l_parent_rpgs.append(parent_rpg)
				del parent_rpg

			# check that one of the parents actually wants to move further and this is not just because some other guy's parent added to the list
			if l_rcent_close == []: b_parent_wants_further = True
			if not b_parent_wants_further:
				return None, [], False
			assert not (l_rcent_close_sorted != [] and l_parent_rpgs == []), 'error'
			rpg = cl_rule_phrase_grp(self.__mgr, self, l_rcent_close_sorted, t_vars_grp, l_parent_rpgs, ts)
			irpg = len(self.__l_rpgs)
			self.__l_rpgs.append(rpg)
		event_hits =  rpg.add_event(result_rcent, t_vars, ts)
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


	def add_event_old(self, rphrase, rphrase_result, result_rcent, ll_rphrases_close, ll_rcents_close, l_t_vars, ts):
		self.__num_hits += 1
		l_event_hits = []
		l_rpgs = []
		base_event_hits = []
		for l_rcent_close, t_vars in zip(ll_rcents_close, l_t_vars):
			result_idx = len(l_rcent_close) + 1
			t_vars_grp = filter(lambda l: l[2] != result_idx, t_vars)
			rpg = None;
			irpg = -1
			for irpg_test, rpg_test in enumerate(self.__l_rpgs):
				if rpg_test.is_match(l_rcent_close, t_vars_grp):
					rpg = rpg_test;
					irpg = irpg_test
					break
			if rpg == None:
				rpg = cl_rule_phrase_grp(self.__mgr, self, l_rcent_close, t_vars_grp, ts)
				irpg = len(self.__l_rpgs)
				self.__l_rpgs.append(rpg)
			event_hits = rpg.add_event(result_rcent, t_vars, ts)
			l_event_hits.append([irpg, event_hits])
			if l_rcent_close == []:
				base_event_hits = event_hits
			if rpg not in l_rpgs: l_rpgs.append(rpg)
			del rpg
		for rpg in l_rpgs:
			rpg.assign_base_events(base_event_hits, result_rcent == -1, ts)
		self.__l_events.append(cl_rule_event(ts, rphrase, rphrase_result, ll_rphrases_close, l_event_hits))


class cl_lrule_mgr(object):
	ts = 0

	def __init__(self, phrase_mgr, phraseperms):
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms
		self.__d_lrules = dict()
		self.__last_print = c_print_every
		pass

	def get_phraseperms(self):
		return self.__phraseperms

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

	def learn_rule(self, mpdbs, stmt, l_results, phase_data, idb):
		map_rphrase_to_s_rcents = dict()
		type(self).ts += 1
		phrase = self.full_split(stmt)
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		s_src_rcents = set(self.__phraseperms.get_cluster(rphrase))
		map_rphrase_to_s_rcents[rphrase] = s_src_rcents

		if l_results == []:
			result = []
			result_rphrase = -1
			s_result_rcents = set([-1])
		else:
			result = self.full_split(self.convert_phrase_to_word_list(l_results[0][1:]))
			result_rphrase = self.__phrase_mgr.get_rphrase(result)
			s_result_rcents = set(self.__phraseperms.get_cluster(result_rphrase))
			map_rphrase_to_s_rcents[result_rphrase] = s_result_rcents

		t_vars = self.make_var_list([phrase] + [result])
		ll_rphrases_close = [[]]; l_t_vars = [t_vars]
		num_phrase_combos = 1; curr_combo = 0
		base_event_hits = []
		while curr_combo < len(ll_rphrases_close):
			for src_rcent in s_src_rcents:
				rsg = self.__d_lrules.get(src_rcent, None)
				if rsg == None:
					rsg = cl_rule_src_grp(self, src_rcent, type(self).ts)
					self.__d_lrules[src_rcent] = rsg
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
											l_t_vars[curr_combo], base_event_hits, type(self).ts)
						if l_rphrases_close == []: base_event_hits = event_hits
						if bfurther:
							all_rphrases = [rphrase] + l_rphrases_close
							s_rphrases_close_new \
									= mpdbs.get_bdb_story().get_matching_irecs(	idb, all_rphrases[-1],all_rphrases[:-1])
							# add one of the close and check against the list to see if its there already
							for rphrase_close_new in s_rphrases_close_new:
								l_rphrases_close_new = sorted(l_rphrases_close + [rphrase_close_new])
								if l_rphrases_close_new in ll_rphrases_close:
									continue
								ll_rphrases_close.append(l_rphrases_close_new)
								phrases_list = [phrase] + [self.__phraseperms.get_phrase(r) for r in l_rphrases_close_new] + [result]
								l_t_vars.append(self.make_var_list(phrases_list))
			# end loop over src_rcent
			curr_combo += 1

		if type(self).ts > self.__last_print:
			print('---> start rules learned at timestamp:', type(self).ts)
			for src_rcent, rsg in self.__d_lrules.iteritems():
				if rsg.get_num_hits() < 10: continue
				rsg.print_rsg()
			self.__last_print += c_print_every
			print('---> end rules learned at timestamp:', type(self).ts)
		pass

	def get_grp_vars(self, l_rphrases):
		phrases_list = [self.__phraseperms.get_phrase(r) for r in l_rphrases]
		return self.make_var_list(phrases_list)

	def learn_rule_old(self, mpdbs, stmt, l_results, phase_data, idb):
		type(self).ts += 1
		phrase = self.full_split(stmt)
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		s_rcents = set(self.__phraseperms.get_cluster(rphrase))
		if l_results == []:
			result = []
			result_rphrase = -1
			s_result_rcents = set([-1])
		else:
			result = self.full_split(self.convert_phrase_to_word_list(l_results[0][1:]))
			result_rphrase = self.__phrase_mgr.get_rphrase(result)
			s_result_rcents = set(self.__phraseperms.get_cluster(result_rphrase))
		t_vars = self.make_var_list([phrase, result])
		ll_rphrases_close = [[]]; l_t_vars = [t_vars]; ll_rcents_close = [[]]
		s_rphrases_close = mpdbs.get_bdb_story().get_matching_irecs(idb, rphrase)
		# s_r_phrase_pairs = mpdbs.get_bdb_story().get_matching_irec_pairs(idb, rphrase)
		for rphrase_close in s_rphrases_close:
			l_rcent_close = self.__phraseperms.get_cluster(rphrase_close)
			for rcent_close in l_rcent_close:
				ll_rphrases_close.append([rphrase_close]); ll_rcents_close.append([rcent_close])
				phrase_close = self.__phraseperms.get_phrase(rphrase_close)
				l_t_vars.append(self.make_var_list([phrase, phrase_close, result]))
			del l_rcent_close
		del s_rphrases_close

		# The code here is a kind of cache about which 2nd, 3rd etc close we have calculated already
		# since multiple rsg's might need to make the calculation and we don't want unnecessary repeat
		d_close_cache = dict()
		for l_rphrases_close in ll_rphrases_close:
			d_close_cache[l_rphrases_close] = []

		for src_rcent in s_rcents:
				# trec = (src_rcent, result_rcent, t_vars)
			rsg = self.__d_lrules.get(src_rcent, None)
			if rsg == None:
				rsg = cl_rule_src_grp(self, src_rcent, type(self).ts)
				self.__d_lrules[src_rcent] = rsg
			for result_rcent in s_result_rcents:
				# ll_close_further is a list of lists of rcents we want to do more search on
				# we actually search on the last in each list but keep the rest o fthe list for passing in again
				ll_close_further_rphrase, ll_close_further_rcents = rsg.add_event(	rphrase, result_rphrase, result_rcent,
													ll_rphrases_close, ll_rcents_close,
													l_t_vars, type(self).ts)
				ll_rphrases_close2 = []; l_t_vars2 = []; ll_rcents_close2 = []
				for l_close_rphrase, l_close_rcent in zip(ll_close_further_rphrase, ll_close_further_rcents):
					l_rcent_closer =  d_close_cache.get(l_close_rphrase, [])
					if l_rcent_closer == []:
						s_rphrases_close = mpdbs.get_bdb_story().get_matching_irecs(idb, l_close_rphrase[-1],
																					l_close_rphrase[:-1] + [rphrase])
						for rphrase_close in s_rphrases_close:
							l_rcent_close = self.__phraseperms.get_cluster(rphrase_close)
							for rcent_close in l_rcent_close:
								ll_rphrases_close2.append([rphrase_close]); ll_rcents_close2.append([rcent_close])
								phrase_close = self.__phraseperms.get_phrase(rphrase_close)
								l_t_vars2.append(self.make_var_list([phrase, phrase_close, result]))

		if type(self).ts > self.__last_print:
			for src_rcent, rsg in self.__d_lrules.iteritems():
				if rsg.get_num_hits() < 10: continue
				rsg.print_rsg()
			self.__last_print += c_print_every
		pass
