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

nt_vo_match_phrases = collections.namedtuple('nt_match_phrases', 'istage, b_matched, phrase')

class cl_vo_match_cont(object):
	def __init__(self, l_var_match_opt_objs, calc_level, first_parent_obj):
		self.__l_var_match_opt_objs = l_var_match_opt_objs
		self.__calc_level = calc_level
		self.__l_parent_objs = [first_parent_obj]
		for var_opt_obj in l_var_match_opt_objs:
			var_opt_obj.set_cont(self)

	def get_calc_level(self):
		return self.__calc_level

	def add_parent_obj(self, parent_obj):
		self.__l_parent_objs.append(parent_obj)

	def get_var_match_opt_objs(self):
		return self.__l_var_match_opt_objs

	def set_score_invalid(self):
		for parent_var_obj in self.__l_parent_objs:
			if parent_var_obj != None:
				parent_var_obj.set_score_invalid()

	def loop_check(self, test_cont):
		for parent_var_obj in self.__l_parent_objs:
			if parent_var_obj == None: continue
			elif parent_var_obj.loop_check(test_cont):
				return True
			else: continue
		return False

class cl_vo_match(object):
	num_apply_cache_calls = 0
	max_obj_id = 0

	def __init__(self, parent_gg, l_match_phrases, ll_match_iphrase_combos, parent_obj, calc_level):
		self.__parent_gg = parent_gg
		self.__l_match_phrases = l_match_phrases
		self.__ll_match_iphrase_combos = ll_match_iphrase_combos
		self.__l_match_phrase_scores =  [0. for _ in l_match_phrases] # l_match_phrase_scores
		self.__l_combo_scores =  [0. for _ in ll_match_iphrase_combos]
		# self.__ll_var_match_opts = [[] for _ in l_match_phrases]  # for each match_phrase an array of cl_var_match_opts
		self.__l_var_match_opt_conts = [[] for _ in l_match_phrases]  # for each match_phrase an cl_var_match_opt_cont # need a list of var_match_objs for each iphrase, one for each matching rule
		self.__best_score = 0.
		self.__b_score_valid = False
		# self.__parent_obj = parent_obj
		self.__calc_level = calc_level
		self.__cont = []
		self.__obj_id = cl_vo_match.max_obj_id
		cl_vo_match.max_obj_id += 1

	def get_calc_level(self):
		return self.__calc_level

	def get_parent_obj(self):
		return self.__parent_obj


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

	def set_mgrs(self, mpdbs_mgr, nlbitvec_mgr, rules3_mgr, phrase_mgr, phraseperms):
		self.__mpdbs_mgr = mpdbs_mgr
		self.__el_bitvec_mgr = nlbitvec_mgr
		self.__rule_mgr = rules3_mgr
		# self.__lrule_mgr = lrule_mgr
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms

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
		l_var_opt_objs = []

		# goal_stmt = [[rec_def_type.obj, w] for w in goal_wlist]
		var_match_opt_cont = self.set_player_goal(	player_name, goal_stmt, db_name, phase_data,
													var_obj_parent=None, calc_level=0,
													calc_level_limit=self.__goal_init_level_limit)


	def get_decision_by_goal(self, player_name, phase_data, rule_stats):
		# l_var_opt_objs, action_selected = \
		self.make_decision_by_goal(player_name, phase_data, rule_stats)

	def set_player_goal(self, player_name, goal_phrase, db_name, phase_data, var_obj_parent,
						calc_level, calc_level_limit):
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
				var_phrase = nt_vo_match_phrases(istage=0, b_matched=True, phrase=l_action_stmts[0])
				l_var_opt_objs = [cl_vo_match(None, [var_phrase], [[0]], var_obj_parent, calc_level+1)]
				return cl_vo_match_cont(l_var_opt_objs, calc_level, var_obj_parent)

		l_var_opt_objs = self.__rule_mgr.find_rules_matching_result(goal_phrase, ['state_from_event', 'event_from_decide'], [], idb,
																	var_obj_parent, calc_level)
		for var_opt_obj in l_var_opt_objs:
			for iphrase, match_phrase_data in enumerate(var_opt_obj.get_l_match_phrases()):
				# if iphrase != dbg_sel_iphrase: continue
				if var_opt_obj.get_b_rule_has_result() and iphrase == len(var_opt_obj.get_l_match_phrases()) - 1: continue
				if not match_phrase_data.b_matched:
					var_match_opt_cont_child = \
						self.set_player_goal(	player_name,
												match_phrase_data.phrase, db_name,
												phase_data, var_opt_obj, var_opt_obj.get_calc_level(),
												calc_level_limit)
					# max_child_score = max(l_var_opt_objs_child, key=lambda x: x.get_best_score()).get_best_score()
					# var_opt_obj.set_match_phrase_score(iphrase, max_child_score)
					var_opt_obj.set_var_match_opts(iphrase, var_match_opt_cont_child)
		return l_var_opt_objs

