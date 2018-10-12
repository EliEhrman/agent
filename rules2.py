from __future__ import print_function
import sys
import csv
from enum import Enum
from StringIO import StringIO
import copy
import collections
import random
import numpy as np

# from rules import conn_type
# from rules import rec_def_type
# import makerecs as mr

conn_type = Enum('conn_type', 'single AND OR start end Insert Remove Modify IF THEN Broadcast replace_with_next, Unique')
rec_def_type = Enum('rec_def_type', 'obj conn var error set like')
# see notebook on 2nd Nov
rule_type = Enum('rule_type', 'story_start event_from_decide state_from_state state_from_event '
							  'event_from_event block_event knowledge_query query event_from_none')
nt_vars = collections.namedtuple('nt_vars', 'loc, b_bound, b_must_bind, val, cd, iext_var, b_resolved')
nt_vars.__new__.__defaults__ = (False, False, None, None, -1, False)
nt_match_phrases = collections.namedtuple('nt_match_phrases', 'istage, b_matched, phrase')


class cl_fixed_rules(object):
	def __init__(self, fn):
		self.__l_rules = []
		self.__l_categories = []
		self.__l_names = []
		self.load_rules(fn)

	def load_rules(self, fn):
		l_rules_data = []
		try:
		# if True:
			with open(fn, 'rb') as fh:
				csvr = csv.reader(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				if int(version_str) != 1:
					raise ValueError('rules2 rules file', fn, 'version cannot be used. Starting from scratch')
				rule_start_marker = next(csvr)[0]
				if rule_start_marker != 'rules start':
					raise IOError('no rules start marker')
				# for irule in xrange(int(num_rules)):
				while True:
					trule = next(csvr)
					if trule[0] == 'rules end':
						break
					rule_name, category, srule = trule
					srule = self.extract_ml_srule(srule, csvr)
					l_rules_data.append((rule_name, category, srule))
		except ValueError as verr:
			print(verr.args)
		except IOError:
		# except:
			print('Could not open db_len_grps file! Starting from scratch.')
		except:
			print('Unexpected error:', sys.exc_info()[0])
			raise

		for rule_name, category, srule in l_rules_data:
			rule_pre = extract_rec_from_str(srule)
			rule, var_dict = [], dict()
			for iel, el in enumerate(rule_pre):
				if el[0] in [rec_def_type.like, rec_def_type.obj] and len(el) > 3:
					var_dict[el[3]] = iel
					rule += [el[:3]]
				elif el[0] == rec_def_type.var:
					rule += [[el[0], var_dict[el[1]]]]
					if len(el) > 2:
						rule[-1] += [el[2]]
				elif el[0] == rec_def_type.conn \
						and el[1] in [conn_type.Insert, conn_type.Modify, conn_type.Broadcast,
									  conn_type.Remove, conn_type.Unique, conn_type.start] \
						and len(el) > 2:
					rule += [el[:2] + [var_dict[e] for e in el[2:]]]
				else:
					rule += [el]

			self.__l_categories.append(category)
			self.__l_rules.append(rule)
			self.__l_names.append(rule_name)

		pass

	def extract_ml_srule(self, srule, csvr):
		ret = ''
		if srule[:3] == 'ml,':
			srule = srule[3:]
			while srule[-4:] != ',mle':
				ret += srule
				srule = next(csvr)[-1]
			ret += srule[:-4]
			return  ret
		return srule

	def add_to_bitvec_mgr(self, bitvec_mgr):
		for irule, rule in enumerate(self.__l_rules):
			bitvec_mgr.add_fixed_rule(rule, self.__l_categories[irule], self.__l_names[irule].rstrip('.'))

	def parse_phrase_for_mod(self, phrase):
		if phrase[0][0] != rec_def_type.conn:
			raise ValueError('Error. The first el in phrase for mod must be a rec_def_type.conn with insert, modify or remove')

		mod_type = phrase[0][1]
		# if len(phrase[0] > 2):
		# 	l_db_names = phrase[0][2:]
		# else:
		# 	l_db_names = ['main']

		remove_phrase, insert_phrase, m_unique_bels, b_insert_next = [], [], [], False
		if mod_type  == conn_type.Modify:
			for el in phrase[1:]:
				if el[0] != rec_def_type.obj:
					raise ValueError('Error. Badly formed phrase for mod', phrase)
				if b_insert_next:
					b_insert_next = False
				else:
					remove_phrase += [el[1]]
					m_unique_bels.append(True)
				insert_phrase += [el[1]]
				if len(el) > 2 and el[2] == True:
					b_insert_next = True
					insert_phrase.pop()
		if mod_type == conn_type.Unique:
			for el in phrase[1:]:
				if el[0] != rec_def_type.obj:
					raise ValueError('Error. Badly formed phrase for mod', phrase)
				insert_phrase += [el[1]]
				remove_phrase += [el[1]]
				# if len(el) > 2 and el[2] == True:
				m_unique_bels.append(len(el) > 2 and el[2] == True)
		elif mod_type == conn_type.Insert:
			insert_phrase = [el[1] for el in phrase[1:]]
		elif mod_type == conn_type.Remove:
			# remove_phrase = [el[1] for el in phrase[1:]]
			# m_unique_bels= [True for _ in phrase[1:]]
			for el in phrase[1:]:
				if el[0] != rec_def_type.obj:
					raise ValueError('Error. Badly formed phrase for mod', phrase)
				remove_phrase += [el[1]]
				# if len(el) > 2 and el[2] == True:
				m_unique_bels.append(len(el) > 2 and el[2] == True)

		return insert_phrase, remove_phrase , m_unique_bels

	def parse_phrase_for_mod_db(self, phrase):
		if phrase[0][1] not in [conn_type.Broadcast, conn_type.Insert,
										conn_type.Remove, conn_type.Modify, conn_type.Unique]:
			return None
		if len(phrase[0]) <= 2:
			return None
		db_name = phrase[0].pop()
		return db_name


def gen_rec_str(rec):
	if rec == None:
		return ''
	lel = []
	for el in rec:
		if el[0] == rec_def_type.conn:
			lcvo = ['c']
			if el[1] == conn_type.AND:
				lcvo += ['a']
			elif el[1] == conn_type.OR:
				lcvo += ['r']
			elif el[1] == conn_type.start:
				lcvo += ['s']
			elif el[1] == conn_type.end:
				lcvo += ['e']
			elif el[1] == conn_type.Insert:
				lcvo += ['i']
			elif el[1] == conn_type.Unique:
				lcvo += ['u']
			elif el[1] == conn_type.Remove:
				lcvo += ['d']
			elif el[1] == conn_type.Modify:
				lcvo += ['m']
			elif el[1] == conn_type.IF:
				lcvo += ['f']
			elif el[1] == conn_type.THEN:
				lcvo += ['t']
			else:
				print('Coding error in gen_rec_str. Unknown rec_def_type. Exiting!')
				exit()
		elif el[0] == rec_def_type.var:
			lcvo = ['v']
			# lcvo += [str(el[1]).rjust(2, '0')]
			lcvo += [el[1]]
		elif el[0] == rec_def_type.obj:
			lcvo = ['o']
			lcvo += [el[1]]
		elif el[0] == rec_def_type.like:
			lcvo = ['l']
			lcvo += [el[1], el[2]]
		else:
			lcvo = ['e', '-1']
		lel += [':'.join(map(str, lcvo))]

	cvo_str =  ','.join(map(str, lel))
	return cvo_str

def extract_rec_from_str(srec):
	if srec == '':
		return None

	f = StringIO(srec)
	# csvw = csv.writer(l)
	rec = []
	lelr = csv.reader(f, delimiter=',')
	row = next(lelr)
	for lcvo in row:
		fcvo = StringIO(lcvo)
		lelf = next(csv.reader(fcvo, delimiter=':'))
		if lelf[0] == 'c':
			el = [rec_def_type.conn]
			if lelf[1] == 'a':
				el += [conn_type.AND]
			elif lelf[1] == 'r':
				el += [conn_type.OR]
			elif lelf[1] == 's':
				el += [conn_type.start]
			elif lelf[1] == 'e':
				el += [conn_type.end]
			elif lelf[1] == 'i':
				el += [conn_type.Insert]
			elif lelf[1] == 'u':
				el += [conn_type.Unique]
			elif lelf[1] == 'm':
				el += [conn_type.Modify]
			elif lelf[1] == 'd':
				el += [conn_type.Remove]
			elif lelf[1] == 'f':
				el += [conn_type.IF]
			elif lelf[1] == 't':
				el += [conn_type.THEN]
			elif lelf[1] == 'b':
				el += [conn_type.Broadcast]
			else:
				print('Unknown rec def. Exiting.')
				exit()
			if lelf[1] in ['s', 'i', 'u', 'm', 'd', 'b']:
				if len(lelf) > 2:
					el += [int(v) for v in lelf[2:]]
		elif lelf[0] == 'v':
			el = [rec_def_type.var]
			el += [int(lelf[1])]
			if len(lelf) > 2 and lelf[2] == 'r':
				el += [conn_type.replace_with_next]
		elif lelf[0] == 'o':
			el = [rec_def_type.obj]
			el += [lelf[1]]
			if len(lelf) > 2 and lelf[2] == 'r':
				el += [conn_type.replace_with_next]
		elif lelf[0] == 'l':
			el = [rec_def_type.like]
			el += [lelf[1], float(lelf[2])]
			if len(lelf) > 3:
				el += [int(lelf[3])]

		else:
			el = [rec_def_type.error]
			el += [lelf[1]]

		rec += [el]

	return rec


def make_rule_arr(rule):
	el = rule[0]
	core = copy.deepcopy(rule)
	if el[0] == rec_def_type.conn and el[1] == conn_type.AND:
		core = core[1:-1]
	start, end = -1, -1
	b_inside = False
	core_arr = []
	for iel, el in enumerate(core):
		if not b_inside and el[0] == rec_def_type.conn and el[1] == conn_type.start:
			b_inside = True
			start = iel
		elif b_inside and el[0] == rec_def_type.conn and el[1] == conn_type.end:
			b_inside = False
			end = iel
			core_arr.append(core[start:end])
	return core_arr

def place_vars_in_phrase(vars_dict, gens_rec):
	result = []
	for el in gens_rec:
		if el[0] == rec_def_type.obj:
			idx = vars_dict.get(el[1], -1)
			if idx >= 0:
				new_el = []
				for inel, nel in enumerate(el):
					if inel == 0:
						new_el.append(rec_def_type.var)
					elif inel == 1:
						new_el.append(idx)
					else:
						new_el.append(nel)
				result.append(new_el)
			else:
				result.append(el)
		else:
			result.append(el)

	return result

def replace_with_vars_in_wlist(l_wlist_src, l_phrase_result):
	vars_dict, l_wlist_vars, l_wlist_lens = dict(), [], []
	for iwlist, wlist in enumerate(l_wlist_src):
		for iel, el in enumerate(wlist):
			iwlist_src, pos_src = vars_dict.get(el, (-1, -1))
			if iwlist_src == -1:
				vars_dict[el] = (iwlist, iel)
			else:
				l_wlist_vars.append((iwlist_src, pos_src, iwlist, iel))
		if iwlist == 0:
			l_wlist_lens.append(len(wlist))
		else:
			l_wlist_lens.append(l_wlist_lens[-1] + len(wlist))

	if l_phrase_result == []:
		return l_wlist_vars, []

	phrase_result = l_phrase_result[0]
	new_result = []
	for ielr, elr in enumerate(phrase_result):
		if elr[0] != rec_def_type.obj:
			new_result.append(elr)
			continue
		word = elr[1]
		iwlist_src, pos_src = vars_dict.get(word, (-1, -1))
		if iwlist_src == -1:
			# new_phrase_list.append([rec_def_type.var, len(vars_dict)])
			new_result.append(elr)
			vars_dict[word] = (len(l_wlist_src), ielr)
		else:
			if iwlist_src == 0:
				dest_pos = pos_src
			else:
				dest_pos = l_wlist_lens[iwlist_src-1] + pos_src
			new_result.append([rec_def_type.var, dest_pos])

	return l_wlist_vars, new_result

def convert_phrase_to_word_list(statement_list):
	return [[el[1] for el in statement] for statement in statement_list]

def convert_single_bound_phrase_to_wlist(stmt):
	ret = []
	for el in stmt:
		if el[0] == rec_def_type.obj:
			ret.append(el[1])
		else:
			return []
	return ret


def build_vars_dict(phrase_list):
	new_phrase_list, vars_dict = [], dict()
	for iel, el in enumerate(phrase_list):
		if el[0] == rec_def_type.var:
			print('Error! Assuming the input phrase list contains no vars. Exiting!')
			exit()
		if el[0] != rec_def_type.obj:
			new_phrase_list.append(el)
			continue
		word = el[1]
		idx = vars_dict.get(word, None)
		if idx == None:
			# new_phrase_list.append([rec_def_type.var, len(vars_dict)])
			new_phrase_list.append(el)
			vars_dict[word] = iel
		else:
			new_phrase_list.append([rec_def_type.var, idx])

	return new_phrase_list, vars_dict

def convert_wlist_to_phrases(statement_list):
	return [[[rec_def_type.obj, item] for item in statement] for statement in statement_list]

def convert_wlist_to_phrase(phrase):
	return [[rec_def_type.obj, item] for item in phrase]

def does_stmt_match_goal(stmt, goal, bitvec_mgr):
	if len(goal) != len(stmt): return False
	iel, bmatch = -1, True
	for sel, gel in zip(stmt, goal):
		# if el[0] == rec_def_type.conn:
		# 	if el[1] in [conn_type.Insert, conn_type.Modify, conn_type.Unique]:
		# 		continue
		# 	else:
		# 		bmatch = False
		# 		break
		# iel += 1
		# if iel >= len(stmt):
		# 	bmatch = False
		# 	break
		# if el[0] == rec_def_type.var:
		# 	l_var_tbl += [(el[1], True, stmt[iel][1])]
		if gel[0] == rec_def_type.obj:
			if gel[1] != sel[1]:
				bmatch = False
				break
		elif gel[0] == rec_def_type.like:
			bmatch = bitvec_mgr.match_el_to_like(sel[1], gel[1], gel[2])
			if not bmatch: break

	return bmatch


class cl_var_match_opt_cont(object):
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


class cl_var_match_opts(object):
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
		self.__obj_id = cl_var_match_opts.max_obj_id
		cl_var_match_opts.max_obj_id += 1

	def get_calc_level(self):
		return self.__calc_level

	def get_parent_obj(self):
		return self.__parent_obj

	def get_parent_gg(self):
		return self.__parent_gg

	def get_l_match_phrases(self):
		return self.__l_match_phrases

	def get_match_phrase(self, iphrase):
		return self.__l_match_phrases[iphrase]

	def get_ll_match_iphrase_combos(self):
		return self.__ll_match_iphrase_combos

	def get_l_match_phrase_scores(self):
		return self.__l_match_phrase_scores

	def get_match_phrase_score(self, iphrase):
		return self.__l_match_phrase_scores[iphrase]

	def set_cont(self, cont):
		assert self.__cont == [], 'Warning. Setting a cont where there is already one set.'
		self.__cont = cont
	# def set_match_phrase_score(self, iphrase, score):
	# 	self.__l_match_phrase_scores[iphrase] = score

	def get_l_var_match_opt_conts(self):
		return self.__l_var_match_opt_conts

	def get_var_match_opt_conts(self, iphrase):
		return self.__l_var_match_opt_conts[iphrase]

	def get_l_var_match_opts(self, iphrase):
		cont = self.__l_var_match_opt_conts[iphrase]
		if cont == [] or cont == None: return []
		return cont.get_var_match_opt_objs()
	# def get_cont_var_match_opts(self, iphrase):

	def set_score_invalid(self):
		if not self.__b_score_valid: return
		self.__b_score_valid = False
		if self.__cont != []:
			self.__cont.set_score_invalid()

	def loop_check(self, test_cont):
		if self.__cont == []:
			return False
		elif self.__cont == test_cont:
			return True
		else:
			return self.__cont.loop_check(test_cont)

	def set_var_match_opts(self, iphrase, var_match_obj_cont):
		# self.__ll_var_match_opts[iphrase] = l_var_match_objs
		if var_match_obj_cont != []: #  and not self.loop_check(var_match_obj_cont):
			self.__l_var_match_opt_conts[iphrase] = var_match_obj_cont
			self.set_score_invalid()

	# def set_l_var_match_opts(self, ll_var_match_objs):
	# 	self.__ll_var_match_opts = ll_var_match_objs
	# 	self.set_score_invalid()

	def apply_cached_var_match_objs(self, l_cache_var_opt_objs, calc_level, calc_level_limit):
		assert False, 'Old code?'
		if calc_level >= calc_level_limit: return [] # [[] for _ in l_cache_var_opt_objs]
		cl_var_match_opts.num_apply_cache_calls += 1
		l_var_opt_objs = []
		for var_opt_obj in l_cache_var_opt_objs:
			var_opt_obj_copy = cl_var_match_opts(var_opt_obj.get_parent_gg(), copy.deepcopy(var_opt_obj.get_l_match_phrases()),
													copy.deepcopy(var_opt_obj.get_ll_match_iphrase_combos()),
													self, calc_level+1)
			for iphrase, l_var_match_opts in enumerate(var_opt_obj.get_ll_var_match_opts()):
				l_var_match_opts_copy = \
					var_opt_obj_copy.apply_cached_var_match_objs(l_var_match_opts, calc_level+1, calc_level_limit)
				var_opt_obj_copy.set_var_match_opts(iphrase, l_var_match_opts_copy)
			l_var_opt_objs.append(var_opt_obj_copy)
			# need a set_var_match_opts here b_top_call?
		return l_var_opt_objs

	def get_best_score(self):
		if not self.__b_score_valid:
			self.calc_best_score()
		return self.__best_score

	def set_best_score(self, best_score):
		self.__best_score = best_score

	def get_gg_name(self):
		return self.__parent_gg.get_name()

	def calc_best_score(self):
		self.__best_score = 0.
		self.__b_score_valid = True

		for iphrase, match_phrase in enumerate(self.__l_match_phrases):
			if match_phrase.b_matched:
				self.__l_match_phrase_scores[iphrase] = 1.
			elif self.__l_var_match_opt_conts[iphrase] == []:
				self.__l_match_phrase_scores[iphrase] = 0.
			else:
				l_var_match_opts = self.get_var_match_opt_conts(iphrase).get_var_match_opt_objs()
				max_child_score = max(l_var_match_opts, key=lambda x: x.get_best_score()).get_best_score()
				self.__l_match_phrase_scores[iphrase] = max_child_score

		l_match_phrase_scores = []
		best_score = 0.
		for icombo, l_match_iphrase_combo in enumerate(self.__ll_match_iphrase_combos):
			score, frac = 0., 1. / len(l_match_iphrase_combo)
			for iphrase in l_match_iphrase_combo:
				score += self.__l_match_phrase_scores[iphrase] * frac
			if score > best_score: best_score = score
			self.__l_combo_scores[icombo] = score
		self.__best_score = best_score
		# self.__b_score_valid = True

	def select_combo(self):
		if not self.__b_score_valid:
			self.calc_best_score()
		return np.random.choice(self.__ll_match_iphrase_combos, 1, p=self.__l_combo_scores)

	def get_sorted_l_combo(self):
		if not self.__b_score_valid:
			self.calc_best_score()
		return [match_iphrase_combo for _,match_iphrase_combo in
				sorted(zip([r * (1. - (random.random()/5.)) for r in self.__l_combo_scores],
						   self.__ll_match_iphrase_combos), reverse=True)]

	# def get_sorted_ll_opts(self):
	# 	if not self.__b_score_valid:
	# 		self.calc_best_score()
	# 	return [match_phrase_with_opt for _,match_phrase_with_opt in
	# 			sorted(zip([r * (1. - (random.random()/5.)) for r in self.__l_match_phrase_scores],
	# 					   zip(self.__l_match_phrases, self.__ll_var_match_opts)), key=lambda pair: pair[0], reverse=True)]




