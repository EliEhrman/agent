from __future__ import print_function

import rules2

ltotup = lambda l: tuple([tuple(li) for li in l])

class cl_rule_event(object):
	def __init__(self, ts, rphrase, rphrase_result, l_ilrules):
		self.__ts = ts
		self.__rphrase = rphrase
		self.__rphrase_result = rphrase_result
		self.__l_ilrules = l_ilrules

	def ts(self):
		return self.__ts

	def rphrase(self):
		return self.__rphrase

	def rphrase_result(self):
		return self.__rphrase_result

	def l_ilrules(self):
		return self.__l_ilrules

class cl_lrule(object):
	def __init__(self, mgr, rsg, rpg, result_rcent, var_list, creation_ts):
		self.__mgr = mgr
		self.__rsg = rsg
		self.__rpg = rpg
		self.__result_rcent = result_rcent
		self.__var_list = var_list
		self.__creation_ts = creation_ts

	def is_match(self, result_rcent, var_list):
		return result_rcent == self.__result_rcent and var_list == self.__var_list

class cl_rule_phrase_grp(object):
	def __init__(self, mgr, rsg, l_rphrases_close, grp_vars, ts):
		self.__mgr = mgr
		self.__rsg = rsg
		self.__l_rphrases_close =  l_rphrases_close
		self.__grp_vars = grp_vars # vars that define the group excluding result vars
		self.__l_rules = [] #  [cl_lrule(mgr, self, -1, (), cl_rule_phrase_grp.ts)]
		self.__creation_ts = ts

	def is_match(self, l_rphrase_close, grp_vars):
		return l_rphrase_close == self.__l_rphrases_close and grp_vars == self.__grp_vars

	def add_event(self, result_rcent, var_list, ts):
		# if not any(lrule.is_match(result_rcent, var_list) for lrule in self.__l_rules):
		# 	self.__l_rules.append(cl_lrule(self.__mgr, self, result_rcent, var_list, cl_rule_phrase_grp.ts))

		# for rphrase_close, var_list in zip(l_rphrases_close, l_t_vars):
		# l_event_hits = []
		l_ilrules = [ilrule for ilrule, lrule in enumerate(self.__l_rules) if lrule.is_match(result_rcent, var_list)]
		if l_ilrules == []:
			l_ilrules = [len(self.__l_rules)]
			self.__l_rules.append(cl_lrule(self.__mgr, self.__rsg, self, result_rcent, var_list, ts))

		# l_event_hits.append(l_ilrules)
		return l_ilrules


class cl_rule_src_grp(object):

	def __init__(self, mgr, phrase_rcent, ts):
		self.__mgr = mgr
		self.__phrase_rcent = phrase_rcent
		self.__l_rpgs = []
		self.__l_rpg_var_lists = [] # indexed as l_rpgs
		self.__l_events = []
		self.__creation_ts = ts

	def add_event(self, rphrase, rphrase_result, result_rcent, ll_rphrases_close, l_t_vars, ts):
		l_event_hits = []
		for l_rphrase_close, t_vars in zip(ll_rphrases_close, l_t_vars):
			result_idx = len(l_rphrase_close) + 1
			t_vars_grp = filter(lambda l: l[2] != result_idx, t_vars)
			rpg = None; irpg = -1
			for irpg_test, rpg_test in enumerate(self.__l_rpgs):
				if rpg_test.is_match(l_rphrase_close, t_vars_grp):
					rpg = rpg_test; irpg = irpg_test
					break
			if rpg == None:
				rpg = cl_rule_phrase_grp(self.__mgr, self, l_rphrase_close, t_vars_grp, ts)
				irpg = len(self.__l_rpgs)
				self.__l_rpgs.append(rpg);
			l_event_hits.append([irpg, rpg.add_event(result_rcent, t_vars, ts)])
		self.__l_events.append(cl_rule_event(ts, rphrase, rphrase_result, l_event_hits))

class cl_lrule_mgr(object):
	ts = 0

	def __init__(self, phrase_mgr, phraseperms):
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms
		self.__d_lrules = dict()
		pass

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
		type(self).ts += 1
		phrase = self.full_split(stmt)
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		l_rcents = self.__phraseperms.get_cluster(rphrase)
		if l_results == []:
			result = []
			result_rphrase = -1
			l_result_rcents = [-1]
		else:
			result = self.full_split(self.convert_phrase_to_word_list(l_results[0][1:]))
			result_rphrase = self.__phrase_mgr.get_rphrase(result)
			l_result_rcents = self.__phraseperms.get_cluster(result_rphrase)
		t_vars = self.make_var_list([phrase, result])
		l_rphrases_close = [[]]; l_t_vars = [t_vars]
		s_rphrases_close = mpdbs.get_bdb_story().get_matching_irecs(idb, rphrase)
		for rphrase_close in s_rphrases_close:
			l_rphrases_close.append([rphrase_close])
			phrase_close = self.__phraseperms.get_phrase(rphrase_close)
			l_t_vars.append(self.make_var_list([phrase, phrase_close, result]))

		for src_rcent in l_rcents:
				# trec = (src_rcent, result_rcent, t_vars)
			rg = self.__d_lrules.get(src_rcent, None)
			if rg == None:
				rg = cl_rule_src_grp(self, src_rcent, type(self).ts)
				self.__d_lrules[src_rcent] = rg
			for result_rcent in l_result_rcents:
				rg.add_event(rphrase, result_rphrase, result_rcent, l_rphrases_close, l_t_vars, type(self).ts)

		pass
