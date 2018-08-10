"""
Mission statement for module.
gps stands for General Problemm Solver; an 80s concept for generic AI using a basic tree-searching creation
of sub-goals. Prolog is built on this. Solve the main goal by instantiating variables then
add the components of the rule as sub-goals

In our case, the rules are learned so this is a General GPS. Moreover we can learn rules that effectively
short-cut across the branches of the tree
"""
from __future__ import print_function
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

	def set_player_goal(self, player_name, goal_stmt, db_name, phase_data):
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

