import csv
import random
from enum import Enum
import timeit
import numpy as np

from utils import profile_decor

c_set_list = ['name', 'object', 'countrie']
c_rules_fn = 'adv/rules.txt'
c_ext_rules_fn = 'adv/ext_rules.txt'
c_dummy_init_fn = 'adv/dummy_init.txt'
c_dummy_events_fn = 'adv/dummy_events.txt'
c_phrase_freq_fnt = '~/tmp/adv_phrase_freq.txt'
c_b_nl = True # nat lang processing. Learn phrases. Initial load from glove. For now, switch bitvec.c_bitvec_size to 16 as well
# if c_b_nl:
# 	c_phrase_bitvec_dict_fnt = '~/tmp/glv_bin_dict.txt'
# else:
# 	c_phrase_bitvec_dict_fnt = '~/tmp/adv_bin_dict.txt'
c_phrase_bitvec_dict_fnt = '~/tmp/adv_bin_dict.txt'
c_nlbitvec_dict_input_fnt = '~/tmp/glv_bin_dict.txt'
# c_nlbitvec_dict_input_fnt = '~/tmp/nlbitvec_dict.txt'
c_nlbitvec_dict_output_fnt = '~/tmp/nlbitvec_dict.txt'
c_nlbitvec_clusters_fnt = '~/tmp/nlbitvec_clusters.txt'
c_bitvec_saved_phrases_fnt = '~/tmp/saved_phrases.txt' # '~/tmp/saved_phrases_small.txt' # '~/tmp/saved_phrases.txt'
c_rule_grp_fnt = 'adv/rule_groups.txt'
c_nlbitvec_rules_fnt = '~/tmp/nlbitvec_rules.txt'
c_num_agents_per_story = 5 # 50
c_num_countries_per_story = 5 # 80
c_num_objects_per_story = 5 # 50
c_num_tries_per_player = 30
c_goal_init_level_limit = 3
c_goal_max_level_limit = 7
c_max_story_time_to_repeat = 250000 # ignore the fact that an action has already be done after this much time and random when less
c_b_restart_from_glv = False
c_b_init_data = True
c_lrn_rule_fn = 'none' # 'load', 'learn', 'none'

els_sets = []
set_names = [lname +'s' for lname in c_set_list]
__rules_mgr = None
__mpdb_mgr = None
__rules_mod = None
__ai_mgr = None
__bitvec_mgr = None
__rec_def_type = None
__mpdbs_mgr = None
__nlbitvec_mgr = None
__phrases_mgr = None
__phraseperms_mgr = None
__d_mgrs = dict()
l_names = []
l_countries = []
l_objects = []
c_b_learn_full_rules = False
c_b_learn_full_rules_nl = True
c_b_save_freq_stats= False
c_story_len = 30 # 200
c_num_stories = 5000
c_num_plays = 100
c_b_dummy = False
l_dummy_types = []
l_dummy_events = []
l_dummy_ruleid = []
g_dummy_idx = -1
c_b_gpsai = True
c_b_save_phrases = False # Create a file of phrases with the rule that generated them

e_player_decide = Enum('e_player_decide', 'goto pickup ask_where tell_where ask_give give')

def mod_init():
	global els_sets

	for ifname, fname in enumerate(c_set_list):
		fh_names = open('adv/' + fname + 's.txt', 'rb')
		fr_names = csv.reader(fh_names, delimiter=',')
		all_names = [lname[0] for lname in fr_names]
		els_sets.append(all_names)

	l_agents = els_sets[set_names.index('names')]

	return 	els_sets, set_names, l_agents, c_rules_fn, c_ext_rules_fn, c_phrase_freq_fnt, c_phrase_bitvec_dict_fnt, \
			c_bitvec_saved_phrases_fnt, c_rule_grp_fnt, c_nlbitvec_dict_input_fnt, c_nlbitvec_dict_output_fnt, \
			c_nlbitvec_clusters_fnt, c_nlbitvec_rules_fnt, c_b_restart_from_glv, c_lrn_rule_fn

