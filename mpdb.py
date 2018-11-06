"""
mp stands for multi-player
Ths module provides support for multiple databases - often partial copies of each other
TYpically each player will have his own database representing his/her knowledge
Also, monte-carlo or tree-based search might use the db

"""

from __future__ import print_function
import numpy as np
# import copy
import warnings
from varopts import varopts


class cl_mpdb_mgr(object):
	def __init__(self, bitvec_mgr, rule_mgr, len_set_names):
		self.__l_dbs = []
		self.__l_d_story_len_refs = []
		self.__d_dn_names = dict()
		self.__bitvec_mgr = bitvec_mgr
		self.__rules_mgr = rule_mgr
		self.__l_delayed_inserts = []
		self.__map_rphrase_to_isrphrase = dict() # maps global ref to phrase (len and iphrase) of bitvec to idx of phrase in l_sphrase
		self.__l_srphrases = [] # list of global rphrase
		self.__ll_idb_mrks = [] # for each idb, list of bools for whether the phrase (indexed on l_srphrases) is in that idb
		rule_mgr.add_to_bitvec_mgr(bitvec_mgr)
		bitvec_mgr.set_mpdb_mgr(self)
		self.__len_set_names = len_set_names
		self.__chmpdb = varopts.mpdb_init(self.__bitvec_mgr.get_hcvo(), self.__len_set_names)
		# self.add_db('main')
		self.__l_poss_stmts = []
		pass

	def get_bitvec_mgr(self):
		return self.__bitvec_mgr

	def clear_dbs(self):
		self.__bitvec_mgr.clear_mpdb_bins()
		varopts.mpdb_clear(self.__chmpdb)
		self.__chmpdb = varopts.mpdb_init(self.__bitvec_mgr.get_hcvo(), self.__len_set_names)
		self.__l_dbs = []
		self.__l_d_story_len_refs = []
		self.__d_dn_names = dict()
		self.__l_delayed_inserts = []
		self.__map_rphrase_to_isrphrase = dict()
		self.__l_srphrases = []
		self.__ll_idb_mrks = []
		self.add_db('main')
		self.__l_poss_stmts = []

	def add_db(self, db_name):
		idb = len(self.__l_dbs)
		self.__l_dbs.append([])
		self.__l_d_story_len_refs.append(dict())
		self.__d_dn_names[db_name] = idb
		if idb == 0:
			self.__ll_idb_mrks.append([])
		else:
			self.__ll_idb_mrks.append([False for _ in self.__ll_idb_mrks[0]])
		varopts.mpdb_add_db(self.__chmpdb, db_name, idb)

		return idb

	def get_chmpdb(self):
		return self.__chmpdb

	def set_poss_db(self, l_poss_stmts):
		self.__l_poss_stmts = l_poss_stmts

	def get_poss_db(self):
		return self.__l_poss_stmts

	def get_story_refs(self, db_name, stg_ilen):
		idb = self.__d_dn_names.get(db_name, -1)
		if idb == -1:
			return []
		return self.__l_d_story_len_refs[idb].get(stg_ilen, [])

	def insert(self, l_db_names, phrase_ref, bdelay=False):
		for db_name in l_db_names:
			idb = self.__d_dn_names.get(db_name, -1)
			if idb == -1:
				# print('Error. mpdb requested to insert into', db_name, 'which doesnt exist.')
				# continue
				idb = self.add_db(db_name)
			if bdelay:
				if [idb, phrase_ref] in self.__l_delayed_inserts:
					# warnings.warn('Double insertion into delayed inserts')
					pass
				else:
					self.__l_delayed_inserts.append([idb, phrase_ref])
			else:
				self.do_base_insert(idb, phrase_ref)
			# ilen, iphrase = phrase_ref
			# self.__l_dbs[idb].append(phrase_ref)
			# d_len_refs = self.__l_d_story_len_refs[idb]
			# len_refs = d_len_refs.get(ilen, [])
			# len_refs.append(iphrase)
			# d_len_refs[ilen] = len_refs

		pass

	def do_base_insert(self, idb, phrase_ref):
		ilen, iphrase = phrase_ref
		self.__l_dbs[idb].append(phrase_ref)
		d_len_refs = self.__l_d_story_len_refs[idb]
		len_refs = d_len_refs.get(ilen, [])
		len_refs.append(iphrase)
		d_len_refs[ilen] = len_refs
		isrphrase = self.__map_rphrase_to_isrphrase.get(phrase_ref, -1)
		if isrphrase == -1:
			# if ilen >= len(self.__ll_sphrases):
			# 	self.__ll_sphrases += [[] for _ in range(len(self.__ll_sphrases), ilen+1)]
			isrphrase = len(self.__l_srphrases)
			self.__map_rphrase_to_isrphrase[phrase_ref] = isrphrase
			self.__l_srphrases.append(phrase_ref)
			varopts.mpdb_add_srphrase(self.__chmpdb, ilen, iphrase)
			for idb_mrk in self.__ll_idb_mrks:
				idb_mrk.append(False)
			self.__bitvec_mgr.add_mpdb_bins(*phrase_ref)
		if self.__ll_idb_mrks[idb][isrphrase]:
			warnings.warn('Warning! Attempting to add a phrase twice')
			db_name = self.get_db_name_from_idb(idb)
			print('not adding duplicate', self.__bitvec_mgr.get_phrase(*phrase_ref), 'to db', db_name)
			del self.__l_dbs[idb][-1]
			d_len_refs = self.__l_d_story_len_refs[idb]
			len_refs = d_len_refs[ilen]
			del len_refs[-1]
			d_len_refs[ilen] = len_refs
		self.__ll_idb_mrks[idb][isrphrase] = True
		varopts.mpdb_set_idb_mrk(self.__chmpdb, idb, isrphrase, chr(1))


	def cleanup_srphrases(self):
		num_srphrases_orig = len(self.__l_srphrases)
		l_idxs = range(num_srphrases_orig)
		for isrphrase in reversed(xrange(num_srphrases_orig)):
			binuse = False
			for idb_mrks in self.__ll_idb_mrks:
				if idb_mrks[isrphrase]:
					binuse = True
					break
			if not binuse:
				del self.__map_rphrase_to_isrphrase[self.__l_srphrases[isrphrase]]
				del l_idxs[isrphrase], self.__l_srphrases[isrphrase]
				varopts.mpdb_del_srphrase(self.__chmpdb, isrphrase)
				for idb_mrks in self.__ll_idb_mrks:
					del idb_mrks[isrphrase]

		d_rev_idx = {idx:iidx for iidx, idx in enumerate(l_idxs)}
		for krphrase in self.__map_rphrase_to_isrphrase:
			iorig = self.__map_rphrase_to_isrphrase[krphrase]
			self.__map_rphrase_to_isrphrase[krphrase] = d_rev_idx[iorig]

		self.__bitvec_mgr.cleanup_mpdb_bins(l_idxs)

	def apply_bin_db_changes(self, l_rphrase_changes):
		for rphrase in l_rphrase_changes:
			isrphrase = self.__map_rphrase_to_isrphrase.get(rphrase, -1)
			if isrphrase != -1: self.__bitvec_mgr.update_mpdb_bins(isrphrase, rphrase)

	def apply_delayed_inserts(self):
		for delayed_insert in self.__l_delayed_inserts:
			self.do_base_insert(*delayed_insert)
		self.__l_delayed_inserts = []

	def get_rphrases(self):
		return self.__l_srphrases

	def get_nd_idb_mrk(self, idb):
		l_idb_mrks = self.__ll_idb_mrks[idb]
		return np.array(l_idb_mrks, dtype=np.bool)

	def remove_phrase(self,  l_db_names, phrase_ref):
		isrphrase = self.__map_rphrase_to_isrphrase.get(phrase_ref, -1)
		if isrphrase == -1:
			print('Error. mpdb requested to remove item', phrase_ref, 'that does not exist in any of the dbs.')
			return
		for db_name in l_db_names:
			idb = self.__d_dn_names.get(db_name, -1)
			if idb == -1:
				print('Error. mpdb requested to remove from', db_name, 'which doesnt exist.')
				continue
			if phrase_ref not in self.__l_dbs[idb]:
				print('Error. mpdb requested to remove item', phrase_ref, 'from db', db_name, '.Item not found.')
				continue
			# self.__l_dbs[idb].remove(phrase_ref)
			self.__l_dbs[idb] = filter(lambda a: a != phrase_ref, self.__l_dbs[idb])
			ilen, iphrase = phrase_ref
			d_len_refs = self.__l_d_story_len_refs[idb]
			len_refs = d_len_refs[ilen]
			len_refs.remove(iphrase)
			self.__ll_idb_mrks[idb][isrphrase] = False
			varopts.mpdb_set_idb_mrk(self.__chmpdb, idb, isrphrase, chr(0))

	def infer(self, l_db_names_from, phase_data, l_rule_cats):
		results = []
		for db_name in l_db_names_from:
			idb = self.__d_dn_names.get(db_name, -1)
			if idb == -1:
				print('Error. mpdb requested to infer from', db_name, 'which doesnt exist.')
				continue
			for ilen, iphrase in list(self.__l_dbs[idb]):
				# story_refs = list(self.__l_dbs[idb])
				# story_refs.remove((ilen, iphrase))
				self.remove_phrase([db_name], (ilen, iphrase))
				phrase = self.__bitvec_mgr.get_phrase(ilen, iphrase)
				pot_results = self.__bitvec_mgr.apply_rule(	phrase, ilen, iphrase, idb, l_rule_cats)
				if pot_results != []:
					results += pot_results
				self.insert([db_name], (ilen, iphrase))

		return results

	def get_idb_from_db_name(self, db_name):
		return self.__d_dn_names.get(db_name, -1)

	def get_srphrases_text(self):
		return [self.__bitvec_mgr.get_phrase(*rphrase) for rphrase in self.__l_srphrases]

	def get_db_name_from_idb(self, idb):
		print('Warning. get_db_name_from_idb is a slow function. NOt intended for production')
		for kname, vidb in self.__d_dn_names.iteritems():
			if vidb == idb:
				return kname
		return 'Name not found'

	def run_rule(self, stmt, phase_data, db_name, l_rule_cats, l_rule_names=[], l_result_rule_names=[]):
		idb = self.__d_dn_names.get(db_name, -1)
		if idb == -1:
			print('Error. mpdb requested to run rule on db', db_name, 'which doesnt exist.')
			return None
		results = self.__bitvec_mgr.run_rule(	stmt, phase_data, idb, l_rule_cats, l_rule_names, l_result_rule_names)
		return [db_name for _ in results], results

	def get_idb_rphrases(self, idb):
		return self.__l_dbs[idb]

	def get_d_story_len_refs(self, idb):
		assert False, 'Intending to delete'
		return self.__l_d_story_len_refs[idb]

	def learn_rule(self, stmt, l_results, phase_data, db_name):
		idb = self.__d_dn_names.get(db_name, -1)
		if idb == -1:
			print('Warning. mpdb requested to learn rule on db', db_name, 'which doesnt exist.')
			return
		return self.__bitvec_mgr.learn_rule(stmt, l_results, phase_data, idb)

	def add_phrase_text(self, db_name, phrase, phase_data):
		idb = self.__d_dn_names.get(db_name, -1)
		if idb == -1: raise ValueError('add_phrase should only be called when the db_name has already been added')
		ilen, iphrase = self.__bitvec_mgr.add_phrase(phrase, phase_data)
		self.insert([db_name], (ilen, iphrase), bdelay=False)

	def remove_phrase_text(self, db_name, phrase, phase_data):
		idb = self.__d_dn_names.get(db_name, -1)
		if idb == -1: raise ValueError('add_phrase should only be called when the db_name has already been added')
		ilen, iphrase = self.__bitvec_mgr.add_phrase(phrase, phase_data)
		self.remove_phrase([db_name], (ilen, iphrase))

	def apply_mods(self, db_name, phrase, phase_data):
		insert_phrase, remove_phrase, m_unique_bels = self.__rules_mgr.parse_phrase_for_mod(phrase)
		# for db_name in l_db_names:
		idb = self.__d_dn_names.get(db_name, -1)
		if idb == -1:
			idb = self.add_db(db_name)
		if remove_phrase != []:
			for iphrase2, phrase2_ref in enumerate( self.__l_dbs[idb]):
				phrase2 = self.__bitvec_mgr.get_phrase(*phrase2_ref)
				if len(phrase2) != len(remove_phrase):
					continue
				bfound = True
				for breq, word, rword in zip(m_unique_bels, phrase2, remove_phrase):
					if breq and word != rword:
						bfound = False
						break
				if bfound:
					# del self.__l_dbs[idb][iphrase2]
					self.remove_phrase([db_name], phrase2_ref)
					break
		if insert_phrase != []:
			ilen, iphrase = self.__bitvec_mgr.add_phrase(insert_phrase, phase_data)
			self.insert([db_name], (ilen, iphrase), bdelay=True)
			# self.__l_dbs[idb].append((ilen, iphrase))

	def show_dbs(self):
		for kdb_name, vidb in self.__d_dn_names.iteritems():
			print('db for', kdb_name)
			for iphrase, phrase_ref in enumerate( self.__l_dbs[vidb]):
				phrase = self.__bitvec_mgr.get_phrase(*phrase_ref)
				print(phrase)
				isrphrase = self.__map_rphrase_to_isrphrase.get(phrase_ref, -1)
				assert isrphrase != -1, 'l_db contains a ref that is not in the isrphrase map'
				assert self.__ll_idb_mrks[vidb][isrphrase], 'l_db contains a ref that idb mrks thinks is false'

	def get_one_db_phrases(self, db_name):
		idb = self.__d_dn_names.get(db_name, -1)
		if idb == -1:
			return []
		phrases = []
		for iphrase, phrase_ref in enumerate( self.__l_dbs[idb]):
			phrases.append(self.__bitvec_mgr.get_phrase(*phrase_ref))
		return phrases


	def extract_mod_db(self, l_dbs_to_mod, events_to_queue):
		for ievq, one_event_to_q in enumerate(events_to_queue):
			db_name = self.__rules_mgr.parse_phrase_for_mod_db(one_event_to_q)
			if db_name != None: l_dbs_to_mod[ievq] = db_name





