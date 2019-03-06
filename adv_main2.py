"""
This is the a module from which the adv example runs. Like webdip it call the logic
module to learn rules.

However, it has its own dictionary and rules. The first is found in files in subdir adv
and the rules are implemented in adv_rules.py. This creates an oracle for story development
which logic must learn
"""

from __future__ import print_function
import random
import time
from enum import Enum
import importlib
import numpy as np
import timeit

import bitvec
import utils
from utils import profile_decor
from rules2 import conn_type
# import bitvec
import rules2
import mpdb
import gpsai
import nlbitvec
import phrases
import mpdbs
import phraseperms
import bdb
import cluster
import rules3
import gpsnlai

# import adv_config
# import adv_learn

complete_time = 0.
# def convert_phrase_to_word_list(statement_list):
# 	return [[el[1] for el in statement] for statement in statement_list]

@profile_decor
def play(	els_lists, num_stories, num_story_steps, learn_vars, mod, d_mod_fns):
	global complete_time
	mpdb_mgr = d_mod_fns['get_mgr']('mpdb')
	bitvec_mgr = d_mod_fns['get_mgr']('bitvec')
	rule_mgr = d_mod_fns['get_mgr']('rules')
	nlbitvec_mgr = d_mod_fns['get_mgr']('nlbitvec')
	gpsai_mgr = d_mod_fns['get_mgr']('ai')
	phrase_mgr = d_mod_fns['get_mgr']('phrases')
	mpdbs_mgr = d_mod_fns['get_mgr']('mpdbs')
	perms_mgr = d_mod_fns['get_mgr']('phraseperms')
	# bitvec_mgr = mpdb_mgr.get_bitvec_mgr()
	# nlbitvec_mgr = mpdb_mgr.get_nlbitvec_mgr()
	# gpsai_mgr = d_mod_fns['get_ai_mgr']()
	# start_rule_names = ['objects_start', 'people_start', 'people_want_start']  # ['people_start'] #
	# event_rule_names = ['pickup_rule', 'went_rule']
	# state_from_event_names = ['gen_rule_picked_up', 'gen_rule_picked_up_free', 'gen_rule_went', 'gen_rule_has_and_went',
	# 						  'gen_rule_knows_dynamic_action']
	# decide_rule_names = ['pickup_decide_rule']
	# event_from_decide_names = ['pickup_rule', 'went_rule']

	# train_rules = []
	# event_results = []
	event_step_id = [learn_vars[0]]
	# event_result_id_arr = []
	# el_set_arr = []

	for i_one_story in range(num_stories):
		# if i_one_story == 6:
		# 	bitvec_mgr.increase_rule_stages()

		l_player_events = []
		story_sets, set_names = d_mod_fns['init_per_story_sets']()
		story_names = story_sets[set_names.index('names')]

		e_story_loop_stage = Enum('e_story_loop_stage', 'story_init decision_init decision event state1 complete_state1 state2')

		story_loop_stage = e_story_loop_stage.story_init

		mpdb_mgr.clear_dbs()
		mpdbs_mgr.clear_dbs()

		# l_story_db_event_refs = []
		# story_db = []
		l_db_names, l_story_phrases, l_init_rule_names = d_mod_fns['create_initial_db']()
		l_poss_stmts = d_mod_fns['create_poss_db']()
		for db_name, story_phrase, init_rule_name in zip(l_db_names, l_story_phrases, l_init_rule_names):
			ilen, iphrase = bitvec_mgr.add_phrase(story_phrase,
												  (i_one_story, -1, e_story_loop_stage.story_init,
												   event_step_id[0]))
			inlphrase = phrase_mgr.add_phrase(story_phrase)
			# inlphrase = nlbitvec_mgr.add_phrase(story_phrase)
			bitvec_mgr.save_phrase(init_rule_name, story_phrase)
			mpdb_mgr.ext_insert([db_name], (ilen, iphrase), inlphrase)
			mpdbs_mgr.ext_insert([db_name], inlphrase)

		db_transfrs, trnsfr_rule_names =  mpdb_mgr.infer(['main'], (i_one_story, -1, story_loop_stage, event_step_id[0]),
												['state_from_start'])
		for one_transfer, trnsfr_rule_name in zip(db_transfrs, trnsfr_rule_names):
			if one_transfer[0][1] == conn_type.Insert:
				db_name = one_transfer[0][2]
				added_wlist = rules2.convert_phrase_to_word_list([one_transfer[1:]])[0]
				ilen, iphrase = bitvec_mgr.add_phrase(added_wlist,
													  (i_one_story, -1, story_loop_stage, event_step_id[0]))
				inlphrase = phrase_mgr.add_phrase(added_wlist)
				# inlphrase = nlbitvec_mgr.add_phrase(added_wlist)
				bitvec_mgr.save_phrase(trnsfr_rule_name, added_wlist)
				mpdb_mgr.ext_insert([db_name], (ilen, iphrase), inlphrase)
				mpdbs_mgr.ext_insert([db_name], inlphrase)

		if mod.c_b_nl:
			mpdbs_mgr.set_poss_db(l_poss_stmts)
		else:
			mpdb_mgr.set_poss_db(l_poss_stmts)

		localtime = time.asctime(time.localtime(time.time()))

		# mpdb_mgr.show_dbs()
		mpdbs_mgr.show_dbs()

		print("Local current time :", localtime)

		story_loop_stage = e_story_loop_stage.decision_init
		# decide_options = []
		player_event = None
		# event_result_list = []
		b_decision_made = False
		i_story_player = -1
		story_player_name = story_names[i_story_player]

		i_story_step = 0
		c_close_to_inf = 10000
		i_story_loop_stage = -1
		if i_one_story == 0:
			# player_decide_rules = adv_rules.init_decide_rules(els_sets, els_dict, story_player_name)
			num_descision_rules = d_mod_fns['get_num_decision_rules']()
			rule_stats = [[0.0, 0.0] for _ in range(num_descision_rules)]

		# s = timeit.default_timer()
		utils.profile_start('play story loop')
		num_since_cleanup = 0
		while i_story_loop_stage < c_close_to_inf:
			# complete_time += timeit.default_timer() - s
			# s = timeit.default_timer()
			utils.profile_end('play story loop')
			utils.profile_start('play story loop')

			i_story_loop_stage += 1
			if i_story_loop_stage >= c_close_to_inf - 1:
				print('Story loop stage seems stuck in an infinite loop. Next story!')
				i_story_loop_stage = -1
				break
			event_step_id[0] += 1
			if story_loop_stage == e_story_loop_stage.decision_init:
				num_since_cleanup += 1
				if num_since_cleanup > 10:
					mpdb_mgr.cleanup_srphrases()
					num_since_cleanup = 0
				# decide_options = []
				if i_story_player < len(story_names) - 1:
					i_story_player += 1
				else:
					if not b_decision_made:
						print('Story has reached an impasse. No player can make a decision.')
						i_story_loop_stage = -1
						break
					i_story_player = 0
					b_decision_made = False
				story_player_name = story_names[i_story_player]
				# d_mod_fns['set_player_goal'](story_player_name, (i_one_story, story_loop_stage, event_step_id[0]), 'main')

				# player_decide_rules = adv_rules.init_decide_rules(els_sets, els_dict, story_player_name)
				# ruleid = random.randint(0, len(player_decide_rules)-1)
				# rule = player_decide_rules[ruleid]
				# _, gens_recs = rules.gen_for_rule(b_gen_for_learn=False, rule=rule)
				# decide_options += gens_recs
				# random.shuffle(decide_options)
				story_loop_stage = e_story_loop_stage.decision
				continue
			elif story_loop_stage == e_story_loop_stage.decision:
				# if len(decide_options) == 0:
				# 	story_loop_stage = e_story_loop_stage.decision_init
				# else:
				# 	one_decide = (decide_options.pop(0).phrase())[1:-1]
				# one_decide, ruleid = \
				# 	mod.get_decision_for_player(story_player_name,
				# 										(i_one_story, story_loop_stage,
				# 										 event_step_id[0]), rule_stats)
				one_decide, ruleid = \
					d_mod_fns['get_decision_for_player'](story_player_name,
														(i_one_story, i_story_step, story_loop_stage,
														event_step_id[0]), rule_stats)
				if one_decide == []:
					story_loop_stage = e_story_loop_stage.decision_init
				else:
					phrase_mgr.add_phrase(one_decide)
					rule_name = d_mod_fns['get_decision_ruleid_name'](ruleid)
					bitvec_mgr.save_phrase(rule_name, one_decide)
					story_loop_stage = e_story_loop_stage.event
					b_decision_made = True
				continue

			elif story_loop_stage == e_story_loop_stage.event:
				# _, event_as_decided = story.infer_from_story(els_dict, els_arr, def_article_dict, story_db,
				# 											 b_apply_results=False,
				# 											 story_step=one_decide,
				# 											 step_effect_rules=event_from_decide_rules,
				# 											 b_remove_mod_hdr=False)
				l_event_result_rule_names = []
				_, event_as_decided =  mpdb_mgr.run_rule(one_decide, 	(i_one_story, i_story_step, story_loop_stage,
																		event_step_id[0]),
														'main', ['event_from_decide'], [], l_event_result_rule_names)
				if event_as_decided != []:
					print(one_decide)
					player_event = event_as_decided[0]
					event_that_decided = l_event_result_rule_names[0]
					player_event_phrase = rules2.convert_phrase_to_word_list([player_event[1:]])[0]
					phrase_mgr.add_phrase(player_event_phrase)
					out_str = 'time: ' + str(i_story_step) + '. Next story step: *** '
					out_str += ' '.join(player_event_phrase) # els.output_phrase(def_article_dict, out_str, player_event[1:])
					out_str += ' **** '
					print(out_str)
					l_player_events.append(player_event_phrase)
					ilen, iphrase = bitvec_mgr.add_phrase(l_player_events[-1], (i_one_story, i_story_step,
																				story_loop_stage, event_step_id[0]))
					inlphrase = phrase_mgr.add_phrase(l_player_events[-1])
					# inlphrase = nlbitvec_mgr.add_phrase(l_player_events[-1])
					bitvec_mgr.save_phrase(event_that_decided, l_player_events[-1])
					#handle deletes and modifies
					story_loop_stage = e_story_loop_stage.state1
				# else:
					# 	event_as_decided = []
					# 	print('Event blocked!')
					# 	story_loop_stage = e_story_loop_stage.decision
				else:
					story_loop_stage = e_story_loop_stage.decision

				if event_as_decided == []:
					rule_stats[ruleid][0] += 1.0
				else:
					rule_stats[ruleid][1] += 1.0
					print('rule stats:',  rule_stats, 'ruleid:', ruleid, 'rand thresh:', (0.99 * rule_stats[ruleid][0] / (rule_stats[ruleid][0] + rule_stats[ruleid][1])))
				# if event_as_decided != [] or (random.random() > (0.99 * rule_stats[ruleid][0] / (rule_stats[ruleid][0] + rule_stats[ruleid][1]))):
				if mod.c_b_learn_full_rules:
					# adv_learn.do_learn_rule_from_step(	event_as_decided, event_step_id[0], story_db, one_decide, '',
					# 									def_article_dict, db_len_grps, sess,
					# 									el_set_arr, glv_dict, els_sets, cascade_dict,
					# 									gg_cont, db_cont_mgr)
					# unindent the following to go back to rule learning
					mpdb_mgr.learn_rule(one_decide, event_as_decided,
										  (i_one_story, i_story_step, story_loop_stage, event_step_id[0]),
										  'main')
				if mod.c_b_learn_full_rules_nl: #  and mod.c_lrn_rule_mode == 'learn':
					mpdbs_mgr.learn_rule(	one_decide, event_as_decided,
											(i_one_story, i_story_step, story_loop_stage, event_step_id[0]),
											story_names[i_story_player], 'event_from_decide') # 'main') #
				if mod.c_lrn_rule_mode == 'load':
					mpdbs_mgr.test_rule(	one_decide, event_as_decided,
											(i_one_story, i_story_step, story_loop_stage, event_step_id[0]),
											story_names[i_story_player], ['event_from_decide']) #  # 'main'


			elif story_loop_stage == e_story_loop_stage.state1:
				# events_to_queue, l_dbs_to_mod = [], []
				# _, events_to_queue = story.infer_from_story(els_dict, els_arr, def_article_dict, story_db,
				# 											b_apply_results=False,
				# 											story_step=player_event[1:],
				# 											step_effect_rules=state_from_event_rules,
				# 											b_remove_mod_hdr=False)
				"""
				Here is the key to writing these rules:
				If you have an event, by default, only the main db knows about it. If there is a state_from_event rule
				then only the main db will be affected by the event. If there is a distr_from_event, then that will
				produce a set of other db's that will now be affected by this knowledge. So any distr will result in the
				state_from_event executing there too.
				If you write a br_state_from_event rule, then the rule is run on the main but state is affected in other
				db's. So if the event has state implications DON"T write a distr_from_event as well, since the same
				state_from_event will now be run on the peripheral db, resulting in the state being created twice.
				Example. gen_has_went from went event. That is distributed ONLY to the guy who went (know I went)
				The consequences of having and going are applied therefore to main and to the guy who went. There is also
				a br_state_from_event rule that will update the db of someone (say, Roy) seeing the guy coming. However,
				if you distribute the went event to Roy, he could be updated twice. So if you must do both, make sure 
				that the addition of state is either unique or else the old data (including the first addtion) must be
				removed.
				Remember, even if a rule is run on main, you can check that a phrase also exists in another db in order to
				work. Just put a var reference on the c:s clause. The pharse must exist in the main as well as in the 
				other db in order for the rule to succeed. 
				Please note. The br_state_from_event path as opposed to distr_from_event wil cause greater difficulty in
				learning. From the player/agent's perspective, there is no event followed by a consequence!    
				"""
				the_main_event = rules2.convert_phrase_to_word_list([player_event[1:]])[0]
				_, events_transfrs =  mpdb_mgr.run_rule(the_main_event, (i_one_story, i_story_step, story_loop_stage, event_step_id[0]),
														'main', ['distr_from_event'])
				result_rule_names = []
				l_dbs_to_mod, events_to_queue =  mpdb_mgr.run_rule(	the_main_event,
																	(i_one_story, i_story_step, story_loop_stage, event_step_id[0]),
																	'main', ['state_from_event', 'br_state_from_event'],
																	[], result_rule_names)
				for event_stmt, event_rule_name in zip(events_to_queue, result_rule_names):
					event_wlist = rules2.convert_phrase_to_word_list([event_stmt[1:]])[0]
					bitvec_mgr.save_phrase(event_rule_name, event_wlist)
				mpdb_mgr.extract_mod_db(l_dbs_to_mod, events_to_queue)
				for trnsfr in events_transfrs:
					if trnsfr[0][1] != conn_type.Broadcast or len(trnsfr[0]) <= 2:
						continue
					for db_name in trnsfr[0][2:]:
						# db_name = trnsfr[0][2]
						trnsfr_phrase = rules2.convert_phrase_to_word_list([trnsfr[1:]])[0]
						l_new_dbs, new_mods = mpdb_mgr.run_rule(trnsfr_phrase, (i_one_story, i_story_step,
																				story_loop_stage, event_step_id[0]),
																db_name, ['state_from_event'], [], result_rule_names)
						events_to_queue += new_mods
						l_dbs_to_mod += l_new_dbs
				# do_learn_rule_from_step(events_to_queue, event_step_id, story_db, player_event[1:], '',
				# 						def_article_dict, db_len_grps, sess, el_set_arr, glv_dict, els_sets)
				story_loop_stage = e_story_loop_stage.complete_state1

			else:
				print('Code flow error. Shouldnt get here')
				exit(1)

			if story_loop_stage == e_story_loop_stage.complete_state1:
				# s = timeit.default_timer()
				for db_name, event_result in zip(l_dbs_to_mod, events_to_queue):
					mpdb_mgr.apply_mods(db_name, event_result, (i_one_story, i_story_step, story_loop_stage, event_step_id[0]))
					mpdbs_mgr.apply_mods(db_name, event_result, rule_mgr)
				mpdb_mgr.apply_delayed_inserts()
				mpdbs_mgr.apply_delayed_inserts()
				bitvec_mgr.clear_all_db_arg_caches()
				gpsai_mgr.db_changed()
					# story_db, iremoved, iadded, added_phrase = \
					# 	rules.apply_mods(story_db, [rules.C_phrase_rec(event_result)], i_story_step)
					# if iremoved != -1:
					# 	l_story_db_event_refs.pop(iremoved)
					# if iadded != -1:
					# 	added_wlist = els.convert_phrase_to_word_list([added_phrase])[0]
					# 	ilen, iphrase = bitvec_mgr.add_phrase(added_wlist,
					# 										  (i_one_story, i_story_step, story_loop_stage, event_step_id[0]))
					# 	l_story_db_event_refs.append((ilen, iphrase))
				# print('All dbs for step', event_step_id[0], 'in story num', i_one_story, ':')
				# mpdb_mgr.show_dbs()
				mpdbs_mgr.show_dbs()
				story_loop_stage = e_story_loop_stage.decision_init
				i_story_step += 1
				if i_story_step >= num_story_steps:
					break
				i_story_loop_stage = -1
				# complete_time += timeit.default_timer() - s

			continue


		# end of loop over story steps
		# if i_one_story % adv_config.c_save_every == 0:
		# 	b_keep_working = adv_learn.create_new_conts(glv_dict, db_cont_mgr, db_len_grps, i_gg_cont)
		# 	adv_learn.save_db_status(db_len_grps, db_cont_mgr)
		# 	if not b_keep_working:
		# 		break

		if mod.c_b_save_phrases:
			bitvec_mgr.flush_saved_phrases()

		if mod.c_b_save_freq_stats:
			# story_phrases = [crec.phrase() for crec in story_db]
			# story_wlists = els.convert_phrase_to_word_list(story_phrases)
			story_wlists = mpdb_mgr.get_one_db_phrases('main')
			# adv_learn.create_phrase_freq_tbl(story_wlists + l_player_events)
			print('Here we would put the freq table ')

	# end of loop over stories

		# end of i_one_step loop
	# end of num stories loop

	# for rule in train_rules:
	# 	out_str = 'rule print: \n'
	# 	out_str = rules.print_rule(rule, out_str)
	# 	print(out_str)