def set_mgrs(rules_mgr, mpdb_mgr, ai_mgr, bitvec_mgr, rules_mod):
	global __rules_mgr, __mpdb_mgr, __ai_mgr, __bitvec_mgr, __rules_mod, __rec_def_type, __d_mgrs
	__rules_mgr, __mpdb_mgr, __ai_mgr, __bitvec_mgr, __rules_mod = rules_mgr, mpdb_mgr, ai_mgr, bitvec_mgr, rules_mod
	t = {'rules':__rules_mgr, 'mpdb': __mpdb_mgr, 'ai':__ai_mgr, 'bitvec':__bitvec_mgr}
	for k, v in t.iteritems():
		__d_mgrs[k] = v
	__rec_def_type = rules_mod.rec_def_type

	__ai_mgr.set_constants(c_goal_init_level_limit, c_goal_max_level_limit, c_max_story_time_to_repeat)

def set_nl_mgrs(nlbitvec_mgr, phrases_mgr, mpdbs_mgr, phraseperms_mgr):
	global __mpdbs_mgr, __nlbitvec_mgr, __phrases_mgr, __d_mgrs
	__mpdbs_mgr = mpdbs_mgr
	__nlbitvec_mgr = nlbitvec_mgr
	__phrases_mgr = phrases_mgr
	__phraseperms_mgr= phraseperms_mgr
	t = {'mpdbs':__mpdbs_mgr, 'nlbitvec': __nlbitvec_mgr, 'phrases':__phrases_mgr, 'phraseperms':__phraseperms_mgr}
	for k, v in t.iteritems():
		__d_mgrs[k] = v



# def get_mpdb_mgr():
# 	return __mpdb_mgr
#
# def get_ai_mgr():
# 	return __ai_mgr

def get_mgr(name):
	return __d_mgrs[name]


def init_per_story_sets():
	global l_objects, l_countries, l_names
	l_names = random.sample(els_sets[set_names.index('names')], c_num_agents_per_story)
	l_objects = random.sample(els_sets[set_names.index('objects')], c_num_objects_per_story)
	l_countries = random.sample(els_sets[set_names.index('countries')], c_num_countries_per_story)
	return [l_names, l_objects, l_countries], ['names', 'objects', 'countries']

def init_functions():
	d_fns = {	'mod_init':mod_init,
				# 'get_mpdb_mgr':get_mpdb_mgr,
				# 'get_ai_mgr':get_ai_mgr,
				'create_initial_db':create_initial_db_dummy if c_b_dummy else create_initial_db,
				 'get_num_decision_rules':get_num_decision_rules,
				'init_per_story_sets':init_per_story_sets,
				# 'set_player_goal':set_player_goal,
				'get_decision_for_player':get_decision_for_player_dummy if c_b_dummy
						else (get_decision_by_goal if c_b_gpsai else get_decision_for_player),
				'get_mgr':get_mgr,
				'get_decision_ruleid_name':get_decision_ruleid_name}
	return d_fns

