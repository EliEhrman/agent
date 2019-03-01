from __future__ import print_function
import random
import sys
import math
import csv
import os
from os.path import expanduser
from shutil import copyfile
import numpy as np
import collections
from bitvecdb import bitvecdb
import utils


# c_num_seeds_initial = 5
# c_cluster_thresh = 10 # 18
c_cluster_min = 10 # minimum number of recs in cluster
c_cluster_thresh_min = 1 # 0.1
c_cluster_thresh_max = 4 # 0.2  # 2 / 5
# 6, self.__bitvec_size * 1 / 5

# __bitvec_size = 0

nt_cluster = collections.namedtuple('nt_cluster', 'l_cent, hd, score, num_hit')

class cl_phrase_cluster_mgr(object):
	def __init__(self, cluster_fnt, rule_grp_fnt):
		self.__bitvec_size = -1
		self.__cluster_fnt = cluster_fnt
		self.__rule_grp_fnt = rule_grp_fnt
		self.__d_rule_grps = dict()
		self.__bdb_all = None
		self.__l_nd_centroids = [] # list of np arrays, one for each len
		self.__ll_centroids = [] # list of centroids, each centroid a list of different length
		self.__ll_cent_hd_thresh = []
		self.__l_cent_hd = [] # list of hds, one for each in __ll_centroids. Note! Now list per centroid. Length of list == plen
		self.__hcdb_cent = bitvecdb.init_capp()
		self.__nlb_mgr = None
		bitvecdb.set_name(self.__hcdb_cent, 'centroids')
		bitvecdb.set_b_hd_thresh(self.__hcdb_cent)

	def set_bdb_all(self, bdb_all):
		self.__bdb_all = bdb_all
		self.__bdb_all.init_db_for_cluster(c_cluster_min)

	def set_nlb_mgr(self, nlb_mgr):
		self.__bitvec_size = nlb_mgr.get_bitvec_size()
		self.__nlb_mgr = nlb_mgr
		bitvecdb.set_el_bitvec_size(self.__hcdb_cent, self.__bitvec_size)

	def load_rule_grps(self):
		fn = self.__rule_grp_fnt
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				for irow, row in enumerate(csvr):
					for rname in row:
						self.__d_rule_grps[rname] = irow

		except IOError:
			print('Cannot open or read ', fn)


	def init(self, l_rule_names):
		self.load_rule_grps()
		score = self.cluster(l_rule_names,  self.__bdb_all.get_max_plen())
		self.save_clusters()

	def get_centroid(self, rcluster):
		return self.__ll_centroids[rcluster]

	def get_cent_hd(self, rcluster):
		return self.__l_cent_hd[rcluster]

	def get_cent_len(self, rcluster):
		return len(self.__ll_centroids[rcluster])

	def get_cluster_words(self, rcluster):
		close_phrase = []
		l_centroid = self.__ll_centroids[rcluster]
		plen = len(l_centroid) / self.__bitvec_size
		for iel in range(plen):
			word = self.__nlb_mgr.dbg_closest_word(
				l_centroid[iel * self.__bitvec_size:(iel + 1) * self.__bitvec_size])
			close_phrase.append(word)
		return close_phrase

	def print_cluster(self, rcluster):
		close_phrase = self.get_cluster_words(rcluster)
		print('centroid:', rcluster, close_phrase)

	def process_clusters(self):
		print('Cluster closest els:')
		for plen, l_cent_hd_thresh in reversed(list(enumerate(self.__ll_cent_hd_thresh))):
			for i_lencent, hd_thresh in enumerate(l_cent_hd_thresh):
				irec = len(self.__ll_centroids)
				close_phrase = []
				for iel in range(plen):
					# print('iel', iel, 'plen:', plen, 'i_lencent', i_lencent, 'len', len(self.__l_nd_centroids[plen][i_lencent])) # , 'bits:', self.__l_nd_centroids[plen][i_lencent])
					word = self.__nlb_mgr.dbg_closest_word(self.__l_nd_centroids[plen][i_lencent][iel*self.__bitvec_size:(iel+1)*self.__bitvec_size])
					close_phrase.append(word)
					# print(close_phrase)
				print('rcent:', irec, 'plen:', plen, ', hd:', hd_thresh, ',', close_phrase)
				self.__ll_centroids.append(np.reshape(self.__l_nd_centroids[plen][i_lencent], -1).tolist())
				self.__l_cent_hd.append(hd_thresh)
				bitvecdb.add_rec(self.__hcdb_cent, plen,
								 utils.convert_charvec_to_arr(self.__ll_centroids[-1]))
				hd_arr = utils.convert_intvec_to_arr(hd_thresh)
				bitvecdb.set_hd_thresh(self.__hcdb_cent, irec, hd_arr, len(hd_thresh))

	def init_from_load(self):
		self.load_clusters()
		self.process_clusters()

	def cluster_one_thresh(self, plen, recc_thresh):
		num_left = self.__bdb_all.init_num_left_buf(plen)
		cent_ret = bitvecdb.charArray(self.__bitvec_size*plen)
		hd_avg_ret, hd_thresh = bitvecdb.floatArray(1), bitvecdb.intArray(plen)
		l_clusters = []
		while num_left >= c_cluster_min:
			num_left_now = self.__bdb_all.get_cluster_seed(cent_ret, hd_avg_ret, hd_thresh, plen, recc_thresh)
			num_added = num_left - num_left_now
			print('py: cluster_one_thresh num_added is', num_added)
			num_left = num_left_now
			if num_added == 0: break
			l_cent = [ord(cent_ret[ib]) for ib in range(self.__bitvec_size*plen)]
			l_clusters.append(nt_cluster(l_cent=l_cent, hd=[hd_thresh[iel] for iel in range(plen)],
										 score=hd_avg_ret[0], num_hit=num_added))
		nd_hd_cluster, nd_num = np.zeros(len(l_clusters)), np.zeros(len(l_clusters))
		nd_centroids = np.zeros((len(l_clusters), self.__bitvec_size*plen), dtype=np.uint8)
		l_hd_thresh = []
		for icluster, cluster in enumerate(l_clusters):
			nd_hd_cluster[icluster] = cluster.score
			nd_num[icluster] = cluster.num_hit
			nd_centroids[icluster, :] = np.array(cluster.l_cent, dtype=np.uint8)
			l_hd_thresh.append(cluster.hd)
			# l_homog_score.append(hd_cluster)
		if (l_clusters == [] or np.sum(nd_num) == 0):
			final_score = 1000.0
		else:
			score = np.sum(np.multiply(nd_hd_cluster, nd_num)) / np.sum(nd_num)
			final_score = (nd_hd_cluster.shape[0] * score) + (num_left * 0.2) # think about the magic number and put it into a constant
		return final_score, nd_centroids, l_hd_thresh

	def assign_rule_name_score(self, plen, nd_centroids, l_cent_hd_thresh, l_rule_names,
							   num_recs):
		l_entr, l_tot_hits = [], []
		for ii1, nd_cent in enumerate(nd_centroids):
			l_rec_rule_names = self.__bdb_all.get_rec_rule_names(nd_cent, l_cent_hd_thresh[ii1], plen, num_recs, l_rule_names)
			tot_hits = len(l_rec_rule_names)
			d_cluster_rules, l_num_hits, l_hit_names = dict(), [], []
			for irec, rule_names in enumerate(l_rec_rule_names):
				s_grp_ids = set()
				for rule_name in rule_names:
					rule_grp_id = self.__d_rule_grps.get(rule_name, -1)
					if rule_grp_id != -1:
						s_grp_ids.add(rule_grp_id)
				if len(s_grp_ids) != 1:
					continue
				rule_grp_id = s_grp_ids.pop()
				# assert rule_grp_id != -1, 'Error. Rule name not in a rule group'
				irule = d_cluster_rules.get(rule_grp_id, -1)
				if irule == -1:
					d_cluster_rules[rule_grp_id] = len(l_num_hits)
					l_num_hits.append(1)
					l_hit_names.append([rule_names])
				else:
					l_num_hits[irule] += 1
					l_hit_names[irule].append(rule_names)
			entr = 0.
			for irule, num_hits in enumerate(l_num_hits):
				p = float(num_hits) / tot_hits
				entr += -p * math.log(p, 2)
			l_entr.append(entr)
			l_tot_hits.append(tot_hits)
		entr_tot, tot_tot_hits = 0., 0
		for entr, tot_hits in zip(l_entr, l_tot_hits):
			entr_tot += entr * tot_hits;
			tot_tot_hits += tot_hits
		return 0 if tot_tot_hits == 0 else entr_tot / tot_tot_hits , tot_tot_hits

	def cluster(self, l_rule_names, max_plen):
		print('Cluster: print db recs.')
		self.__bdb_all.print_db(self.__nlb_mgr.get_hcbdb())
		entr_tot, tot_hits, tot_clusters = 0., 0, 0
		self.__l_nd_centroids, self.__ll_cent_hd_thresh = [[] for _ in range(max_plen)], [[] for _ in range(max_plen)]
		for plen in range(max_plen):
			# print('cluster at plen', plen)
			# if plen != 4: continue
			num_plen_recs = self.__bdb_all.get_num_plen(plen)
			print('cluster: Num recs for plen', plen, 'is', num_plen_recs)
			if num_plen_recs <= 0: continue
			best_thresh, best_homog_score = -1, sys.float_info.max
			# for recc_thresh in range(6, self.__bitvec_size * 1 / 5): # * 2 / 5
			# for recc_thresh in range(c_cluster_thresh_min, c_cluster_thresh_max):
			for recc_thresh in range(int(c_cluster_thresh_min * plen), int(c_cluster_thresh_max * plen)): # Note. This version has not been checked
				homog_score, nd_centroids_t, l_cent_hd_thresh_t = self.cluster_one_thresh(plen, recc_thresh)
				print('cluster: homog_score', homog_score, 'recc_thresh', recc_thresh, 'num cents', len(l_cent_hd_thresh_t), 'thresh:', l_cent_hd_thresh_t)
				if homog_score < best_homog_score:
					best_homog_score = homog_score
					best_thresh, nd_centroids, l_cent_hd_thresh = recc_thresh, nd_centroids_t, l_cent_hd_thresh_t
				else:
					if len(l_cent_hd_thresh_t) > 0:
						break # Don't keep testing for higher recc_thresh if score is the same. Note. As long as there are SOME cents
					# break
			if best_thresh == -1: continue
			print('best_thresh for plen', plen, 'is', best_thresh)
			assert nd_centroids.shape[1] == plen * self.__bitvec_size, 'bad length'
			self.__l_nd_centroids[plen] = nd_centroids; self.__ll_cent_hd_thresh[plen] = l_cent_hd_thresh
			# print('uncomment')
			entr_score,plen_hits= self.assign_rule_name_score(plen, nd_centroids, l_cent_hd_thresh, l_rule_names,
														 num_plen_recs)
			entr_tot += entr_score*plen_hits; tot_hits += plen_hits; tot_clusters += nd_centroids.shape[0]
			# if plen > 9:
			# 	exit()

		# The entropy score is just entr_tot / tot_hits, but I want to penalize for having too many clusters
		score = tot_clusters * (0.1 + entr_tot / (tot_hits+0.001))
		print('Score:', score)
		# print('uncomment')
		self.process_clusters()
		return score


	def save_clusters(self):
		num_cents = 0
		for ilen, l_hds in enumerate(self.__ll_cent_hd_thresh):
			num_cents += len(l_hds)

		fn = expanduser(self.__cluster_fnt)

		if os.path.isfile(fn):
			copyfile(fn, fn + '.bak')
		fh = open(fn, 'wb')
		csvw = csv.writer(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
		csvw.writerow(['blbitvec centroids', 'Version', '1'])
		csvw.writerow(['Num Cents:', num_cents, 'num lengths', len(self.__ll_cent_hd_thresh)])
		for ilen, l_hds in enumerate(self.__ll_cent_hd_thresh):
			for icent, hd in enumerate(l_hds):
				cent = self.__l_nd_centroids[ilen][icent, :]
				lbits = cent.tolist() # [onebit for l in cent.tolist() for onebit in l]
				csvw.writerow([ilen] + hd + lbits)

		fh.close()

	def load_clusters(self):
		fn = expanduser(self.__cluster_fnt)
		# if True:
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				_, snum_cents, _, snum_lens = next(csvr)
				ll_centroids, self.__ll_cent_hd_thresh = [[] for _ in range(int(snum_lens))], [[] for _ in range(int(snum_lens))]
				for irow in range(int(snum_cents)):
					row = next(csvr)
					# ilen, hd, lsbits = int(row[0]), int(row[1]), row[2:]
					ilen = int(row[0])
					hd = map(int, row[1:ilen+1])
					# bitvals = np.reshape(np.array(map(int, lsbits), dtype=np.int8), (ilen, self.__bitvec_size))
					bitvals = np.array(map(int, row[ilen+1:]), dtype=np.int8)
					self.__ll_cent_hd_thresh[ilen].append(hd)
					ll_centroids[ilen].append(bitvals)
					del row, ilen, hd #, lsbits
				self.__l_nd_centroids = []
				for ilen, l_cents in enumerate(ll_centroids):
					if l_cents == []:
						self.__l_nd_centroids.append([])
					else:
						self.__l_nd_centroids.append(np.stack(l_cents, axis=0))

		except IOError:
			raise ValueError('Cannot open or read ', fn)

		# return l_nd_centroids, ll_cent_hd_thresh

	# def convert_charvec_to_arr(self, bin, size=-1):
	# 	size = len(bin)
	# 	bin_arr = bitvecdb.charArray(size)
	# 	for ib in range(size): bin_arr[ib] = chr(bin[ib])
	# 	return bin_arr
	#

	def get_cluster(self, l_phrase_bits):
		plen = len(l_phrase_bits) / self.__bitvec_size
		# Each cent is an array of el bitvecs, each cent is also an array of hd, one for each el
		num_recs = len(self.__l_cent_hd)
		ret_arr = bitvecdb.intArray(num_recs)
		null_arr = bitvecdb.intArray(0)
		num_ret = bitvecdb.get_thresh_recs(	self.__hcdb_cent, ret_arr, plen, null_arr,
											utils.convert_charvec_to_arr(l_phrase_bits), False, True)
		l_rcents = [ret_arr[i] for i in range(num_ret)]
		return l_rcents