def do_adv(els_lists, learn_vars, mod, d_mod_fns):

	learn_vars[0] = 0
	for iplay in range(mod.c_num_plays):
		play(	els_lists, mod.c_num_stories, mod.c_story_len, learn_vars, mod, d_mod_fns)
	print('Done!')
	exit(1)



def main():
	random.seed(9001)
	np.random.seed(9001)
	mod = importlib.import_module('adv2')
	d_mod_fns = getattr(mod, 'init_functions')()

	# following need not be string dynamic but keeping working code to show how it's done
	# els_sets, set_names, l_agents, rules_fn, phrase_freq_fnt, bitvec_dict_fnt = getattr(mod, 'mod_init')()
	els_sets, set_names, l_agents, rules_fn, ext_rules_fn, phrase_freq_fnt, bitvec_dict_fnt, \
			bitvec_saved_phrases_fnt, rule_grp_fnt, nlbitvec_dict_fnt, nlbitvec_dict_output_fnt, \
			cluster_fnt, rules_fnt, b_restart_from_glv, lrn_rule_mode \
		= d_mod_fns['mod_init']()
	# import adv2
	# els_sets, set_names, l_agents, rules_fn, phrase_freq_fnt, bitvec_dict_fnt = mod.mod_init()
	fixed_rule_mgr = rules2.cl_fixed_rules(rules_fn)
	ext_rule_mgr = rules3.cl_ext_rules(ext_rules_fn, nlbitvec.c_bitvec_size, lrn_rule_mode)
	bitvec_mgr = bitvec.cl_bitvec_mgr(mod)
	nlbitvec_mgr = None
	if mod.c_b_nl:
		phrases_mgr = phrases.cl_phrase_mgr(b_restart_from_glv, bitvec_saved_phrases_fnt)
		phraseperms_mgr = phraseperms.cl_phrase_perms(phrases_mgr)
		phrases_mgr.set_phraseperms(phraseperms_mgr)
		mpdbs_mgr = mpdbs.cl_mpdbs_mgr(phrases_mgr, phraseperms_mgr)
		bdb_global = bdb.cl_bitvec_db(phraseperms_mgr, 'global')
		cluster_mgr = cluster.cl_phrase_cluster_mgr(cluster_fnt, rule_grp_fnt)
		cluster_mgr.set_bdb_all(bdb_global)
		phraseperms_mgr.set_cluster_mgr(cluster_mgr)
		nlbitvec_mgr = nlbitvec.cl_nlb_mgr(	b_restart_from_glv, phrases_mgr, phraseperms_mgr, bdb_global,
											nlbitvec_dict_fnt, rule_grp_fnt,
											bitvec_saved_phrases_fnt, nlbitvec_dict_output_fnt, cluster_fnt)
		bdb_global.set_nlb_mgr(nlbitvec_mgr)
		mpdbs_mgr.set_nlb_mgr(nlbitvec_mgr)
		phraseperms_mgr.set_nlb_mgr(nlbitvec_mgr)
		cluster_mgr.set_nlb_mgr(nlbitvec_mgr)
		if mod.c_b_init_data:
			phrases_mgr.init_data()
		ext_rule_mgr.set_mgrs(nlbitvec_mgr, phrases_mgr, phraseperms_mgr)
		mpdbs_mgr.init_lrule_mgr(rules_fnt, lrn_rule_mode, ext_rule_mgr)
		mod.set_nl_mgrs(nlbitvec_mgr, phrases_mgr, mpdbs_mgr, phraseperms_mgr)
	mpdb_mgr = mpdb.cl_mpdb_mgr(bitvec_mgr, fixed_rule_mgr, len(l_agents), nlbitvec_mgr)
	gpsai_mgr = gpsai.cl_gpsai_mgr()
	gpsai_mgr.set_mgrs(fixed_rule_mgr, mpdb_mgr, gpsai_mgr, bitvec_mgr, rules2)
	gpsnlai_mgr = gpsnlai.cl_gpsnlai_mgr()
	gpsnlai_mgr.set_mgrs(mpdbs_mgr, nlbitvec_mgr, ext_rule_mgr, phrases_mgr, phraseperms_mgr, rules3)
	mod.set_mgrs(fixed_rule_mgr, mpdb_mgr, gpsai_mgr, bitvec_mgr, rules2) # use for learning rules while keeping the oracle classic
	# mod.set_mgrs(ext_rule_mgr, mpdbs_mgr, gpsnlai_mgr, nlbitvec_mgr, rules3)
	# mod.set_mgrs(fixed_rule_mgr, mpdb_mgr, gpsnlai_mgr, bitvec_mgr, rules2) # use for debugging gpsnlai
	l_all_set_words = mod.get_all_set_words()
	s_rule_words = bitvec_mgr.get_s_rule_clauses()
	gpsnlai_mgr.create_clause_dict(l_all_set_words + list(s_rule_words))
	ext_rule_mgr.init_vo(mpdbs_mgr)

	event_step_id = -1
	learn_vars = [event_step_id]
	do_adv(els_sets, learn_vars, mod, d_mod_fns)


	# all_dicts = logic_init()

if __name__ == "__main__":
    main()
