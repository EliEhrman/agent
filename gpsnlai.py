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
		pass

	def set_constants(self, goal_init_level_limit, goal_max_level_limit, max_story_time_to_repeat):
		self.__goal_init_level_limit = goal_init_level_limit
		self.__goal_max_level_limit = goal_max_level_limit
		self.__max_story_time_to_repeat = max_story_time_to_repeat

	def set_mgrs(self, mpdbs_mgr, nlbitvec_mgr, rules3_mgr):
		self.__mpdbs_mgr = mpdbs_mgr
		self.__el_bitvec_mgr = nlbitvec_mgr
		self.__rule_mgr = rules3_mgr
		# self.__lrule_mgr = lrule_mgr

	def set_calc_level(self, min_calc_level, max_calc_level):
		self.__min_calc_level = min_calc_level
		self.__max_calc_level = max_calc_level

	def db_changed(self):
		self.__player_goal_arg_cache = dict()

	def make_decision_by_goal(self, player_name, phase_data, rule_stats):
		goal_stmt = self.__mpdbs_mgr.run_rule(['I', 'am', player_name], phase_data,
									   player_name, [], ['get_goal_phrase'])[1][0]

	def get_decision_by_goal(self, player_name, phase_data, rule_stats):
		l_var_opt_objs, action_selected = self.make_decision_by_goal(player_name, phase_data, rule_stats)
