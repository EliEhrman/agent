import random
import sys
import math
import numpy as np

c_num_seeds_initial = 5
c_cluster_thresh = 10 # 18

def cluster_one_thresh(plen, ndbits, num_recs, gen_cluster_thresh):
	left_out_mrk = np.ones(num_recs, dtype=np.uint8)
	num_left = num_recs
	nd_centroids = []
	while num_left > 0:
		num_seeds_to_add = min(num_left, c_num_seeds_initial)
		rand_top_sel = np.multiply(np.random.random(num_recs), left_out_mrk)
		# arg_sel = np.argsort(rand_top_sel)
		# l_iseeds = [np.where(arg_sel==ir)[0][0] for ir in range(num_seeds_to_add)]
		l_iseeds = np.argsort(-rand_top_sel)[:num_seeds_to_add]
		nd_new_centroids = ndbits[l_iseeds]
		nd_centroids = nd_new_centroids if nd_centroids == [] else np.concatenate((nd_centroids, nd_new_centroids),
																				  axis=0)
		# l_iseeds = random.sample(range(num_recs), c_num_seeds_initial)
		l_remove = []
		for ii1, iseed1 in enumerate(nd_centroids):
			for ii2, iseed2 in enumerate(nd_centroids):
				if ii2 <= ii1: continue
				if ii2 in l_remove: continue
				hd = np.sum(np.not_equal(iseed1, iseed2)) / plen
				if hd < gen_cluster_thresh:  # using the original thresh here
					l_remove.append(ii2)
				del ii2, iseed2, hd
			del ii1, iseed1
		l_keep = range(nd_centroids.shape[0])
		for ii3 in sorted(l_remove, key=int, reverse=True):
			del l_keep[ii3]
			del ii3
		nd_centroids = nd_centroids[l_keep]
		l_cent_hd_thresh = [gen_cluster_thresh for _ in nd_centroids]
		left_out_mrk, num_left = create_clusters_from_seeds(num_recs, plen, ndbits, nd_centroids, l_cent_hd_thresh)
	# nd_cluster_mrks = np.zeros((nd_centroids.shape[0], num_recs), dtype=np.uint8)
	# for ii1, nd_cent in enumerate(nd_centroids):
	# 	hd = np.sum(np.not_equal(ndbits, nd_cent), axis=(1,2)) / plen
	# 	frst_cluster_mrks = np.less(hd, l_cent_hd_thresh[ii1]).astype(np.uint8)
	# 	cluster_sum = np.sum(np.multiply(np.transpose(ndbits, axes=(1, 2, 0)), frst_cluster_mrks), axis=2)
	# 	fcentroid = cluster_sum / float(np.count_nonzero(frst_cluster_mrks))
	# 	centroid = np.round_(fcentroid).astype(np.uint8)
	# 	hd2 = np.sum(np.not_equal(ndbits, centroid), axis=(1,2)) / plen
	# 	nd_cluster_mrks[ii1, :] = np.less(hd2, l_cent_hd_thresh[ii1]).astype(np.uint8)
	# all_mrks = np.any(nd_cluster_mrks, axis=0)
	# left_out_mrk = np.logical_xor(all_mrks, 1)
	# num_left = np.count_nonzero(left_out_mrk)
	l_keep_reducing = [True for _ in nd_centroids]
	l_cent_hd_thresh = [gen_cluster_thresh for _ in nd_centroids]
	while any(l_keep_reducing):
		for icent, nd_centroid in enumerate(nd_centroids):
			if not l_keep_reducing[icent]: continue
			l_cent_hd_thresh[icent] -= 1
			_, num_left = create_clusters_from_seeds(num_recs, plen, ndbits, nd_centroids, l_cent_hd_thresh)
			if num_left > 0:
				l_cent_hd_thresh[icent] += 1
				# _, num_left = create_clusters_from_seeds(num_recs, plen, ndbits, nd_centroids, l_cent_hd_thresh)
				# assert (num_left == 0), 'Error. No records should be out of cluster at this point'
				l_keep_reducing[icent] = False
	homog_score = calc_homog(plen, ndbits, nd_centroids, l_cent_hd_thresh)
	return homog_score, nd_centroids, l_cent_hd_thresh

def assign_rule_name_score(plen, ndbits, nd_centroids, l_cent_hd_thresh, l_rule_names, iphrase_by_len, d_rule_gprs):
	l_entr, l_tot_hits = [], []
	for ii1, nd_cent in enumerate(nd_centroids):
		hd = np.sum(np.not_equal(ndbits, nd_cent), axis=(1, 2)) / plen
		cluster_mrks = np.less(hd, l_cent_hd_thresh[ii1]).astype(np.bool)
		tot_hits = np.sum(cluster_mrks)
		d_cluster_rules, l_num_hits, l_hit_names = dict(), [], []
		for irec, bcluster in enumerate(cluster_mrks):
			if not bcluster: continue
			rule_name = l_rule_names[iphrase_by_len[plen][irec]]
			rule_grp_id = d_rule_gprs.get(rule_name, -1)
			assert rule_grp_id != -1, 'Error. Rule name not in a rule group'
			irule = d_cluster_rules.get(rule_grp_id, -1)
			if irule == -1:
				d_cluster_rules[rule_grp_id] = len(l_num_hits)
				l_num_hits.append(1)
				l_hit_names.append([rule_name])
			else:
				l_num_hits[irule] += 1
				l_hit_names[irule].append(rule_name)
		entr = 0.
		for irule, num_hits in enumerate(l_num_hits):
			p = float(num_hits) / tot_hits
			entr += -p*math.log(p, 2)
		l_entr.append(entr)
		l_tot_hits.append(tot_hits)
	entr_tot, tot_tot_hits = 0., 0
	for entr, tot_hits in zip(l_entr, l_tot_hits):
		entr_tot += entr * tot_hits; tot_tot_hits += tot_hits
	return entr_tot / tot_tot_hits, tot_tot_hits

