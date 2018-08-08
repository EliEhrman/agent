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

	def set_player_goal(self, player_name, goal_stmt, db_name):
		l_options, l_irule_opts = [], []
		l_rules, l_rule_names = self.__bitvec_mgr.get_rules_by_cat(['state_from_event', 'event_from_decide'])
		for irule, gg in enumerate(l_rules):
			bmatch, l_var_tbl = gg.does_stmt_match_result(goal_stmt)
			if bmatch:
				l_options.append(l_var_tbl)
				l_irule_opts.append(irule)

		for opt, irule in zip(l_options, l_irule_opts):
			gg = l_rules[irule]
			l_matches, l_b_phrases_matched = gg.find_var_opts(opt, db_name)
			for match, b_phrase_matched in zip(l_matches, l_b_phrases_matched):
				if not b_phrase_matched: self.set_player_goal(player_name, match, db_name)
		pass