def create_initial_db():
	l_db, l_db_names, l_db_poss, l_db_rule_names = [], [], [], []

	l_db += [[name, 'is located in', random.choice(l_countries)] for name in l_names]
	l_db_rule_names += ['init_located' for _ in l_names]
	l_db += [[o, 'is free in', random.choice(l_countries)] for o in l_objects]
	l_db_rule_names += ['init_free_in' for _ in l_objects]
	l_db += [[name, 'wants', random.choice(l_objects)] for name in l_names]
	l_db_rule_names += ['init_wants' for _ in l_names]
	l_db_names += ['main' for _ in l_db]
	l_db += [['I', 'am', name] for name in l_names]
	l_db_rule_names += ['init_am' for _ in l_names]
	l_db_names += l_names

	l_db_poss += [	[	[__rec_def_type.obj, name],
						[__rec_def_type.obj, 'is located in'],
						[__rec_def_type.like, l_countries[0], 0.]
					] for name in l_names ]
	l_db_poss += [	[	[__rec_def_type.like, l_names[0], 0.],
						[__rec_def_type.obj, 'is located in'],
						[__rec_def_type.obj, place]
					] for place in l_countries ]
	l_db_poss += [	[	[__rec_def_type.obj, o],
						[__rec_def_type.obj, 'is free in'],
						[__rec_def_type.like, l_countries[0], 0.]
					] for o in l_objects ]
	l_db_poss += [	[	[__rec_def_type.like, l_objects[0], 0.],
						[__rec_def_type.obj, 'is free in'],
						[__rec_def_type.obj, place]
					] for place in l_countries ]
	# l_db_poss += [[name, 'is located in', place] for place in l_countries for name in l_names ]
	# l_db_poss += [[o, 'is free in', place] for place in l_countries for o in l_objects ]
	# l_db_poss += [[o, 'is held in', place] for place in l_countries for o in l_objects ]
	# l_db_poss += [[name, 'has', o] for o in l_objects for name in l_names ]
	# # l_db_poss += [[o, 'is free in', random.sample(l_countries, len(l_countries))] for o in l_objects]
	#
	# l_db_names += ['poss' for _ in l_db_poss]
	# l_db += l_db_poss

	assert len(l_db) == len(l_db_rule_names), 'init. db and rule names must have the same length'
	return l_db_names, l_db, l_db_poss, l_db_rule_names

def create_initial_db_dummy():
	global l_dummy_types, l_dummy_events, l_dummy_ruleid, g_dummy_idx
	l_db, l_db_names = [], []

	fh = open(c_dummy_init_fn, 'rb')
	fr = csv.reader(fh, delimiter='\t')
	for row in fr:
		l_db += [row[1:]]
		l_db_names += [row[0]]
	fh.close()
	# l_db_names += ['main' for _ in l_db]
	# l_db += [['I', 'am', name] for name in l_names]
	# l_db_names += l_names

	fh = open(c_dummy_events_fn, 'rb')
	fr = csv.reader(fh, delimiter='\t')
	for row in fr:
		if row[0] == '#':
			continue
		l_dummy_types += [row[0]]
		l_dummy_events += [row[1:-1]]
		l_dummy_ruleid += [e_player_decide[row[-1]]]
		g_dummy_idx = -1

	return l_db_names, l_db, [], ['dummy_init' for _ in l_db]

def make_decision_by_goal(player_name, phase_data, rule_stats):
	assert False, 'Old code?'
	l_compul_stmt = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								   player_name, ['compul_goal_actv'])[1]
	for compul_stmt in l_compul_stmt:
		l_poss_action = __mpdb_mgr.run_rule(__rules_mod.convert_single_bound_phrase_to_wlist(compul_stmt), phase_data,
								   player_name, ['event_from_decide'])
		if l_poss_action[1] != []:
			return [], compul_stmt

	goal_stmt = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								   player_name, [], ['get_goal_phrase'])[1][0]
	db_name, goal_init_level_limit = player_name, c_goal_init_level_limit
	l_var_opt_objs = __ai_mgr.set_player_goal(	player_name, goal_stmt, db_name, phase_data,
												var_obj_parent=None, calc_level=0,
												calc_level_limit=goal_init_level_limit)
	# for var_opt_obj in l_var_opt_objs: var_opt_obj.calc_best_score()
	for goal_level_limit in range(goal_init_level_limit, c_goal_max_level_limit+1, 2):
		l_phrase_actions_tried, l_calc_level_tried = [], []
		__ai_mgr.set_calc_level(goal_init_level_limit, goal_level_limit)
		action_selected, action_id_selected = \
			__ai_mgr.select_action(	l_var_opt_objs, player_name, db_name, phase_data,
									goal_init_level_limit, l_phrase_actions_tried, l_calc_level_tried)
		if action_selected != []:
			break

	return l_var_opt_objs, action_selected

