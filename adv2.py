import csv
import random
from enum import Enum
import timeit
import numpy as np

c_set_list = ['name', 'object', 'countrie']
c_rules_fn = 'adv/rules.txt'
c_dummy_init_fn = 'adv/dummy_init.txt'
c_dummy_events_fn = 'adv/dummy_events.txt'
c_phrase_freq_fnt = '~/tmp/adv_phrase_freq.txt'
c_phrase_bitvec_dict_fnt = '~/tmp/adv_bin_dict.txt'
c_num_agents_per_story = 5
c_num_countries_per_story = 5
c_num_objects_per_story = 5
c_num_tries_per_player = 10

els_sets = []
set_names = [lname +'s' for lname in c_set_list]
__rules_mgr = None
__mpdb_mgr = None
__rules_mod = None
__ai_mgr = None
l_names = []
l_countries = []
l_objects = []
c_b_learn_full_rules = True
c_b_save_freq_stats= False
c_story_len = 200
c_num_stories = 500
c_num_plays = 100
c_b_dummy = False
l_dummy_types = []
l_dummy_events = []
l_dummy_ruleid = []
g_dummy_idx = -1

e_player_decide = Enum('e_player_decide', 'goto pickup ask_where tell_where ask_give give')

def mod_init():
	global els_sets

	for ifname, fname in enumerate(c_set_list):
		fh_names = open('adv/' + fname + 's.txt', 'rb')
		fr_names = csv.reader(fh_names, delimiter=',')
		all_names = [lname[0] for lname in fr_names]
		els_sets.append(all_names)

	l_agents = els_sets[set_names.index('names')]

	return els_sets, set_names, l_agents, c_rules_fn, c_phrase_freq_fnt, c_phrase_bitvec_dict_fnt

def set_mgrs(rules_mgr, mpdb_mgr, ai_mgr, rules_mod):
	global __rules_mgr, __mpdb_mgr, __ai_mgr, __rules_mod
	__rules_mgr, __mpdb_mgr, __ai_mgr, __rules_mod = rules_mgr, mpdb_mgr, ai_mgr, rules_mod

def get_mpdb_mgr():
	return __mpdb_mgr

def get_ai_mgr():
	return __ai_mgr

def init_per_story_sets():
	global l_objects, l_countries, l_names
	l_names = random.sample(els_sets[set_names.index('names')], c_num_agents_per_story)
	l_objects = random.sample(els_sets[set_names.index('objects')], c_num_objects_per_story)
	l_countries = random.sample(els_sets[set_names.index('countries')], c_num_countries_per_story)
	return [l_names, l_objects, l_countries], ['names', 'objects', 'countries']

def init_functions():
	d_fns = {	'mod_init':mod_init,
				'get_mpdb_mgr':get_mpdb_mgr,
				'get_ai_mgr':get_ai_mgr,
				'create_initial_db':create_initial_db_dummy if c_b_dummy else create_initial_db,
				 'get_num_decision_rules':get_num_decision_rules,
				'init_per_story_sets':init_per_story_sets,
				'set_player_goal':set_player_goal,
				'get_decision_for_player':get_decision_for_player_dummy if c_b_dummy else get_decision_for_player}
	return d_fns

def create_initial_db():
	l_db = []

	l_db += [[name, 'is located in', random.choice(l_countries)] for name in l_names]
	l_db += [[o, 'is free in', random.choice(l_countries)] for o in l_objects]
	l_db += [[name, 'wants', random.choice(l_objects)] for name in l_names]

	return l_db

def create_initial_db_dummy():
	global l_dummy_types, l_dummy_events, l_dummy_ruleid, g_dummy_idx
	l_db = []

	fh = open(c_dummy_init_fn, 'rb')
	fr = csv.reader(fh, delimiter='\t')
	for row in fr:
		l_db += [row]
	fh.close()
	fh = open(c_dummy_events_fn, 'rb')
	fr = csv.reader(fh, delimiter='\t')
	for row in fr:
		if row[0] == '#':
			continue
		l_dummy_types += [row[0]]
		l_dummy_events += [row[1:-1]]
		l_dummy_ruleid += [e_player_decide[row[-1]]]
		g_dummy_idx = -1

	return l_db

def set_player_goal(player_name, phase_data):
	goal_stmt = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								   player_name, [], ['get_goal_phrase'])[1][0]
	__ai_mgr.set_player_goal(player_name, goal_stmt,__rules_mgr)

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

# @time_decor
def get_decision_for_player(player_name, phase_data, rule_stats, decision_choice = None):
	for one_try in range(c_num_tries_per_player):
		if decision_choice == None:
			decision_choice = np.random.choice([e_player_decide.goto, e_player_decide.pickup,
												e_player_decide.ask_where, e_player_decide.tell_where,
												e_player_decide.ask_give, e_player_decide.give],
											   p=[0.02, 0.18, 0.2, 0.2, 0.2, 0.2])
		# decision_choice = e_player_decide.ask_where
		ruleid = decision_choice.value-1
		if c_b_learn_full_rules:
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
