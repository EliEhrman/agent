"""
Mission statement for module.
gps stands for General Problemm Solver; an 80s concept for generic AI using a basic tree-searching creation
of sub-goals. Prolog is built on this. Solve the main goal by instantiating variables then
add the components of the rule as sub-goals

In our case, the rules are learned so this is a General GPS. Moreover we can learn rules that effectively
short-cut across the branches of the tree
"""
from __future__ import print_function
import random
import timeit
import numpy as np

total_time = 0.
num_calls = 0
b_in_time = False

def gpsai_time_decor(fn):
	def wr(*args, **kwargs):
		global total_time, num_calls, b_in_time
		s = timeit.default_timer()
		b_top = False
		if not b_in_time:
			b_top = True
			b_in_time = True
		r = fn(*args, **kwargs)
		if b_top:
			total_time += timeit.default_timer() - s
			b_in_time = False
		num_calls += 1
		return r

	return wr


class cl_gpsai_mgr(object):
	def __init__(self):
		pass

	def set_mgrs(self, fixed_rule_mgr, mpdb_mgr, gpsai_mgr, bitvec_mgr, rule_mod):
		self.__mpdb_mgr = mpdb_mgr
		self.__fixed_rule_mgr = fixed_rule_mgr
		self.__gpsai_mgr = gpsai_mgr
		self.__bitvec_mgr = bitvec_mgr
		self.__rule_mod = rule_mod

	def set_calc_level(self, min_calc_level, max_calc_level):
		self.__min_calc_level = min_calc_level
		self.__max_calc_level = max_calc_level

	def set_player_goal(self, player_name, goal_stmt, db_name, phase_data, var_obj_parent,
						calc_level, calc_level_limit):
		# if var_obj_parent == None:
		# 	calc_level = 0
		# else:
		# 	calc_level = var_obj_parent.get_calc_level()
		if calc_level >= calc_level_limit: return []
		# if rec_left <= 0: return []

		goal_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(goal_stmt)
		if goal_phrase != []:
			l_action_stmts = self.__mpdb_mgr.run_rule(	goal_phrase, phase_data,
														player_name, ['get_player_action'])[1]
			if l_action_stmts != []:
				assert len(l_action_stmts) == 1, 'Error. get_player_action should not produce more than one result.'
				var_phrase = self.__rule_mod.nt_match_phrases(istage=0, b_matched=True, phrase=l_action_stmts[0])
				return [self.__rule_mod.cl_var_match_opts(None, [var_phrase], [[0]],
														  var_obj_parent, calc_level+1)]
			# The rest should be deleted
		# for action_stmt in l_action_stmts:
		# 	if self.__rule_mod.does_stmt_match_goal(goal_stmt, action_stmt, self.__bitvec_mgr):
		# 		var_phrase = self.__rule_mod.nt_match_phrases(istage=0, b_matched=True, phrase=action_stmt)
		# 		return [self.__rule_mod.cl_var_match_opts(None, [var_phrase], [[0]])]
		# 		# return [1.0], [[self.__rule_mod.convert_phrase_to_word_list([goal_stmt])[0]]], [[]]

		# l_action_rules, l_action_rule_names = \
		# 		self.__bitvec_mgr.get_rules_by_cat(['get_player_action'])
		# for gg in l_action_rules:
		# 	bmatch, l_var_tbl = gg.does_stmt_match_result(goal_stmt)

		l_options, l_irule_opts = [], []
		l_rules, l_rule_names = self.__bitvec_mgr.get_rules_by_cat(['state_from_event', 'event_from_decide', 'br_state_from_event'])
		for irule, gg in enumerate(l_rules):
			bmatch, l_var_tbl = gg.does_stmt_match_result(goal_stmt)
			if bmatch:
				l_options.append(l_var_tbl)
				l_irule_opts.append(irule)

		l_var_opt_objs = []
		for opt, irule in zip(l_options, l_irule_opts):
			gg = l_rules[irule]
			var_opt_obj = gg.find_var_opts(opt, db_name, var_obj_parent, calc_level)
			if var_opt_obj == None: continue
			for iphrase, match_phrase_data in enumerate(var_opt_obj.get_l_match_phrases()):
				if not match_phrase_data.b_matched:
					l_var_opt_objs_child = self.set_player_goal(player_name,
																match_phrase_data.phrase, db_name,
																phase_data, var_opt_obj, var_opt_obj.get_calc_level(),
																calc_level_limit)
					# max_child_score = max(l_var_opt_objs_child, key=lambda x: x.get_best_score()).get_best_score()
					# var_opt_obj.set_match_phrase_score(iphrase, max_child_score)
					var_opt_obj.set_var_match_opts(iphrase, l_var_opt_objs_child)

			# print('Need to add up scores from the best of each ')
			l_var_opt_objs.append(var_opt_obj)

		return l_var_opt_objs

	def add_poss_stmt(	self, l_unmatched_match_stmts, player_name, db_name, phase_data, rule_stats,
						decision_on_new_phrase_fn):
		for stmt in l_unmatched_match_stmts:
			poss_db = self.__mpdb_mgr.get_poss_db()
			for poss in random.sample(poss_db, len(poss_db)) :
				poss_opt = self.__bitvec_mgr.combine_templates(stmt, poss)
				if poss_opt == []: continue
				l_poss_phrases = self.__mpdb_mgr.run_rule(	poss_opt, phase_data,
														player_name, ['foolme_fact_test'])
				if l_poss_phrases[1] != []:
					poss_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(l_poss_phrases[1][0])
					action_selected = decision_on_new_phrase_fn(player_name, phase_data, rule_stats, poss_phrase)
					if action_selected != []: return action_selected

		return []

	def get_unmatch_opts(self, l_var_opt_objs, player_name, db_name, l_unmatched_match_phrases):
		# l_unmatched_match_phrases_new = []
		l_opt_scores = [var_opt_obj.get_best_score() for var_opt_obj in l_var_opt_objs]
		l_var_opt_objs_sorted = \
			sorted(l_var_opt_objs, key=lambda x: x.get_best_score() * (1. - (random.random() / 3.)), reverse=True)
		for var_opt_obj in l_var_opt_objs_sorted:
			match_phrase_scores = var_opt_obj.get_l_match_phrase_scores()
			l_iphrase_sorted = [sc for sc, _ in
								sorted(	enumerate(match_phrase_scores),
										key=lambda pair: pair[1] * (1. - (random.random() / 30.)), reverse=True)]
			for iphrase in l_iphrase_sorted:
				match_phrase = var_opt_obj.get_match_phrase(iphrase)
				if match_phrase.b_matched or match_phrase.phrase in l_unmatched_match_phrases: continue
				l_unmatched_match_phrases.append(match_phrase.phrase)
				l_child_var_opts = var_opt_obj.get_l_var_match_opts(iphrase)
				if l_child_var_opts == []: continue
				self.get_unmatch_opts(l_child_var_opts, player_name, db_name, l_unmatched_match_phrases)

				# for match_phrase in var_opt_obj.get_l_match_phrases():
				# if not match_phrase.b_matched:
				# 	if match_phrase.phrase not in l_unmatched_match_phrases:
				# 		l_unmatched_match_phrases_new.append(match_phrase.phrase)
				#
				# for var_opt_obj in l_var_opt_objs_sorted:
				# 	for l_child_var_opt_pair in var_opt_obj.get_sorted_ll_opts():
				# 		if l_child_var_opt_pair[1] == []: continue
				# 		if l_child_var_opt_pair[0].phrase in l_unmatched_match_phrases: continue
				# 		if l_child_var_opt_pair[0].phrase in l_unmatched_match_phrases_new:
				# 			# The assumption is that if it in the list, someone else has already looked at the same var_opts. No point repeating.
				# 			l_unmatched_match_phrases.append(l_child_var_opt_pair[0].phrase)
				# 			l_unmatched_match_phrases_new.remove(l_child_var_opt_pair[0].phrase)
				# 		self.get_unmatch_opts(l_child_var_opt_pair[1], player_name, db_name, l_unmatched_match_phrases)
				#
				# l_unmatched_match_phrases += l_unmatched_match_phrases_new
				#
				# # extra_calc_levels = itry * 2
				# for l_combo in ll_combo:

	@gpsai_time_decor
	def select_action(	self, l_var_opt_objs, player_name, db_name, phase_data,
						calc_level_limit_src, l_phrases_tried, l_calc_level_tried):
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
				# Step 1. make sure that we don't have combo with one action and all the rest matched
				# Priority for that to return
				for iphrase in l_combo:
					match_phrase = var_opt_obj.get_l_match_phrases()[iphrase]
					l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
					if l_var_match_opt != []:
						child_match_phrase = l_var_match_opt[0].get_l_match_phrases()[0]
						if not match_phrase.b_matched and child_match_phrase.b_matched \
								and l_var_match_opt[0].get_parent_gg() == None:
							assert iphrase_action == -1, 'Rule error. There should only be one action phrase in a rule'
							iphrase_action = iphrase
					if iphrase_action != iphrase and not match_phrase.b_matched:
						l_iphrase_not_matched += [iphrase]
				if iphrase_action != -1 and l_iphrase_not_matched == []:
					return var_opt_obj.get_l_match_phrases()[iphrase_action].phrase, action_id_selected
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
					l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
					# go deeper if failed already
					if l_var_match_opt == []: # and itry > 0: #
						l_var_match_opt = self.set_player_goal(	player_name, match_phrase.phrase, db_name,
																phase_data, var_opt_obj,
																var_opt_obj.get_calc_level(),
																calc_level_limit)
						var_opt_obj.set_var_match_opts(iphrase, l_var_match_opt)
						# l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
					if l_var_match_opt == []: continue
					action_selected, action_id_selected = \
						self.select_action(	l_var_match_opt, player_name, db_name, phase_data,
											calc_level_limit, l_phrases_tried, l_calc_level_tried)
					if action_selected != []:
						return action_selected, action_id_selected
		# end itry loop
		return [], -1