def add_phrase_to_get_decision(player_name, phase_data, rule_stats, new_phrase):
	assert False, 'Old code?'
	__mpdb_mgr.add_phrase_text(player_name, new_phrase, phase_data)
	_, action_selected = make_decision_by_goal(player_name, phase_data, rule_stats)
	if action_selected == []:
		__mpdb_mgr.remove_phrase_text(player_name, new_phrase, phase_data)
	return action_selected


def get_decision_by_goal_old(player_name, phase_data, rule_stats):
	l_var_opt_objs, action_selected = make_decision_by_goal(player_name, phase_data, rule_stats)

	if action_selected == []:
		l_unmatched_match_phrases = []
		__ai_mgr.get_unmatch_opts(l_var_opt_objs, player_name, player_name, l_unmatched_match_phrases)
		if l_unmatched_match_phrases != []:
			action_selected = \
				__ai_mgr.add_poss_stmt(	l_unmatched_match_phrases, player_name, player_name,
										phase_data, rule_stats, add_phrase_to_get_decision)
	return __rules_mod.convert_single_bound_phrase_to_wlist(action_selected), 0 # action_id_selected

def get_decision_by_goal(player_name, phase_data, rule_stats):
	return __ai_mgr.get_decision_by_goal(player_name, phase_data, rule_stats)

def get_num_decision_rules():
	return len(e_player_decide)

def get_decision_for_player_dummy(player_name, phase_data, rule_stats):
	global g_dummy_idx
	g_dummy_idx += 1
	if g_dummy_idx >= len(l_dummy_types):
		print('Dummy run finished')
		exit()
	if l_dummy_types[g_dummy_idx] == 'e':
		return l_dummy_events[g_dummy_idx], l_dummy_ruleid[g_dummy_idx].value-1

	if l_dummy_types[g_dummy_idx] == 'g':
		return get_decision_by_goal(l_dummy_events[g_dummy_idx][0], phase_data, rule_stats)

	return get_decision_for_player(	l_dummy_events[g_dummy_idx][0], phase_data,
									rule_stats, l_dummy_ruleid[g_dummy_idx])

total_time = 0

def time_decor(fn):
	def wr(*args, **kwargs):
		global total_time
		s = timeit.default_timer()
		r = fn(*args, **kwargs)
		total_time += timeit.default_timer() - s
		return r
	return wr

def get_decision_ruleid_name(ruleid):
	return 'decision_' + e_player_decide(ruleid+1)._name_
