"""
Mission statement for module.
gps stands for General Problemm Solver; an 80s concept for generic AI using a basic tree-searching creation
of sub-goals. Prolog is built on this. Solve the main goal by instantiating variables then
add the components of the rule as sub-goals

This module is a fork of the gpsai module. This version is designed for use with the nl components (nlbitvec, mpdbs,
rules3, rule_learn)

In our case, the rules are learned so this is a General GPS. Moreover we can learn rules that effectively
short-cut across the branches of the tree
"""
from __future__ import print_function
import random
import timeit
import collections
import numpy as np

from utils import profile_decor
from utils import conn_type
from utils import rec_def_type

# nt_vo_match_phrases = collections.namedtuple('nt_match_phrases', 'istage, b_matched, phrase')
nt_past_action = collections.namedtuple('nt_past_action', 'l_phrase, last_time')


class cl_gpsnlai_mgr(object):
	def __init__(self):
		self.__goal_init_level_limit = -1
		self.__goal_max_level_limit = -1
		self.__l_action_history = []
		self.__curr_story_id = -1
		self.__max_story_time_to_repeat = 1
		self.__player_goal_arg_cache = dict()
		self.__arg_cache_hits = 0
		self.__arg_cache_misses = 0
		self.__mpdbs_mgr = None
		self.__el_bitvec_mgr = None
		self.__rule_mgr = None
		self.__lrule_mgr = None
		self.__phrase_mgr = None
		self.__phraseperms = None
		pass

	def set_constants(self, goal_init_level_limit, goal_max_level_limit, max_story_time_to_repeat):
		self.__goal_init_level_limit = goal_init_level_limit
		self.__goal_max_level_limit = goal_max_level_limit
		self.__max_story_time_to_repeat = max_story_time_to_repeat

	def set_mgrs(self, mpdbs_mgr, nlbitvec_mgr, rules3_mgr, phrase_mgr, phraseperms, rule_mod):
		self.__mpdbs_mgr = mpdbs_mgr
		self.__el_bitvec_mgr = nlbitvec_mgr
		self.__rule_mgr = rules3_mgr
		# self.__lrule_mgr = lrule_mgr
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms
		self.__rule_mod = rule_mod

	def get_mpdbs_mgr(self):
		return self.__mpdbs_mgr

	def set_calc_level(self, min_calc_level, max_calc_level):
		self.__min_calc_level = min_calc_level
		self.__max_calc_level = max_calc_level

	def db_changed(self):
		self.__player_goal_arg_cache = dict()

	def make_decision_by_goal(self, player_name, phase_data, rule_stats):
		_, ll_done_els = self.__mpdbs_mgr.run_rule(['I', 'am', player_name], phase_data,
									   player_name, [], ['get_done_phrase'])
		if ll_done_els != [] and ll_done_els[0] == [player_name, 'is', 'done']:
			return [], 'done'
		ll_result_rels, ll_result_els = self.__mpdbs_mgr.run_rule(	['I', 'am', player_name], phase_data,
									   								player_name, [], ['get_goal_phrase'])
		goal_stmt = ll_result_els[0]

		db_name = player_name
		l_var_opt_objs = []; action_selected = []

		# goal_stmt = [[rec_def_type.obj, w] for w in goal_wlist]
		var_match_opt_cont = self.set_player_goal(	player_name, goal_stmt, db_name, phase_data,
													var_obj_parent=None, calc_level=0,
													calc_level_limit=self.__goal_init_level_limit)


		if var_match_opt_cont != []:
			l_var_opt_objs = var_match_opt_cont.get_var_match_opt_objs()
			# for var_opt_obj in l_var_opt_objs: var_opt_obj.calc_best_score()
			for goal_level_limit in range(self.__goal_init_level_limit, self.__goal_max_level_limit+1, 2):
				l_phrase_actions_tried, l_calc_level_tried = [], []
				self.set_calc_level(self.__goal_init_level_limit, goal_level_limit)
				action_selected, action_id_selected = \
					self.select_action(	l_var_opt_objs, player_name, db_name, phase_data,
										   self.__goal_init_level_limit, l_phrase_actions_tried, l_calc_level_tried)
				if action_selected != []:
					break

		return l_var_opt_objs, action_selected

	def add_phrase_to_get_decision(self, player_name, phase_data, rule_stats, new_phrase):
		inlphrase = self.__phrase_mgr.add_phrase(new_phrase)
		self.__mpdbs_mgr.ext_insert([player_name], inlphrase)
		# self.__mpdbs_mgr.add_phrase_text(player_name, new_phrase)
		self.__rule_mgr.clr_db_arg_cache()
		# self.__el_bitvec_mgr.clear_all_db_arg_caches()

		self.db_changed()
		_, action_selected = self.make_decision_by_goal(player_name, phase_data, rule_stats)
		if action_selected == []:
			self.__mpdbs_mgr.remove_phrase_text(player_name, new_phrase, phase_data)
			self.__el_bitvec_mgr.clear_all_db_arg_caches()
			self.db_changed()
		return action_selected

	def get_decision_by_goal(self, player_name, phase_data, rule_stats):
		selected_action_phrase = []
		l_var_opt_objs, action_selected = self.make_decision_by_goal(player_name, phase_data, rule_stats)

		if action_selected == []:
			l_unmatched_match_phrases = []
			self.get_unmatch_opts(l_var_opt_objs, player_name, player_name, l_unmatched_match_phrases)
			if l_unmatched_match_phrases != []:
				action_selected = \
					self.add_poss_stmt(	l_unmatched_match_phrases, player_name, player_name,
											phase_data, rule_stats) #, self.add_phrase_to_get_decision)


		# if action_selected != []:
		# 	selected_action_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(action_selected)

		return action_selected, 0 # action_id_selected

	def set_player_goal(self, player_name, goal_phrase, db_name, phase_data, var_obj_parent,
						calc_level, calc_level_limit):
		if calc_level >= calc_level_limit:
			return []
		idb = self.__mpdbs_mgr.get_idb_from_db_name(db_name)
		# b_pure_wlist = True; goal_wlist = []
		# for el in goal_phrase:
		# 	if el[0] != rec_def_type.obj:
		# 		b_pure_wlist = False
		# 		break
		# 	goal_wlist.append(el[1])

		if goal_phrase != []:
			self.__phrase_mgr.add_phrase(goal_phrase)
			l_action_stmts = self.__mpdbs_mgr.run_rule(	goal_phrase, phase_data,
														player_name, ['get_player_action'])[1]
			if l_action_stmts != []:
				assert len(l_action_stmts) == 1, 'Error. get_player_action should not produce more than one result.'
				var_phrase = self.__rule_mod.nt_match_phrases(istage=0, b_matched=True, phrase=l_action_stmts[0], b_result=False)
				# l_var_opt_objs = [cl_vo_match(None, [var_phrase], [[0]], var_obj_parent, calc_level+1)]
				l_var_opt_objs = [self.__rule_mod.cl_var_match_opts(-1, [var_phrase], [[0]],
																	var_obj_parent, calc_level + 1, False, [])]
				return self.__rule_mod.cl_var_match_opt_cont(l_var_opt_objs, calc_level, var_obj_parent)

		l_var_opt_objs = \
				self.__rule_mgr.find_var_opts_for_rules(goal_phrase, ['state_from_event', 'event_from_decide'], [], idb,
														var_obj_parent, calc_level)

		for var_opt_obj in l_var_opt_objs:
			for iphrase, match_phrase_data in enumerate(var_opt_obj.get_l_match_phrases()):
				# if iphrase != dbg_sel_iphrase: continue
				# if var_opt_obj.get_b_rule_has_result() and iphrase == len(var_opt_obj.get_l_match_phrases()) - 1: continue
				if not match_phrase_data.b_matched and not match_phrase_data.b_result:
					var_match_opt_cont_child = \
						self.set_player_goal(	player_name,
												match_phrase_data.phrase, db_name,
												phase_data, var_opt_obj, var_opt_obj.get_calc_level(),
												calc_level_limit)
					# max_child_score = max(l_var_opt_objs_child, key=lambda x: x.get_best_score()).get_best_score()
					# var_opt_obj.set_match_phrase_score(iphrase, max_child_score)
					var_opt_obj.set_var_match_opts(iphrase, var_match_opt_cont_child)

		return self.__rule_mod.cl_var_match_opt_cont(l_var_opt_objs, calc_level, var_obj_parent) if l_var_opt_objs != [] else []

	def add_poss_stmt(	self, l_unmatched_match_stmts, player_name, db_name, phase_data, rule_stats):
						# decision_on_new_phrase_fn):
		for stmt in l_unmatched_match_stmts:
			poss_db = self.__mpdbs_mgr.get_poss_db()
			for poss in random.sample(poss_db, len(poss_db)) :
				poss_opt = self.__el_bitvec_mgr.combine_templates(stmt, poss, rec_def_type.obj, rec_def_type.like)
				if poss_opt == []: continue
				self.__phrase_mgr.add_phrase(poss_opt)
				run_ret = self.__mpdbs_mgr.run_rule(	poss_opt, phase_data,
														player_name, ['foolme_fact_test'])
				if len(run_ret) < 2: continue
				l_poss_phrases = run_ret[1]
				if l_poss_phrases != []:
					# poss_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist()
					action_selected = self.add_phrase_to_get_decision(player_name, phase_data, rule_stats, l_poss_phrases[0])
					if action_selected != []: return action_selected

		return []

	def get_unmatch_opts(self, l_var_opt_objs, player_name, db_name, l_unmatched_match_phrases):
		# l_unmatched_match_phrases_new = []
		l_opt_scores = [var_opt_obj.get_best_score() for var_opt_obj in l_var_opt_objs]
		l_var_opt_objs_sorted = \
			sorted(l_var_opt_objs, key=lambda x: x.get_best_score() * (1. - (random.random() / 3.)), reverse=True)
		for var_opt_obj in l_var_opt_objs_sorted:
			for open_phrase in var_opt_obj.get_l_open_phrases():
				l_unmatched_match_phrases.append(open_phrase)
			match_phrase_scores = var_opt_obj.get_l_match_phrase_scores()
			l_iphrase_sorted = [sc for sc, _ in
								sorted(	enumerate(match_phrase_scores),
										key=lambda pair: pair[1] * (1. - (random.random() / 30.)), reverse=True)]
			for iphrase in l_iphrase_sorted:
				match_phrase = var_opt_obj.get_match_phrase(iphrase)
				if match_phrase.b_matched or match_phrase.b_result or match_phrase.phrase in l_unmatched_match_phrases: continue
				l_unmatched_match_phrases.append([[rec_def_type.obj, v] for v in match_phrase.phrase])
				l_child_var_opts = var_opt_obj.get_l_var_match_opts(iphrase)
				if l_child_var_opts == []: continue
				self.get_unmatch_opts(l_child_var_opts, player_name, db_name, l_unmatched_match_phrases)

	def select_action(	self, l_var_opt_objs, player_name, db_name, phase_data,
						calc_level_limit_src, l_phrases_tried, l_calc_level_tried):
		# global atime_tot, btime_tot, ctime_tot
		story_id, story_time, story_loop_stage, eid = phase_data
		action_selected, action_id_selected = [], -1
		l_opt_scores = [var_opt_obj.get_best_score() for var_opt_obj in l_var_opt_objs]
		unrealistic_num_tries = 200
		# calc_level_limit = calc_level_limit_src
		# for itry in xrange(unrealistic_num_tries):
		# calc_level_limit = calc_level_limit_src + (itry * 2)
		# if calc_level_limit > self.__max_calc_level: break
		calc_level_limit = self.__max_calc_level
		for var_opt_obj in sorted(l_var_opt_objs, key=lambda x: x.get_best_score() * (1. - (random.random()/3.)), reverse=True):
			# var_opt_obj = np.random.choice(l_var_opt_objs, 1, p=l_opt_scores)[0]
			ll_combo = var_opt_obj.get_sorted_l_combo()
			# extra_calc_levels = itry * 2
			for l_combo in ll_combo:
				iphrase_action, l_iphrase_not_matched = -1, []
				# atime = timeit.default_timer()

				# Step 1. make sure that we don't have combo with one action and all the rest matched
				# Priority for that to return
				for iphrase in l_combo:
					match_phrase = var_opt_obj.get_l_match_phrases()[iphrase]
					# remove where phrase is result
					if match_phrase.b_result: continue
					# l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
					var_match_opt_cont = var_opt_obj.get_var_match_opt_conts(iphrase)
					if var_match_opt_cont != []:
						l_var_match_opt = var_match_opt_cont.get_var_match_opt_objs()
						# if l_var_match_opt != []:
						child_match_phrase = l_var_match_opt[0].get_l_match_phrases()[0]
						if not match_phrase.b_matched and child_match_phrase.b_matched \
								and l_var_match_opt[0].get_irule() == -1:
							assert iphrase_action == -1, 'Rule error. There should only be one action phrase in a rule'
							iphrase_action = iphrase
					if iphrase_action != iphrase and not match_phrase.b_matched:
						l_iphrase_not_matched += [iphrase]
				if iphrase_action != -1 and l_iphrase_not_matched == []:
					selected_action_phrase = var_opt_obj.get_l_match_phrases()[iphrase_action].phrase
					# selected_action_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(action_selected)
						# reject action if already in history with random
					for past_action in self.__l_action_history:
						if selected_action_phrase == past_action.l_phrase:
							time_passed = story_time - past_action.last_time
							if time_passed > self.__max_story_time_to_repeat:
								break
							if random.random() > (story_time - time_passed) / float(
									self.__max_story_time_to_repeat):
								selected_action_phrase = []
								break

					if selected_action_phrase != []:
						self.__l_action_history.append(
								nt_past_action(l_phrase=selected_action_phrase, last_time=story_time))
						return selected_action_phrase, action_id_selected

				# Step 2. Dig deeper
				for iphrase in random.sample(l_iphrase_not_matched, len(l_iphrase_not_matched)):
					# pick a phrase that isnt a b_matched, if its an action return it otherwise dig deeper
					match_phrase = var_opt_obj.get_l_match_phrases()[iphrase]
					if match_phrase.phrase in l_phrases_tried:
						itried = l_phrases_tried.index(match_phrase.phrase)
						level_tried = l_calc_level_tried[itried]
						if level_tried <= var_opt_obj.get_calc_level():
							continue
						else:
							l_calc_level_tried[itried] = var_opt_obj.get_calc_level()
					else:
						l_calc_level_tried.append(var_opt_obj.get_calc_level())
						l_phrases_tried.append(match_phrase.phrase)
					# if match_phrase.b_matched or iphrase == iphrase_action: continue
					# l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
					l_var_match_opt = []
					var_match_opt_cont = var_opt_obj.get_var_match_opt_conts(iphrase)
					# if var_match_opt_cont != []:
					# 	l_var_match_opt = var_match_opt_cont.get_var_match_opt_objs()
					# atime = timeit.default_timer()
					# go deeper if failed already
					if var_match_opt_cont == []: # and itry > 0: #
						var_match_opt_cont = self.set_player_goal(	player_name, match_phrase.phrase, db_name,
																phase_data, var_opt_obj,
																var_opt_obj.get_calc_level(),
																calc_level_limit)
						var_opt_obj.set_var_match_opts(iphrase, var_match_opt_cont)
						# l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
					if var_match_opt_cont != []:
						l_var_match_opt = var_match_opt_cont.get_var_match_opt_objs()
					# btime = timeit.default_timer()
					# atime_tot += btime - atime
					if l_var_match_opt == []: continue
					action_selected, action_id_selected = \
						self.select_action(	l_var_match_opt, player_name, db_name, phase_data,
											calc_level_limit, l_phrases_tried, l_calc_level_tried)
					if action_selected != []:
						return action_selected, action_id_selected
		# end itry loop
		return [], -1