def cluster(ndbits_by_len, l_rule_names, iphrase_by_len, d_rule_gprs):
	l_nd_centroids, ll_cent_hd_thresh = [[] for _ in ndbits_by_len], [[] for _ in ndbits_by_len]
	entr_tot, tot_hits, tot_clusters = 0., 0, 0
	for plen, ndbits in enumerate(ndbits_by_len):
		if ndbits == None or ndbits == []: continue
		num_recs = ndbits.shape[0]
		if num_recs < c_num_seeds_initial: continue
		best_thresh, best_homog_score = -1, sys.float_info.max
		for gen_cluster_thresh in range(6, ndbits.shape[2] * 2 / 5): # * 2 / 5
			homog_score, nd_centroids_t, l_cent_hd_thresh_t = cluster_one_thresh(plen, ndbits, num_recs, gen_cluster_thresh)
			if homog_score < best_homog_score:
				best_homog_score = homog_score
				best_thresh, nd_centroids, l_cent_hd_thresh = gen_cluster_thresh, nd_centroids_t, l_cent_hd_thresh_t
		l_nd_centroids[plen] = nd_centroids; ll_cent_hd_thresh[plen] = l_cent_hd_thresh
		entr_score,plen_hits= assign_rule_name_score(plen, ndbits, nd_centroids, l_cent_hd_thresh, l_rule_names, iphrase_by_len, d_rule_gprs)
		entr_tot += entr_score*plen_hits; tot_hits += plen_hits; tot_clusters += nd_centroids.shape[0]
		pass
	# The entropy score is just entr_tot / tot_hits, but I want to penalize for having too many clusters
	score = tot_clusters * (0.1 + entr_tot / tot_hits)
	print('Score:', score)
	exit()
	return score


def calc_homog(plen, ndbits, nd_centroids, l_cent_hd_thresh):
	nd_hd_cluster, nd_num = np.zeros(nd_centroids.shape[0]), np.zeros(nd_centroids.shape[0])
	for ii1, nd_cent in enumerate(nd_centroids):
		hd = np.sum(np.not_equal(ndbits, nd_cent), axis=(1, 2)) / plen
		# cluster_mrks = np.less(hd, l_cent_hd_thresh[ii1]).astype(np.uint8)
		# cluster_sum = np.sum(np.multiply(np.transpose(ndbits, axes=(1, 2, 0)), cluster_mrks), axis=2)
		# fcentroid = cluster_sum / float(np.count_nonzero(cluster_mrks))
		# centroid = np.round_(fcentroid).astype(np.uint8)
		# nd_cluster = ndbits[cluster_mrks, :, :]
		cluster_mrks = np.less(hd, l_cent_hd_thresh[ii1]).astype(np.bool)
		nd_cluster = ndbits[cluster_mrks, :, :]
		fcentroid = np.average(nd_cluster, axis=0)
		centroid = np.round_(fcentroid).astype(np.uint8)
		nd_hd_cluster[ii1] = np.sum(np.average(np.not_equal(nd_cluster, centroid), axis=0)) / plen
		nd_num[ii1] = np.sum(cluster_mrks)
		# l_homog_score.append(hd_cluster)
	score = np.sum(np.multiply(nd_hd_cluster, nd_num)) / np.sum(nd_num)
	return nd_centroids.shape[0] * score # * score

def create_clusters_from_seeds(num_recs, plen, ndbits, nd_centroids, l_cent_hd_thresh):
	nd_cluster_mrks = np.zeros((nd_centroids.shape[0], num_recs), dtype=np.uint8)
	for ii1, nd_cent in enumerate(nd_centroids):
		hd = np.sum(np.not_equal(ndbits, nd_cent), axis=(1, 2)) / plen
		# frst_cluster_mrks = np.less(hd, l_cent_hd_thresh[ii1]).astype(np.uint8)
		# cluster_sum = np.sum(np.multiply(np.transpose(ndbits, axes=(1, 2, 0)), frst_cluster_mrks), axis=2)
		# fcentroid = cluster_sum / float(np.count_nonzero(frst_cluster_mrks))
		# centroid = np.round_(fcentroid).astype(np.uint8)
		# hd2 = np.sum(np.not_equal(ndbits, centroid), axis=(1, 2)) / plen
		# nd_cluster_mrks[ii1, :] = np.less(hd2, l_cent_hd_thresh[ii1]).astype(np.uint8)
		nd_cluster_mrks[ii1, :] = np.less(hd, l_cent_hd_thresh[ii1]).astype(np.uint8)
		# nd_centroids[ii1, :, :] = centroid
	all_mrks = np.any(nd_cluster_mrks, axis=0)
	left_out_mrk = np.logical_xor(all_mrks, 1)
	num_left = np.count_nonzero(left_out_mrk)
	return  left_out_mrk, num_left