# @profile_decor
def get_decision_for_player(player_name, phase_data, rule_stats, decision_choice_src = None):
	for one_try in range(c_num_tries_per_player):
		decision_choice =  decision_choice_src
		if decision_choice == None:
			decision_choice = np.random.choice([e_player_decide.goto, e_player_decide.pickup,
												e_player_decide.ask_where, e_player_decide.tell_where,
												e_player_decide.ask_give, e_player_decide.give],
											   p=[0.02, 0.28, 0.2, 0.2, 0.15, 0.15])
		# decision_choice = e_player_decide.ask_where
		ruleid = decision_choice.value-1
		if c_b_learn_full_rules or c_b_learn_full_rules_nl:
			bfail = random.random() < rule_stats[ruleid][1] / (rule_stats[ruleid][0] + rule_stats[ruleid][1] + 1e-6)
		else:
			bfail = False

		if decision_choice == e_player_decide.goto:
			player_loc = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_location'])[1][0][0][1]
			dest = player_loc if bfail else random.choice(tuple(set(l_countries)-set([player_loc])))
			if random.random() < 0.5:
				l_has_my_obj = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
									player_name, [], ['has_want_obj'])[1]
				if l_has_my_obj == [] or l_has_my_obj[0][0][1] != 'yes':
					l_want_loc = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
										player_name, [], ['get_want_loc', 'get_want_loc2'])[1]
					if l_want_loc != []:
						poss_dest = l_want_loc[0][0][1]
						if poss_dest == player_loc: continue
						dest = poss_dest
			return [player_name, 'decided to', 'go to', dest], ruleid
		elif decision_choice == e_player_decide.pickup:
			want_obj = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_want_obj'])[1][0][0][1]
			l_free_objs = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_free_objs'])[1]
			if l_free_objs == []: continue
			wlist_objs_els = __rules_mod.convert_phrase_to_word_list(l_free_objs)
			wlist_objs = [o[0] for o in wlist_objs_els]
			pickup_obj = random.choice(tuple(set(l_objects)-set(wlist_objs))) if bfail else random.choice(wlist_objs)
			l_has_my_obj = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
											player_name, [], ['has_want_obj'])[1]
			if l_has_my_obj == [] or l_has_my_obj[0][0][1] != 'yes':
				if want_obj in wlist_objs:
					pickup_obj = want_obj
			return [player_name, 'decided to', 'pick up', pickup_obj],ruleid
		elif decision_choice == e_player_decide.ask_where:
			want_obj = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_want_obj'])[1][0][0][1]
			l_want_loc = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_want_loc', 'get_want_loc2'])[1]
			if l_want_loc != []:
				continue
			l_ask_cands = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_ask_cands'])[1]
			if l_ask_cands == []: continue
			wlist_player_els = __rules_mod.convert_phrase_to_word_list(l_ask_cands)
			wlist_players = [o[0] for o in wlist_player_els]
			player_asked = random.choice(tuple(set(l_names)-set(wlist_players))) if bfail \
					else random.choice(wlist_players)
			return [player_name, 'decided to', 'ask', player_asked, 'where is', want_obj],ruleid
		elif decision_choice == e_player_decide.tell_where:
			l_tell_cands = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_tell_cands', 'get_tell_cands2'])[1]
			if l_tell_cands == []:
				continue
			wlist_cand_els = __rules_mod.convert_phrase_to_word_list(l_tell_cands)
			icand = random.randrange(0, len(wlist_cand_els))
			player_told, obj = wlist_cand_els[icand]
			if bfail:
				if random.random() < 0.5: player_told = random.choice(l_names)
				else: obj = random.choice(l_objects)
			return [player_name, 'decided to', 'tell', player_told,
					'where is', obj],ruleid
		elif decision_choice == e_player_decide.ask_give:
			l_has_my_obj = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
												player_name, [], ['has_want_obj'])[1]
			if l_has_my_obj != [] and l_has_my_obj[0][0][1] == 'yes': continue
			l_ask_give_cands = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_ask_give_cands'])[1]
			if l_ask_give_cands == []: continue
			want_obj = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
										   player_name, [], ['get_want_obj'])[1][0][0][1]
			player_asked = l_ask_give_cands[0][0][1]
			if bfail:
				if random.random() < 0.5: player_asked = random.choice(l_names)
				else: want_obj = random.choice(l_objects)
			return [player_name, 'decided to', 'ask', player_asked, 'for', want_obj], ruleid
		elif decision_choice == e_player_decide.give:
			l_give_cands = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
												player_name, [], ['get_give_cands'])[1]
			if l_give_cands == []: continue
			wlist_cand_els = __rules_mod.convert_phrase_to_word_list(l_give_cands)
			want_obj = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
										   player_name, [], ['get_want_obj'])[1][0][0][1]
			l_cand_objs = [cand[1] for cand in wlist_cand_els]
			if want_obj in l_cand_objs:
				del wlist_cand_els[l_cand_objs.index(want_obj)]
			if wlist_cand_els == []: continue
			icand = random.randrange(0, len(wlist_cand_els))
			player_to_give, obj = wlist_cand_els[icand]
			if bfail:
				if random.random() < 0.5: player_to_give = random.choice(l_names)
				else: obj = random.choice(l_objects)
			return [player_name, 'decided to', 'give', player_to_give, obj], ruleid
	return [],-1
