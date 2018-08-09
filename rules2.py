from __future__ import print_function
import sys
import csv
from enum import Enum
from StringIO import StringIO
import copy

# from rules import conn_type
# from rules import rec_def_type
# import makerecs as mr

conn_type = Enum('conn_type', 'single AND OR start end Insert Remove Modify IF THEN Broadcast replace_with_next, Unique')
rec_def_type = Enum('rec_def_type', 'obj conn var error set like')
# see notebook on 2nd Nov
rule_type = Enum('rule_type', 'story_start event_from_decide state_from_state state_from_event '
							  'event_from_event block_event knowledge_query query event_from_none')


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
