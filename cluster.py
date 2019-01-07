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


c_num_seeds_initial = 5
c_cluster_thresh = 10 # 18

# __bitvec_size = 0

nt_cluster = collections.namedtuple('nt_cluster', 'l_cent, hd, score, num_hit')

class cl_phrase_cluster_mgr(object):
	def __init__(self, cluster_fnt, rule_grp_fnt):
		self.__bitvec_size = -1
		self.__cluster_fnt = cluster_fnt
		self.__rule_grp_fnt = rule_grp_fnt
		self.__d_rule_grps = dict()
		self.__bdb_all = None
		self.__l_nd_centroids = []
		self.__ll_centroids = []
		self.__ll_cent_hd_thresh = []
		self.__l_cent_hd = []
		self.__hcdb_cent = bitvecdb.init_capp()
		self.__nlb_mgr = None
		bitvecdb.set_name(self.__hcdb_cent, 'centroids')
		bitvecdb.set_b_hd_thresh(self.__hcdb_cent)

	def set_bdb_all(self, bdb_all):
		self.__bdb_all = bdb_all

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
		# return l_nd_centroids, ll_cent_hd_thresh

	def get_centroid(self, rcluster):
		return self.__ll_centroids[rcluster]

	def get_cent_hd(self, rcluster):
		return self.__l_cent_hd[rcluster]

	def print_cluster(self, rcluster):
		close_phrase = []
		l_centroid = self.__ll_centroids[rcluster]
		plen = len(l_centroid)/self.__bitvec_size

		for iel in range(plen):
			word = self.__nlb_mgr.dbg_closest_word(
				l_centroid[iel * self.__bitvec_size:(iel + 1) * self.__bitvec_size])
			close_phrase.append(word)
		print('centroid:', rcluster, close_phrase)

	def process_clusters(self):
		print('Cluster closest els:')
		for plen, l_cent_hd_thresh in enumerate(self.__ll_cent_hd_thresh):
			for i_lencent, hd_thresh in enumerate(l_cent_hd_thresh):
				irec = len(self.__ll_centroids)
				close_phrase = []
				for iel in range(plen):
					word = self.__nlb_mgr.dbg_closest_word(self.__l_nd_centroids[plen][i_lencent][iel*self.__bitvec_size:(iel+1)*self.__bitvec_size])
					close_phrase.append(word)
				print('rcent:', irec, ', hd:', hd_thresh, ',', close_phrase)
				self.__ll_centroids.append(np.reshape(self.__l_nd_centroids[plen][i_lencent], -1).tolist())
				self.__l_cent_hd.append(hd_thresh)
				bitvecdb.add_rec(self.__hcdb_cent, plen,
								 self.convert_charvec_to_arr(self.__ll_centroids[-1]))
				bitvecdb.set_hd_thresh(self.__hcdb_cent, irec, hd_thresh)

	def init_from_load(self):
		self.load_clusters()
		self.process_clusters()

	def cluster_one_thresh(self, plen, recc_thresh):
		num_left = self.__bdb_all.init_num_left_buf(plen)
		cent_ret = bitvecdb.charArray(self.__bitvec_size*plen)
		hd_avg_ret, hd_thresh = bitvecdb.floatArray(1), bitvecdb.intArray(1)
		l_clusters = []
		while num_left > 0:
			num_left_now = self.__bdb_all.get_cluster_seed(cent_ret, hd_avg_ret, hd_thresh, plen, recc_thresh)
			num_added = num_left - num_left_now
			num_left = num_left_now
			l_cent = [ord(cent_ret[ib]) for ib in range(self.__bitvec_size*plen)]
			l_clusters.append(nt_cluster(l_cent=l_cent, hd=hd_thresh[0], score=hd_avg_ret[0], num_hit=num_added))
		nd_hd_cluster, nd_num = np.zeros(len(l_clusters)), np.zeros(len(l_clusters))
		nd_centroids = np.zeros((len(l_clusters), self.__bitvec_size*plen), dtype=np.uint8)
		l_hd_thresh = []
		for icluster, cluster in enumerate(l_clusters):
			nd_hd_cluster[icluster] = cluster.score
			nd_num[icluster] = cluster.num_hit
			nd_centroids[icluster, :] = np.array(cluster.l_cent, dtype=np.uint8)
			l_hd_thresh.append(cluster.hd)
			# l_homog_score.append(hd_cluster)
		score = np.sum(np.multiply(nd_hd_cluster, nd_num)) / np.sum(nd_num)
		final_score = nd_hd_cluster.shape[0] * score
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
		return entr_tot / tot_tot_hits, tot_tot_hits

	def cluster(self, l_rule_names, max_plen):
		entr_tot, tot_hits, tot_clusters = 0., 0, 0
		self.__l_nd_centroids, self.__ll_cent_hd_thresh = [[] for _ in range(max_plen)], [[] for _ in range(max_plen)]
		for plen in range(max_plen):
			num_plen_recs = self.__bdb_all.get_num_plen(plen)
			if num_plen_recs <= 0: continue
			best_thresh, best_homog_score = -1, sys.float_info.max
			for recc_thresh in range(6, self.__bitvec_size * 1 / 5): # * 2 / 5
				homog_score, nd_centroids_t, l_cent_hd_thresh_t = self.cluster_one_thresh(plen, recc_thresh)
				if homog_score < best_homog_score:
					best_homog_score = homog_score
					best_thresh, nd_centroids, l_cent_hd_thresh = recc_thresh, nd_centroids_t, l_cent_hd_thresh_t
			self.__l_nd_centroids[plen] = nd_centroids; self.__ll_cent_hd_thresh[plen] = l_cent_hd_thresh
			entr_score,plen_hits= self.assign_rule_name_score(plen, nd_centroids, l_cent_hd_thresh, l_rule_names,
														 num_plen_recs)
			entr_tot += entr_score*plen_hits; tot_hits += plen_hits; tot_clusters += nd_centroids.shape[0]

		# The entropy score is just entr_tot / tot_hits, but I want to penalize for having too many clusters
		score = tot_clusters * (0.1 + entr_tot / tot_hits)
		print('Score:', score)
		self.process_clusters()
		# exit()
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
				csvw.writerow([ilen, hd] + lbits)

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
					ilen, hd, lsbits = int(row[0]), int(row[1]), row[2:]
					# bitvals = np.reshape(np.array(map(int, lsbits), dtype=np.int8), (ilen, self.__bitvec_size))
					bitvals = np.array(map(int, lsbits), dtype=np.int8)
					self.__ll_cent_hd_thresh[ilen].append(hd)
					ll_centroids[ilen].append(bitvals)
					del row, ilen, hd, lsbits
				self.__l_nd_centroids = []
				for ilen, l_cents in enumerate(ll_centroids):
					if l_cents == []:
						self.__l_nd_centroids.append([])
					else:
						self.__l_nd_centroids.append(np.stack(l_cents, axis=0))

		except IOError:
			raise ValueError('Cannot open or read ', fn)

		# return l_nd_centroids, ll_cent_hd_thresh

	def convert_charvec_to_arr(self, bin, size=-1):
		size = len(bin)
		bin_arr = bitvecdb.charArray(size)
		for ib in range(size): bin_arr[ib] = chr(bin[ib])
		return bin_arr


	def get_cluster(self, l_phrase_bits):
		plen = len(l_phrase_bits) / self.__bitvec_size
		# Each cent is an array of el bitvecs, each cent is also an array of hd, one for each el
		num_recs = len(self.__l_cent_hd)
		ret_arr = bitvecdb.intArray(num_recs)
		num_ret = bitvecdb.get_thresh_recs(	self.__hcdb_cent, ret_arr, plen,
											self.convert_charvec_to_arr(l_phrase_bits))
		l_rcents = [ret_arr[i] for i in range(num_ret)]
		return l_rcents




