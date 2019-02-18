"""
mp stands for multi-player
This module provides support for multiple databases - often partial copies of each other
TYpically each player will have his own database representing his/her knowledge
Also, monte-carlo or tree-based search might use the db

mpdbs stands for small mpdb. It is intended to be a stripped down-version of the mpdb.
It maintains lists of phrases that are current in the various dbs but it does not
get involved in the bitvec db.

"""

from __future__ import print_function
import warnings
import bdb
import rule_learn

class cl_mpdbs_mgr(object):
	def __init__(self, phrase_mgr, phraseperms):
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms
		self.__bdb_story = bdb.cl_bitvec_db(phraseperms, 'story')
		self.__rule_mgr = None
		self.__lrule_mgr = None # for learned rules
		self.clear_dbs()

	def set_nlb_mgr(self, nlbitvec_mgr):
		self.__nl_el_mgr = nlbitvec_mgr
		self.__bdb_story.set_nlb_mgr(nlbitvec_mgr)

	def init_lrule_mgr(self, rules_fnt, lrn_rule_fn, rule_mgr):
		self.__rule_mgr = rule_mgr
		if lrn_rule_fn != 'none':
			self.__lrule_mgr = rule_learn.cl_lrule_mgr(	self.__phrase_mgr, self.__phraseperms, rules_fnt,
														lrn_rule_fn, rule_mgr)

	def clear_dbs(self):
		self.__l_dbs = []  # type: List[List[int]] # list of rphrase in each idb
		self.__d_db_names = dict()  # type: Dict[str, int] # map of db name to index in __l_dbs
		self.__l_rphrases = []  # type: List[int] # list of global rphrase. An rphrase is an index for a phrase in the phrases mgr
		self.__ll_idb_mrks = []   # type: List[List[bool]] # for each idb, list of bools for whether the phrase (indexed on l_srphrases) is in that idb
		self.__map_rphrase_to_irphrase = dict()  # type: Dict[int, int] # maps global ref to phrase (len and iphrase) of bitvec to idx of phrase in l_sphrase
		self.__l_delayed_inserts = [] # type: List[Tuple[int]] # list of pairs of (idb, rphrase) waiting to be inserted into a specific db
		self.__l_poss_stmts = [] # keeping here till rules start accessing this info. Perhpas belongs in another module
		self.__bdb_story.clear_db()

	def get_bdb_story(self):
		return self.__bdb_story

	def get_hcdb_story(self):
		return self.__bdb_story.get_hcbdb()

	def add_db(self, db_name):
		idb = self.__d_db_names.get(db_name, -1)
		if idb != -1:
			return idb
		idb = len(self.__l_dbs)
		self.__l_dbs.append([])
		if idb != 0:
			self.__bdb_story.agent_add(idb)
		# self.__l_d_story_len_refs.append(dict())
		self.__d_db_names[db_name] = idb
		if idb == 0:
			self.__ll_idb_mrks.append([])
		else:
			self.__ll_idb_mrks.append([False for _ in self.__ll_idb_mrks[0]])

		return idb

	def ext_insert(self, l_db_names, rphrase, bdelay=False):
		for db_name in l_db_names:
			idb = self.__d_db_names.get(db_name, -1)
			if idb == -1:
				# print('Error. mpdb requested to insert into', db_name, 'which doesnt exist.')
				# continue
				idb = self.add_db(db_name)
			if bdelay:
				if (idb, rphrase) in self.__l_delayed_inserts:
					# warnings.warn('Double insertion into delayed inserts')
					pass
				else:
					self.__l_delayed_inserts.append((idb, rphrase))
			else:
				self.do_base_insert(idb, rphrase)

		pass

	def do_base_insert(self, idb, rphrase):
		self.__l_dbs[idb].append(rphrase)
		isrphrase = self.__map_rphrase_to_irphrase.get(rphrase, -1)
		if isrphrase == -1:
			isrphrase = len(self.__l_rphrases)
			self.__map_rphrase_to_irphrase[rphrase] = isrphrase
			self.__l_rphrases.append(rphrase)
			# l_rperms = self.__phraseperms.get_perms(rphrase)
			self.__bdb_story.add_new_phrase(rphrase)
			for idb_mrk in self.__ll_idb_mrks:
				idb_mrk.append(False)
		if self.__ll_idb_mrks[idb][isrphrase]:
			warnings.warn('Warning! Attempting to add a phrase twice')
			db_name = self.get_db_name_from_idb(idb)
			print('not adding duplicate', self.__phrase_mgr.get_phrase(rphrase), 'to db', db_name)
		self.__ll_idb_mrks[idb][isrphrase] = True
		self.__bdb_story.agent_change_phrase(idb, rphrase, badd=True)


	def apply_delayed_inserts(self):
		for delayed_insert in self.__l_delayed_inserts:
			self.do_base_insert(*delayed_insert)
		self.__l_delayed_inserts = []

	def get_rphrases(self):
		return self.__l_rphrases

	def get_nd_idb_mrk(self, idb):
		l_idb_mrks = self.__ll_idb_mrks[idb]
		return l_idb_mrks

	def remove_phrase(self,  l_db_names, rphrase):
		isrphrase = self.__map_rphrase_to_irphrase.get(rphrase, -1)
		if isrphrase == -1:
			print('Error. mpdb requested to remove item', rphrase, 'that does not exist in any of the dbs.')
			return
		for db_name in l_db_names:
			idb = self.__d_db_names.get(db_name, -1)
			if idb == -1:
				print('Error. mpdb requested to remove from', db_name, 'which doesnt exist.')
				continue
			if rphrase not in self.__l_dbs[idb]:
				print('Error. mpdb requested to remove item', rphrase, 'from db', db_name, '.Item not found.')
				continue
			# self.__l_dbs[idb].remove(phrase_ref)
			self.__l_dbs[idb] = filter(lambda a: a != rphrase, self.__l_dbs[idb])
			self.__ll_idb_mrks[idb][isrphrase] = False
			self.__bdb_story.agent_change_phrase(idb, rphrase, badd=False)

	def get_idb_from_db_name(self, db_name):
		return self.__d_db_names.get(db_name, -1)

	def get_srphrases_text(self):
		return [self.__phrase_mgr.get_phrase(rphrase) for rphrase in self.__l_rphrases]

	def get_db_name_from_idb(self, idb):
		print('Warning. get_db_name_from_idb is a slow function. NOt intended for production')
		for kname, vidb in self.__d_db_names.iteritems():
			if vidb == idb:
				return kname
		return 'Name not found'

	def get_idb_rphrases(self, idb):
		return self.__l_dbs[idb]

	def add_phrase_text(self, db_name, phrase):
		idb = self.__d_db_names.get(db_name, -1)
		if idb == -1: raise ValueError('add_phrase_text should only be called when the db_name has already been added')
		rphrase = self.__phrase_mgr.add_phrase(phrase)

		self.ext_insert([db_name], rphrase, bdelay=False)

	def remove_phrase_text(self, db_name, phrase, phase_data):
		idb = self.__d_db_names.get(db_name, -1)
		if idb == -1: raise ValueError('remove_phrase_text should only be called when the db_name has already been added')
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		self.remove_phrase([db_name], rphrase)

	def show_dbs(self):
		for kdb_name, vidb in self.__d_db_names.iteritems():
			print('db for', kdb_name)
			for iphrase, rphrase in enumerate( self.__l_dbs[vidb]):
				phrase = self.__phrase_mgr.get_phrase(rphrase)
				print(phrase)
				isrphrase = self.__map_rphrase_to_irphrase.get(rphrase, -1)
				assert isrphrase != -1, 'l_db contains a ref that is not in the isrphrase map'
				assert self.__ll_idb_mrks[vidb][isrphrase], 'l_db contains a ref that idb mrks thinks is false'

	def get_one_db_phrases(self, db_name):
		idb = self.__d_db_names.get(db_name, -1)
		if idb == -1:
			return []
		phrases = []
		for iphrase, rphrase in enumerate( self.__l_dbs[idb]):
			phrases.append(self.__phrase_mgr.get_phrase(rphrase))
		return phrases

	def set_poss_db(self, l_poss_stmts):
		self.__l_poss_stmts = l_poss_stmts

	def get_poss_db(self):
		return self.__l_poss_stmts

	def apply_mods(self, db_name, phrase, rules_mgr):
		insert_phrase, remove_phrase, m_unique_bels = rules_mgr.parse_phrase_for_mod(phrase)
		# for db_name in l_db_names:
		idb = self.__d_db_names.get(db_name, -1)
		if idb == -1:
			idb = self.add_db(db_name)
		if remove_phrase != []:
			nl_remove_phrase = []; m_unique_bnels = []
			for el, bel in zip(remove_phrase, m_unique_bels):
				for nel in el.split():
					nl_remove_phrase.append(nel)
					m_unique_bnels.append(bel)
			for iphrase2, rphrase2 in enumerate( self.__l_dbs[idb]):
				phrase2 = self.__phrase_mgr.get_phrase(rphrase2)
				if len(phrase2) != len(nl_remove_phrase):
					continue
				bfound = True
				for breq, word, rword in zip(m_unique_bnels, phrase2, nl_remove_phrase):
					if breq and word != rword:
						bfound = False
						break
				if bfound:
					# del self.__l_dbs[idb][iphrase2]
					self.remove_phrase([db_name], rphrase2)
					break
		if insert_phrase != []:
			rphrase = self.__phrase_mgr.add_phrase(insert_phrase)
			self.ext_insert([db_name], rphrase, bdelay=True)
			# self.__l_dbs[idb].append((ilen, iphrase))

	def run_rule(self, stmt, phase_data, db_name, l_rule_cats, l_rule_names=[]):
		idb = self.__d_db_names.get(db_name, -1)
		if idb == -1:
			print('Warning. mpdb requested to learn rule on db', db_name, 'which doesnt exist.')
			return None, None
		print('run rule for:', stmt, 'for db:', db_name, 'rule cats:', l_rule_cats, 'and rule name', l_rule_names)
		return self.__rule_mgr.run_rule(self, stmt, phase_data, idb, l_rule_cats, l_rule_names)

	def test_rule(self, stmt, l_results, phase_data, db_name):
		idb = self.__d_db_names.get(db_name, -1)
		if idb == -1:
			print('Warning. mpdb requested to learn rule on db', db_name, 'which doesnt exist.')
			return
		print('learning for:', stmt, 'for db:', db_name)
		self.__rule_mgr.test_rule(self, stmt, l_results, idb)


	def learn_rule(self, stmt, l_results, phase_data, db_name, cat_name):
		idb = self.__d_db_names.get(db_name, -1)
		if idb == -1:
			print('Warning. mpdb requested to learn rule on db', db_name, 'which doesnt exist.')
			return
		print('learning for:', stmt, 'for db:', db_name)
		self.__lrule_mgr.learn_rule(self, stmt, l_results, phase_data, idb, cat_name)
		# rphrase = self.__phrase_mgr.get_rphrase(stmt)
		# # return self.__bdb_story.get_matching_irecs(idb, rphrase)
		# l_rcents = self.__phraseperms.get_cluster(rphrase)
