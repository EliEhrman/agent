import csv
import random

c_set_list = ['name', 'object', 'countrie']
c_rules_fn = 'adv/rules.txt'
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
l_names = []
l_countries = []
l_objects = []
c_b_learn_full_rules = False
c_b_save_freq_stats= False
c_story_len = 200
c_num_stories = 500
c_num_plays = 100


def mod_init():
	global els_sets

	for ifname, fname in enumerate(c_set_list):
		fh_names = open('adv/' + fname + 's.txt', 'rb')
		fr_names = csv.reader(fh_names, delimiter=',')
		all_names = [lname[0] for lname in fr_names]
		els_sets.append(all_names)

	l_agents = els_sets[set_names.index('names')]

	return els_sets, set_names, l_agents, c_rules_fn, c_phrase_freq_fnt, c_phrase_bitvec_dict_fnt

def set_mgrs(rules_mgr, mpdb_mgr, rules_mod):
	global __rules_mgr, __mpdb_mgr, __rules_mod
	__rules_mgr, __mpdb_mgr, __rules_mod = rules_mgr, mpdb_mgr, rules_mod

def get_mpdb_mgr():
	return __mpdb_mgr

def init_per_story_sets():
	global l_objects, l_countries, l_names
	l_names = random.sample(els_sets[set_names.index('names')], c_num_agents_per_story)
	l_objects = random.sample(els_sets[set_names.index('objects')], c_num_objects_per_story)
	l_countries = random.sample(els_sets[set_names.index('countries')], c_num_countries_per_story)
	return [l_names, l_objects, l_countries], ['names', 'objects', 'countries']

def create_initial_db():
	l_db = []

	l_db += [[name, 'is located in', random.choice(l_countries)] for name in l_names]
	l_db += [[o, 'is free in', random.choice(l_countries)] for o in l_objects]
	l_db += [[name, 'wants', random.choice(l_objects)] for name in l_names]

	return l_db

def get_num_decision_rules():
	return 4

def get_decision_for_player(player_name, phase_data, rule_stats):
	for one_try in range(c_num_tries_per_player):
		ruleid = random.randint(0,1)
		ruleid = 0
		bfail = random.random() < rule_stats[ruleid][1] / (rule_stats[ruleid][0] + rule_stats[ruleid][1] + 1e-6)
		if ruleid == 0:
			player_loc = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_location'])[1][0][0][1]
			dest = player_loc if bfail else random.choice(tuple(set(l_countries)-set([player_loc])))
			return [player_name, 'decided to', 'go to', dest],ruleid
		elif ruleid == 1:
			l_free_objs = __mpdb_mgr.run_rule(['I', 'am', player_name], phase_data,
								player_name, [], ['get_free_objs'])[1]
			if l_free_objs == []: continue
			wlist_objs_els = __rules_mod.convert_phrase_to_word_list(l_free_objs)
			wlist_objs = [o[0] for o in wlist_objs_els]
			pickup_obj = random.choice(tuple(set(l_objects)-set(wlist_objs))) if bfail else random.choice(wlist_objs)
			return [player_name, 'decided to', 'pick up', pickup_obj],ruleid

	return [],-1
