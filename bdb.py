from __future__ import print_function
import numpy as np
import phraseperms
import nlbitvec
from bitvecdb import bitvecdb
from nlbitvec import c_bitvec_size as bitvec_size
# import cluster
import utils

class cl_phrase_perms_notifier(phraseperms.cl_phrase_perms_notific):
	def __init__(self, client):
		self.__client = client
		phraseperms.cl_phrase_perms_notific.__init__(self)


	def rphrase_perm_added_alert(self, rphrase, rperm):
		self.__client.add_perm(rphrase, rperm)


class cl_nlb_mgr_notifier(nlbitvec.cl_nlb_mgr_notific):
	def __init__(self, client):
		self.__client = client
		nlbitvec.cl_nlb_mgr_notific.__init__(self)


	def iel_bitvec_changed_alert(self, iel, bitvec):
		self.__client.iel_bitvec_changed(iel, bitvec)


class cl_bitvec_db(object):
	def __init__(self, phraseperms_mgr, name):
		self.__hcbdb = None
		self.__name = name
		self.clear_db() # Also initializes
		self.__max_perm_len = -1
		self.__phraseperms = phraseperms_mgr
		self.__el_nlb_mgr = None
		self.__phrase_perms_notifier = cl_phrase_perms_notifier(self)
		self.__phraseperms.register_notific(self.__phrase_perms_notifier)
		self.__nlb_mgr_notifier = cl_nlb_mgr_notifier(self)
		self.__hcbdb = bitvecdb.init_capp()
		bitvecdb.set_el_bitvec_size(self.__hcbdb, bitvec_size)
		bitvecdb.set_name(self.__hcbdb, name)
		# cluster.init_clusters(bitvec_size)

	def set_nlb_mgr(self, el_bitvec_mgr):
		self.__el_nlb_mgr = el_bitvec_mgr
		self.__el_nlb_mgr.register_notific(self.__nlb_mgr_notifier)
		bitvecdb.set_pdbels(self.__hcbdb, self.__el_nlb_mgr.get_hcbdb())

	def clear_db(self):
		self.__d_rphrase_to_iphrase = dict() # type: Dict[int, int]  # map of global ref of phrase to index in local list
		self.__d_rperm_to_iperm = dict() # type: Dict[int, int]  # map of global ref of perm to index in local list
		self.__d_iel_to_l_iperm = dict() # type: Dict[int, Set[int]] # maps iel to each iperm that the iel appears in
		self.__l_phrase_rphrases = [] # type: List[int] # list of phrase global refs, this is indexed to give iphrase
		self.__ll_iperms = [] # type: List[List[int]] # list of local iperm for each entry in l_phrase_rphrases
		self.__l_rperms = [] # type: List[int] # list of perm each a global ref ot a perm from phraseperms
		self.__l_perm_iphrase = [] # type: List[int] # list of local iphrase refs for each perm in l_phrase_perms
		self.__l_perm_len = [] # type: List[int] # list of lengths for each perm in l_phrase_perms
		if self.__hcbdb != None:
			bitvecdb.clear_db(self.__hcbdb)
			self.__phrase_perms_notifier.reset()
			self.__nlb_mgr_notifier.reset()

	def get_max_plen(self):
		return self.__max_perm_len

	def get_db_name(self):
		return self.__name

	def get_hcbdb(self):
		return self.__hcbdb

	def add_new_phrase(self, rphrase):
		iphrase = len(self.__l_phrase_rphrases)
		self.__d_rphrase_to_iphrase[rphrase] = iphrase
		self.__l_phrase_rphrases.append(rphrase)
		self.__ll_iperms.append([])
		l_rperms = self.__phraseperms.get_perms(rphrase)
		for rperm in l_rperms:
			self.add_perm(rphrase, rperm)
		self.__phrase_perms_notifier.notify_on_rphrase(rphrase)

	def del_phrase(self, rphrase):
		iphrase = self.__d_rphrase_to_iphrase.get(rphrase, -1)
		assert iphrase != -1, 'Error request to delete unknown rphrase:' + str(rphrase)
		# Lots to clean up here
		# Remove the record from self.__l_phrase_rphrases
		del self.__l_phrase_rphrases[iphrase]
		# Find all the iperms that this phrase has perms of
		l_iphrase_iperms = sorted(self.__ll_iperms[iphrase])
		# Now you can remove that record too
		del self.__ll_iperms[iphrase]
		# There can be multiple perms for this phrase. Create a dictionary mapping the original indexes of these perms to the new ones
		pip = 0; d_map_iperm_old_to_new = dict()
		for ii in range(len(self.__l_rperms)):
			if pip < len(l_iphrase_iperms) and ii == l_iphrase_iperms[pip]:
				# As we go through each item in the remove list, the correction we need will increase by one
				pip += 1
			else:
				d_map_iperm_old_to_new[ii] = ii - pip
		# Now reverse the remove list, so that the later removals don't mess up the earlier ones
		# and remove the reference in the perm table
		for irp in reversed(l_iphrase_iperms):
			num_els_removed = self.__l_perm_len[irp]
			del self.__l_rperms[irp], self.__l_perm_iphrase[irp], self.__l_perm_len[irp]
			# Inform the c bitvec db that a perm has been removed. It knows nothing of phrases just lists of els as bitvecs instead of eid
			bitvecdb.del_rec(self.__hcbdb, num_els_removed, irp)

		# rebuild the dictionary mapping the external (unremovable) reference to the perm to the index of the perm in the tables here
		self.__d_rperm_to_iperm = dict()
		for iperm, rperm in enumerate(self.__l_rperms):
			self.__d_rperm_to_iperm[rperm] = iperm
		# We have no list of iels locally. We just have a map from iel to the local reference in the ref table. So we have
		# to build the dict anew. We use the old dict and the mapping of old iperm to new iperm created earlier.
		# We must create a new copy of the dict to avoid changing the dict while iterating through it. Then copy in the new version
		d_iel_to_l_iperm = dict()
		for kiel, v_s_iperms in self.__d_iel_to_l_iperm.iteritems():
			s_new_iperms = set()
			for old_iperm in v_s_iperms:
				new_iperm = d_map_iperm_old_to_new.get(old_iperm, -1)
				if new_iperm != -1:
					s_new_iperms.add(new_iperm)
			if s_new_iperms != set():
				d_iel_to_l_iperm[kiel] = s_new_iperms
		self.__d_iel_to_l_iperm = d_iel_to_l_iperm
		# rebuild the dictionary that maps rphrase to iphrase. The information is in the list. The dict is just to make processing efficient
		self.__d_rphrase_to_iphrase = dict()
		for ip, rp in enumerate(self.__l_phrase_rphrases):
			self.__d_rphrase_to_iphrase[rp] = ip


	def add_perm(self, rphrase, rperm):
		iphrase = self.__d_rphrase_to_iphrase.get(rphrase, -1)
		assert iphrase != -1, 'Error. add_perm received for unknown rphrase: ' + str(rphrase)
		iperm = self.__d_rperm_to_iperm.get(rperm, -1)
		if iperm != -1 and iperm in self.__ll_iperms[iphrase]:
			return
		del iperm
		iperm_new = len(self.__l_rperms)
		if rperm in self.__l_rperms:
			print('Error. rperm', rperm, 'passed to cl_bitvec_db already in __l_rperms')
			assert False, 'not dealt with yet'
		self.__l_rperms.append(rperm)
		self.__d_rperm_to_iperm[rperm] = iperm_new
		self.__ll_iperms[iphrase].append(iperm_new)
		self.__l_perm_iphrase.append(iphrase)
		l_perm_eids = self.__phraseperms.get_perm_eids(rperm)
		perm_len = len(l_perm_eids)
		self.__l_perm_len.append(perm_len)
		if perm_len > self.__max_perm_len:
			self.__max_perm_len = perm_len
		phrase_bitvec = []
		for iel in l_perm_eids:
			phrase_bitvec += self.__el_nlb_mgr.get_bin_by_id(iel)
			s_iperms = self.__d_iel_to_l_iperm.get(iel, set())
			s_iperms.add(iperm_new)
			self.__d_iel_to_l_iperm[iel] = s_iperms
			self.__nlb_mgr_notifier.notify_on_iel(iel)
		bitvecdb.add_rec(self.__hcbdb, len(l_perm_eids), utils.convert_charvec_to_arr(phrase_bitvec))

	def agent_add(self, idb):
		num_agents = bitvecdb.add_agent(self.__hcbdb)
		assert idb == (num_agents-1), 'Error! The idb num added does not match the cdb expected value'

	def agent_change_phrase(self, idb, rphrase, badd):
		iphrase = self.__d_rphrase_to_iphrase.get(rphrase, -1)
		assert iphrase != -1, 'Error. add_perm received for unknown rphrase: ' + str(rphrase)
		# get the perms and add them
		for iperm in self.__ll_iperms[iphrase]:
			# rperm = self.__l_rperms[iperm]
			bitvecdb.agent_change_rec(self.__hcbdb, idb, iperm, 1 if badd else 0)

	# def convert_charvec_to_arr(self, bin, size=-1):
	# 	if size==-1:
	# 		size = len(bin)
	# 	bin_arr = bitvecdb.charArray(size)
	# 	for ib in range(size): bin_arr[ib] = chr(bin[ib])
	# 	return bin_arr

	def iel_bitvec_changed(self, iel, bitvec):
		s_iperms = self.__d_iel_to_l_iperm.get(iel, set())
		for iperm in s_iperms:
			rperm = self.__l_rperms[iperm]
			l_perm_eids = self.__phraseperms.get_perm_eids(rperm)
			phrase_bitvec = []
			for iel in l_perm_eids:
				phrase_bitvec += self.__el_nlb_mgr.get_bin_by_id(iel)
			bitvecdb.change_rec(self.__hcbdb, len(l_perm_eids),
								utils.convert_charvec_to_arr(phrase_bitvec), iperm)

		pass

	def get_closest_recs(self, k, phrase_eids, iskip, shrink=0):
		ret_arr, hds_arr, obits_arr = bitvecdb.intArray(k), bitvecdb.intArray(k), bitvecdb.charArray(k*bitvec_size)
		qdata = []
		for iel in phrase_eids:
			qdata += self.__el_nlb_mgr.get_bin_by_id(iel)
		num_ret = bitvecdb.get_closest_recs(self.__hcbdb, k, ret_arr, hds_arr, obits_arr, len(phrase_eids),
											utils.convert_charvec_to_arr(qdata), iskip, shrink)
		l_idexs_ret, l_hds_arr = [ret_arr[ir] for ir in range(num_ret) ], [hds_arr[ir] for ir in range(num_ret) ]
		nd_obits = np.array([ord(obits_arr[ib]) for ib in range(num_ret * bitvec_size)], dtype=np.int8)
		nd_obits = np.reshape(nd_obits, (num_ret, bitvec_size))
		return l_idexs_ret, l_hds_arr, nd_obits

	# def do_clusters(self, ndbits_by_len, l_rule_names, iphrase_by_len, d_rule_grps, max_plen):
	# 	return cluster.cluster(ndbits_by_len, l_rule_names, iphrase_by_len, d_rule_grps,
	# 						   self.__hcbdb, max_plen, self)

	def get_rec_rule_names(self, nd_cent, hd_thresh, plen, num_recs, l_rule_names):
		iperm_arr = bitvecdb.intArray(num_recs)
		cent_arr = utils.convert_charvec_to_arr(nd_cent.tolist())
		hd_arr = utils.convert_intvec_to_arr(hd_thresh)
		num_ret = bitvecdb.get_cluster(self.__hcbdb, iperm_arr, num_recs, cent_arr, plen, hd_arr)
		l_ret = [l_rule_names[self.__l_phrase_rphrases[self.__l_perm_iphrase[iperm_arr[iperm]]]] for iperm in range(num_ret)]
		return l_ret

	def get_matching_irec_pairs(self, idb, rphrase):
		assert False, 'Remove wrapping before use.'
		s_rphrases_close = self.get_matching_rphrases(idb, rphrase)
		s_close_pairs = set()
		for rphrase2 in s_rphrases_close:
			s_rphrases_close2 = self.get_matching_rphrases(idb, rphrase2, [rphrase])
			for rphrase3 in s_rphrases_close2:
				if rphrase3 == rphrase: continue
				p = (rphrase2, rphrase3)
				if p[1] < p[0]: p = (p[1], p[0])
				s_close_pairs.add(p)
		return s_close_pairs


	def get_matching_rphrases(self, idb, rphrase, l_rphrase_excl = []):
		l_rperms = self.__phraseperms.get_perms(rphrase)
		s_eids = set()
		for rperm in l_rperms:
			l_perm_eids = self.__phraseperms.get_perm_eids(rperm)
			for eid in l_perm_eids:
				s_eids.add(eid)
		s_rphrases_close = set()
		for eid in s_eids:
			# print('Story phrases for:', )
			s_rphrases_close |= self.get_irecs_with_eid(idb, eid, rphrase, l_rphrase_excl)
		return s_rphrases_close


	def get_irecs_with_eid(self, idb, eid, rphrase_src, l_rphrase_excl):
		bufsize = len(self.__l_rperms)
		irec_arr = bitvecdb.intArray(bufsize)
		el_bitvec = self.__el_nlb_mgr.get_bin_by_id(eid)
		num_ret = bitvecdb.get_irecs_with_eid(self.__hcbdb, irec_arr, idb, -1,
							utils.convert_charvec_to_arr(el_bitvec, bitvec_size))
		s_rphrases_close = set()
		for iret in range(num_ret):
			rphrase =  self.__l_phrase_rphrases[self.__l_perm_iphrase[irec_arr[iret]]]
			if rphrase in [rphrase_src] + l_rphrase_excl: continue
			# phrase = self.__phraseperms.get_phrase(rphrase)
			# print(phrase)
			s_rphrases_close.add(rphrase)
		return s_rphrases_close

	def print_db(self, hcdbels):
		bitvecdb.print_db_recs(self.__hcbdb, hcdbels)

	def get_rperms_with_eid_at(self, idb, eid, pos, num_cands, cands_arr):
		# bufsize = len(self.__l_rperms)
		irec_arr = bitvecdb.intArray(num_cands)
		el_bitvec = self.__el_nlb_mgr.get_bin_by_id(eid)
		num_ret = bitvecdb.get_irecs_with_eid_by_list(	self.__hcbdb, irec_arr, idb, pos, cands_arr, num_cands,
														utils.convert_charvec_to_arr(el_bitvec, bitvec_size))
		return num_ret, irec_arr

	def get_num_plen(self, plen):
		return bitvecdb.get_num_plen(self.__hcbdb, plen)

	def get_plen_irecs(self, idb, plen):
		bufsize = len(self.__l_rperms)
		irec_arr = bitvecdb.intArray(bufsize)
		num_ret = bitvecdb.get_plen_irecs(self.__hcbdb, irec_arr, plen, idb)
		return num_ret, irec_arr

	def get_close_recs(self, idb, plen, hd_thresh, l_qbits):
		num_ret, len_arr = self.get_plen_irecs(idb, plen)
		ret_arr = bitvecdb.intArray(num_ret)
		num_ret = bitvecdb.get_thresh_recs_by_list(	self.__hcbdb, ret_arr, plen, utils.convert_intvec_to_arr(hd_thresh),
													len_arr, num_ret, utils.convert_charvec_to_arr(l_qbits))
		return num_ret, ret_arr

	def get_el_hd_recs(self, pos, hd, el, num_cands, cands_arr):
		irec_arr = bitvecdb.intArray(num_cands)
		# el_bitvec = self.__el_bitvec_mgr.get_bin_by_id(eid).tolist()
		el_bitvec = self.__el_nlb_mgr.get_el_bin(el)
		num_ret = bitvecdb.get_el_hd_recs_by_list(	self.__hcbdb, irec_arr, cands_arr, num_cands, pos, hd,
													utils.convert_charvec_to_arr(el_bitvec))
		return num_ret, irec_arr

	def init_db_for_cluster(self, cluster_min):
		l_buckets = [0, bitvec_size / 5, 2 * bitvec_size / 5, bitvec_size]
		buckets_arr = bitvecdb.intArray(len(l_buckets))
		for ib, bhd in enumerate(l_buckets): buckets_arr[ib] = bhd
		bitvecdb.set_hd_buckets(self.get_hcbdb(), len(l_buckets), buckets_arr)
		bitvecdb.set_cluster_min(self.get_hcbdb(), cluster_min)

	def get_cluster_seed(self, cent_ret, hd_avg_ret, hd_thresh, plen, recc_thresh):
		num_left_now = bitvecdb.get_cluster_seed(self.__hcbdb, cent_ret, hd_avg_ret, hd_thresh, plen, recc_thresh)
		return num_left_now

	def init_num_left_buf(self, plen):
		num_left = bitvecdb.init_num_left_buf(self.__hcbdb, plen)
		return num_left

	def get_rperm_from_iperm(self, iperm):
		# iperm is the local index to the perm. It is also the record number in the cdb for the bdb
		return self.__l_rperms[iperm]