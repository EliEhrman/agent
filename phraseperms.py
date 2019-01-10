from __future__ import print_function

class cl_phrase_perms_notific(object):
	def __init__(self):
		self.__d_rphrases = dict()

	def notify_on_rphrase(self, rphrase):
		self.__d_rphrases[rphrase] = True

	def rphrase_perm_added(self, rphrase, rperm):
		balert = self.__d_rphrases.get(rphrase, False)
		if not balert: return
		self.rphrase_perm_added_alert(rphrase, rperm)

	def rphrase_perm_added_alert(self, rphrase, rperm):
		print('Error. This should not be called')

	def reset(self):
		self.__d_rphrases = dict()


class cl_phrase_perms(object):
	def __init__(self, phrase_mgr):
		# iphrase is the local index for the rphrase. It should be the same as rphrase, bit not assuming this for now
		self.__d_rphrase_to_iphrase = dict()
		self.__l_phrase_rphrases = []
		self.__ll_rperms = [] # type: List[List[int]] # list of rperm for each entry in l_phrase_rphrases
		self.__l_phrase_perms = [] # type: List[List[int]] # list of perms, each a list of el ids from nlbitvec
		self.__l_notifics = [] # type: List[cl_phrase_perms_notific]
		self.__el_bitvec_mgr = None
		self.__cluster_mgr = None
		self.__phrase_mgr = phrase_mgr

	def set_nlb_mgr(self, el_bitvec_mgr):
		self.__el_bitvec_mgr = el_bitvec_mgr

	def get_nlb_mgr(self):
		return self.__el_bitvec_mgr

	def get_bdb_all_hcdb(self): # A functionm giving direct access to the c db handle of the bdb_all. Access through the el_bitvec mgr but it is a peer to that mgr
		return self.__el_bitvec_mgr.get_bdb_all_hcdb()

	def set_cluster_mgr(self, cluster_mgr):
		self.__cluster_mgr = cluster_mgr

	def get_cluster_mgr(self):
		return self.__cluster_mgr

	def add_new_phrase(self, rphrase):
		iphrase = len(self.__l_phrase_rphrases)
		self.__d_rphrase_to_iphrase[rphrase] = iphrase
		self.__l_phrase_rphrases.append(rphrase)
		# rperm = len(self.__l_phrase_perms)
		self.__ll_rperms.append([])
		# self.__l_phrase_perms.append(l_phrase_eids)
		self.__el_bitvec_mgr.new_phrase_from_phrase_mgr(rphrase)

	def add_perm(self, rphrase, l_phrase_eids):
		iphrase = self.__d_rphrase_to_iphrase[rphrase]
		for rperm in self.__ll_rperms[iphrase]:
			if l_phrase_eids == self.__l_phrase_perms[rperm]:
				return
		rperm_new = len(self.__l_phrase_perms)
		self.__ll_rperms[iphrase].append(rperm_new)
		self.__l_phrase_perms.append(l_phrase_eids)
		for notific in self.__l_notifics:
			notific.rphrase_perm_added(rphrase, rperm_new)

	def get_perms(self, rphrase):
		iphrase = self.__d_rphrase_to_iphrase.get(rphrase, -1)
		if iphrase == -1:
			print('Warning. phraseperms received request for perms for unknown rphrase', rphrase)
			return []
		return self.__ll_rperms[iphrase]

	def get_perm_eids(self, rperm):
		if rperm >= len(self.__l_phrase_perms):
			print('Warning phraseperms received request for eids for unknown rperm', rperm)
			return []
		return self.__l_phrase_perms[rperm]

	def register_notific(self, notific):
		self.__l_notifics.append(notific)

	def get_phrase(self, rphrase):
		return self.__phrase_mgr.get_phrase(rphrase)

	def init(self, l_rule_names):
		if self.__cluster_mgr == None:
			print('Error!. Cluster mgr not set yet for phraseperms')
			return
		self.__cluster_mgr.init(l_rule_names)
		# self.test_clusters()
		self.__el_bitvec_mgr.save_word_db()

	def init_from_load(self):
		if self.__cluster_mgr == None:
			print('Error!. Cluster mgr not set yet for phraseperms')
			return
		self.__cluster_mgr.init_from_load()

	def get_cluster(self, rphrase):
		# print('get_cluster_called for', self.__phrase_mgr.get_phrase(rphrase))
		l_rperms = self.get_perms(rphrase)
		l_rcent = []
		for rperm in l_rperms:
			l_perm_eids = self.get_perm_eids(rperm)
			l_phrase_bits = []
			for eid in l_perm_eids:
				l_phrase_bits += self.__el_bitvec_mgr.get_bin_by_id(eid).tolist()
			l_rcent += self.__cluster_mgr.get_cluster(l_phrase_bits)
		return l_rcent

	def get_cent_len(self, rcent):
		return self.__cluster_mgr.get_cent_len(rcent)

	def get_cent_hd(self, rcent):
		return self.__cluster_mgr.get_cent_hd(rcent)

	def get_centroid(self, rcent):
		return self.__cluster_mgr.get_centroid(rcent)

	def test_clusters(self):
		tot = self.__phrase_mgr.get_num_phrases()
		for i in range(tot):
			self.get_cluster(i)

	def print_cluster(self, rcent):
		if rcent < 0: return
		self.__cluster_mgr.print_cluster(rcent)


