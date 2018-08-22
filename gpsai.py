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
import numpy as np

class cl_gpsai_mgr(object):
	def __init__(self):
		pass

	def set_mgrs(self, fixed_rule_mgr, mpdb_mgr, gpsai_mgr, bitvec_mgr, rule_mod):
		self.__mpdb_mgr = mpdb_mgr
		self.__fixed_rule_mgr = fixed_rule_mgr
		self.__gpsai_mgr = gpsai_mgr
		self.__bitvec_mgr = bitvec_mgr
		self.__rule_mod = rule_mod

	def set_player_goal(self, player_name, goal_stmt, db_name, phase_data,  rec_left):
		if rec_left <= 0: return []

		goal_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(goal_stmt)
		if goal_phrase != []:
			l_action_stmts = self.__mpdb_mgr.run_rule(	goal_phrase, phase_data,
														player_name, ['get_player_action'])[1]
			if l_action_stmts != []:
				assert len(l_action_stmts) == 1, 'Error. get_player_action should not produce more than one result.'
				return [self.__rule_mod.cl_var_match_opts(None, [l_action_stmts[0]], [[0]])]
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
		l_rules, l_rule_names = self.__bitvec_mgr.get_rules_by_cat(['state_from_event', 'event_from_decide'])
		for irule, gg in enumerate(l_rules):
			bmatch, l_var_tbl = gg.does_stmt_match_result(goal_stmt)
			if bmatch:
				l_options.append(l_var_tbl)
				l_irule_opts.append(irule)

		l_var_opt_objs = []
		for opt, irule in zip(l_options, l_irule_opts):
			gg = l_rules[irule]
			var_opt_obj = gg.find_var_opts(opt, db_name)
			if var_opt_obj == None: continue
			for iphrase, match_phrase_data in enumerate(var_opt_obj.get_l_match_phrases()):
				if not match_phrase_data.b_matched:
					l_var_opt_objs_child = self.set_player_goal(player_name,
																match_phrase_data.phrase, db_name,
																phase_data, rec_left-1)
					# max_child_score = max(l_var_opt_objs_child, key=lambda x: x.get_best_score()).get_best_score()
					# var_opt_obj.set_match_phrase_score(iphrase, max_child_score)
					var_opt_obj.set_var_match_opts(iphrase, l_var_opt_objs_child)

			# print('Need to add up scores from the best of each ')
			l_var_opt_objs.append(var_opt_obj)

		return l_var_opt_objs

	def select_action(self, l_var_opt_objs):
		action_selected, action_id_selected = [], -1
		l_opt_scores = [var_opt_obj.get_best_score() for var_opt_obj in l_var_opt_objs]
		var_opt_obj = np.random.choice(l_var_opt_objs, 1, p=l_opt_scores)
		if var_opt_obj.get_parent_gg():
			print('TBD. Need to calc an action id')
			return var_opt_obj.get_l_match_phrases()[0].phrase, 0
		l_combo = var_opt_obj.select_combo()
		for iphrase in random.shuffle(l_combo):
			# pick a phrase that isnt a b_matched, if its an action return it otherwise dig deeper
			match_phrase,  = var_opt_obj.get_l_match_phrases()[iphrase]
			if match_phrase.b_matched: continue
			l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
			if l_var_match_opt == []: continue
			action_selected, action_id_selected = self.select_action(l_var_match_opt)
			if action_selected == []: continue
			break

		return action_selected, action_id_selected

	def set_player_goal_old(self, player_name, goal_stmt, db_name, phase_data):
		l_action_stmts = self.__mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
										player_name, ['get_player_action'])[1]
		for action_stmt in l_action_stmts:
			if self.__rule_mod.does_stmt_match_goal(goal_stmt, action_stmt, self.__bitvec_mgr):
				return [1.0], [[self.__rule_mod.convert_phrase_to_word_list([goal_stmt])[0]]], [[]]

		l_options, l_irule_opts = [], []
		l_rules, l_rule_names = self.__bitvec_mgr.get_rules_by_cat(['state_from_event', 'event_from_decide'])
		for irule, gg in enumerate(l_rules):
			bmatch, l_var_tbl = gg.does_stmt_match_result(goal_stmt)
			if bmatch:
				l_options.append(l_var_tbl)
				l_irule_opts.append(irule)

		ll_ret_match_paths, ll_ret_action_phrases, l_ret_full_match_score = [], [], []
		for opt, irule in zip(l_options, l_irule_opts):
			gg = l_rules[irule]
			l_l_matches, l_l_b_phrases_matched = gg.find_var_opts(opt, db_name)
			for l_matches, l_b_phrases_matched in zip(l_l_matches, l_l_b_phrases_matched):
				l_full_match_score, ll_action_phrases, ll_match_paths = [], [], []
				l_full_match_score_2, ll_action_phrases_2, ll_match_paths_2 = [], [], []
				for match, b_phrase_matched in zip(l_matches, l_b_phrases_matched):
					if not b_phrase_matched:
						l_new_full_match_score, ll_new_action_phrases, ll_new_match_paths = \
								self.set_player_goal(player_name, match, db_name, phase_data)
						for new_full_match_score, l_new_action_phrases, l_new_match_paths in \
								zip(l_new_full_match_score, ll_new_action_phrases, ll_new_match_paths):
							if l_full_match_score == []:
								if new_full_match_score > 0.:
									l_full_match_score_2.append(new_full_match_score)
									ll_action_phrases_2.append(l_new_action_phrases)
									ll_match_paths_2.append(l_new_match_paths)
								else:
									l_full_match_score_2.append(0.75)
							else:
								for iold, old_full_match_score in enumerate(l_full_match_score):
									l_old_action_phrases , l_old_mathc_paths = ll_action_phrases[iold], ll_match_paths[iold]
									if new_full_match_score > 0.:
										l_full_match_score_2.append(old_full_match_score * new_full_match_score)
										ll_action_phrases_2.append(l_old_action_phrases + l_new_action_phrases)
										ll_match_paths_2.append(l_old_mathc_paths + l_new_match_paths)
									else:
										l_full_match_score_2.append(old_full_match_score * 0.75)
						l_full_match_score[:], ll_action_phrases[:] = l_full_match_score_2, ll_action_phrases_2
						ll_match_paths[:] = ll_match_paths_2
						l_full_match_score_2[:], ll_action_phrases_2[:], ll_match_paths_2[:] = [], [], []
					else:
						if l_full_match_score == []:
							l_full_match_score.append(1.0)
							ll_match_paths.append(match)
						else:
							for full_match_score, match_paths in zip(l_full_match_score, ll_match_paths):
								match_paths.append(match)

				l_ret_full_match_score += l_full_match_score
				ll_ret_action_phrases += ll_action_phrases
				ll_ret_match_paths += ll_match_paths

		return l_full_match_score, ll_ret_action_phrases, ll_ret_match_paths

