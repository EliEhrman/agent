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
import collections
import numpy as np

nt_past_action = collections.namedtuple('nt_past_action', 'l_phrase, last_time')

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

num_c_calls = 0
atime_tot, btime_tot, ctime_tot = 0,0,0

class cl_gpsai_mgr(object):
	def __init__(self):
		self.__goal_init_level_limit = -1
		self.__goal_max_level_limit = -1
		self.__l_action_history = []
		self.__curr_story_id = -1
		self.__max_story_time_to_repeat = 1
		self.__player_goal_arg_cache = dict()
		self.__arg_cache_hits = 0
		self.__arg_cache_misses = 0
		pass

	def set_constants(self, goal_init_level_limit, goal_max_level_limit, max_story_time_to_repeat):
		self.__goal_init_level_limit = goal_init_level_limit
		self.__goal_max_level_limit = goal_max_level_limit
		self.__max_story_time_to_repeat = max_story_time_to_repeat

	def set_mgrs(self, fixed_rule_mgr, mpdb_mgr, gpsai_mgr, bitvec_mgr, rule_mod):
		self.__mpdb_mgr = mpdb_mgr
		self.__fixed_rule_mgr = fixed_rule_mgr
		self.__gpsai_mgr = gpsai_mgr
		self.__bitvec_mgr = bitvec_mgr
		self.__rule_mod = rule_mod

	def set_calc_level(self, min_calc_level, max_calc_level):
		self.__min_calc_level = min_calc_level
		self.__max_calc_level = max_calc_level

	def db_changed(self):
		self.__player_goal_arg_cache = dict()

	set_player_goal_num_calls = 0

	@gpsai_time_decor
	def set_player_goal(self, player_name, goal_stmt, db_name, phase_data, var_obj_parent,
						calc_level, calc_level_limit):
		global atime_tot, btime_tot, ctime_tot, num_c_calls
		cl_gpsai_mgr.set_player_goal_num_calls += 1
		# if var_obj_parent == None:
		# 	calc_level = 0
		# else:
		# 	calc_level = var_obj_parent.get_calc_level()
		if calc_level >= calc_level_limit: return []
		# if rec_left <= 0: return []

		cache_key = (tuple(tuple(x) for x in goal_stmt), player_name, db_name)
		cache_var_opt_obj_cont = self.__player_goal_arg_cache.get(cache_key, [])
		if cache_var_opt_obj_cont == [] or cache_var_opt_obj_cont.get_calc_level() > calc_level:
			self.__arg_cache_misses += 1
		else:
			self.__arg_cache_hits += 1
			# return []
			# if cache_calc_level >= calc_level:
			c1time = timeit.default_timer()
			# cret = var_obj_parent.apply_cached_var_match_objs(l_cache_var_opt_objs, calc_level, calc_level_limit)
			# if not var_obj_parent.loop_check(cache_var_opt_obj_cont):
			cache_var_opt_obj_cont.add_parent_obj(var_obj_parent)
			# 	ret = cache_var_opt_obj_cont
			# else:
			# 	ret = []
			c2time = timeit.default_timer()
			ctime_tot += c2time - c1time
			num_c_calls += 1
			return cache_var_opt_obj_cont


		# self.__player_goal_arg_cache[cache_key] = [calc_level, []]

		goal_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(goal_stmt)
		if goal_phrase != []:
			l_action_stmts = self.__mpdb_mgr.run_rule(	goal_phrase, phase_data,
														player_name, ['get_player_action'])[1]
			if l_action_stmts != []:
				assert len(l_action_stmts) == 1, 'Error. get_player_action should not produce more than one result.'
				var_phrase = self.__rule_mod.nt_match_phrases(istage=0, b_matched=True, phrase=l_action_stmts[0])
				l_var_opt_objs = [self.__rule_mod.cl_var_match_opts(None, [var_phrase], [[0]],
																	var_obj_parent, calc_level+1)]
				# self.__player_goal_arg_cache[cache_key] = [calc_level, l_var_opt_objs]
				self.__player_goal_arg_cache[cache_key] = \
					self.__rule_mod.cl_var_match_opt_cont(l_var_opt_objs, calc_level, var_obj_parent) \
						if l_var_opt_objs != [] else []
				return self.__player_goal_arg_cache[cache_key]
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
		atime = timeit.default_timer()

		l_options, l_irule_opts = [], []
		l_rules, l_rule_names = self.__bitvec_mgr.get_rules_by_cat(['state_from_event', 'event_from_decide', 'br_state_from_event'])
		for irule, gg in enumerate(l_rules):
			bmatch, l_var_tbl = gg.does_stmt_match_result(goal_stmt)
			if bmatch:
				l_options.append(l_var_tbl)
				l_irule_opts.append(irule)

		btime = timeit.default_timer()
		atime_tot += btime - atime

		l_var_opt_objs = []
		# dbg_sel_irule = -1ctime
		for iirule, (opt, irule) in enumerate(zip(l_options, l_irule_opts)):
			# if iirule != dbg_sel_irule: continue
			gg = l_rules[irule]
			b1time = timeit.default_timer()
			var_opt_obj = gg.find_var_opts(opt, db_name, var_obj_parent, calc_level)
			b2time = timeit.default_timer()
			btime_tot += b2time - b1time
			if var_opt_obj == None: continue
			# dbg_sel_iphrase = -1
			for iphrase, match_phrase_data in enumerate(var_opt_obj.get_l_match_phrases()):
				# if iphrase != dbg_sel_iphrase: continue
				if not match_phrase_data.b_matched:
					var_match_opt_cont_child = \
						self.set_player_goal(	player_name,
												match_phrase_data.phrase, db_name,
												phase_data, var_opt_obj, var_opt_obj.get_calc_level(),
												calc_level_limit)
					# max_child_score = max(l_var_opt_objs_child, key=lambda x: x.get_best_score()).get_best_score()
					# var_opt_obj.set_match_phrase_score(iphrase, max_child_score)
					var_opt_obj.set_var_match_opts(iphrase, var_match_opt_cont_child)

			# print('Need to add up scores from the best of each ')
			l_var_opt_objs.append(var_opt_obj)

		# ctime_tot += timeit.default_timer()- ctime

		# self.__player_goal_arg_cache[cache_key] = [calc_level, l_var_opt_objs]
		self.__player_goal_arg_cache[cache_key] = \
			self.__rule_mod.cl_var_match_opt_cont(l_var_opt_objs, calc_level, var_obj_parent) \
				if l_var_opt_objs != [] else []
		return self.__player_goal_arg_cache[cache_key]

	def add_poss_stmt(	self, l_unmatched_match_stmts, player_name, db_name, phase_data, rule_stats):
						# decision_on_new_phrase_fn):
		for stmt in l_unmatched_match_stmts:
			poss_db = self.__mpdb_mgr.get_poss_db()
			for poss in random.sample(poss_db, len(poss_db)) :
				poss_opt = self.__bitvec_mgr.combine_templates(stmt, poss)
				if poss_opt == []: continue
				l_poss_phrases = self.__mpdb_mgr.run_rule(	poss_opt, phase_data,
														player_name, ['foolme_fact_test'])
				if l_poss_phrases[1] != []:
					poss_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(l_poss_phrases[1][0])
					action_selected = self.add_phrase_to_get_decision(player_name, phase_data, rule_stats, poss_phrase)
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

	# @gpsai_time_decor
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
					# l_var_match_opt = var_opt_obj.get_ll_var_match_opts()[iphrase]
					var_match_opt_cont = var_opt_obj.get_var_match_opt_conts(iphrase)
					if var_match_opt_cont != []:
						l_var_match_opt = var_match_opt_cont.get_var_match_opt_objs()
						# if l_var_match_opt != []:
						child_match_phrase = l_var_match_opt[0].get_l_match_phrases()[0]
						if not match_phrase.b_matched and child_match_phrase.b_matched \
								and l_var_match_opt[0].get_parent_gg() == None:
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


	# @gpsai_time_decor
	def make_decision_by_goal(self, player_name, phase_data, rule_stats):
		l_compul_stmt = self.__mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
									   player_name, ['compul_goal_actv'])[1]
		for compul_stmt in l_compul_stmt:
			l_poss_action = self.__mpdb_mgr.run_rule(self.__rule_mod.convert_single_bound_phrase_to_wlist(compul_stmt), phase_data,
									   player_name, ['event_from_decide'])
			if l_poss_action[1] != []:
				return [], compul_stmt

		done_stmt = self.__mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
									   player_name, [], ['get_done_phrase'])
		if done_stmt != ([], []) and done_stmt[1][0][1][1] == 'is done':
			return [], 'done'

		goal_stmt = self.__mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
									   player_name, [], ['get_goal_phrase'])[1][0]
		db_name = player_name
		l_var_opt_objs = []
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
		self.__mpdb_mgr.add_phrase_text(player_name, new_phrase, phase_data)
		self.__bitvec_mgr.clear_all_db_arg_caches()

		self.db_changed()
		_, action_selected = self.make_decision_by_goal(player_name, phase_data, rule_stats)
		if action_selected == []:
			self.__mpdb_mgr.remove_phrase_text(player_name, new_phrase, phase_data)
			self.__bitvec_mgr.clear_all_db_arg_caches()
			self.db_changed()
		return action_selected


	def get_decision_by_goal(self, player_name, phase_data, rule_stats):
		# global atime_tot, btime_tot, ctime_tot
		story_id, story_time, story_loop_stage, eid = phase_data
		if story_id != self.__curr_story_id:
			self.__curr_story_id = story_id
			self.__l_action_history = []

		atime = timeit.default_timer()

		selected_action_phrase = []
		l_var_opt_objs, action_selected = self.make_decision_by_goal(player_name, phase_data, rule_stats)

		if l_var_opt_objs == [] and action_selected == 'done':
			return [], -1

		# btime = timeit.default_timer()
		# atime_tot += btime - atime

		if action_selected == []:
			l_unmatched_match_phrases = []
			self.get_unmatch_opts(l_var_opt_objs, player_name, player_name, l_unmatched_match_phrases)
			if l_unmatched_match_phrases != []:
				action_selected = \
					self.add_poss_stmt(	l_unmatched_match_phrases, player_name, player_name,
											phase_data, rule_stats) #, self.add_phrase_to_get_decision)

		# ctime = timeit.default_timer()
		# btime_tot += ctime - btime

		if action_selected != []:
			selected_action_phrase = self.__rule_mod.convert_single_bound_phrase_to_wlist(action_selected)
		# 	# reject action if already in history with random
		# 	for past_action in self.__l_action_history:
		# 		if selected_action_phrase == past_action.l_phrase:
		# 			time_passed = story_time - past_action.last_time
		# 			if time_passed > self.__max_story_time_to_repeat:
		# 				break
		# 			if random.random() < (story_time - time_passed) / float(self.__max_story_time_to_repeat):
		# 				selected_action_phrase = []
		# 				break
		#
		# if selected_action_phrase != []:
		# 	self.__l_action_history.append(nt_past_action(l_phrase=selected_action_phrase, last_time=story_time))

		# ctime_tot += timeit.default_timer()- ctime

		return selected_action_phrase, 0 # action_id_selected

