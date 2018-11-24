import random
import numpy as np

c_num_seeds_initial = 5
c_cluster_thresh = 18

def cluster(ndbits_by_len):
	for plen, ndbits in enumerate(ndbits_by_len):
		if ndbits == None or ndbits == []: continue
		num_recs = ndbits.shape[0]
		if num_recs < c_num_seeds_initial: continue
		left_out_mrk = np.ones(num_recs, dtype=np.uint8)
		num_left = num_recs
		# l_iseeds = []
		nd_centroids = []
		while num_left > 0:
			num_seeds_to_add = min(num_left, c_num_seeds_initial)
			rand_top_sel = np.multiply(np.random.random(num_recs), left_out_mrk)
			arg_sel = np.argsort(rand_top_sel)
			l_iseeds = [np.where(arg_sel==ir)[0][0] for ir in range(num_seeds_to_add)]
			nd_new_centroids = ndbits[l_iseeds]
			nd_centroids = nd_new_centroids if nd_centroids == [] else np.concatenate(nd_centroids, nd_new_centroids)
			# l_iseeds = random.sample(range(num_recs), c_num_seeds_initial)
			l_remove = []
			for ii1, iseed1 in enumerate(nd_centroids):
				for ii2, iseed2 in enumerate(nd_centroids):
					if ii2 <= ii1: continue
					if ii2 in l_remove: continue
					hd = np.sum(np.not_equal(iseed1, iseed2)) / plen
					if hd < c_cluster_thresh:
						l_remove.append(ii2)
					del ii2, iseed2, hd
				del ii1, iseed1
			l_keep = range(nd_centroids.shape[0])
			for ii3 in sorted(l_remove, key=int, reverse=True):
				del l_keep[ii3]
			del ii3
			nd_centroids = nd_centroids[l_keep]
			nd_cluster_mrks = np.zeros((nd_centroids.shape[0], num_recs), dtype=np.uint8)
			for ii1, nd_cent in enumerate(nd_centroids):
				hd = np.sum(np.not_equal(ndbits, nd_cent), axis=(1,2)) / plen
				frst_cluster_mrks = np.less(hd, c_cluster_thresh).astype(np.uint8)
				cluster_sum = np.sum(np.multiply(np.transpose(ndbits, axes=(1, 2, 0)), frst_cluster_mrks), axis=2)
				fcentroid = cluster_sum / float(np.count_nonzero(frst_cluster_mrks))
				centroid = np.round_(fcentroid).astype(np.uint8)
				hd2 = np.sum(np.not_equal(ndbits, centroid), axis=(1,2)) / plen
				nd_cluster_mrks[ii1, :] = np.less(hd2, c_cluster_thresh).astype(np.uint8)
			all_mrks = np.logical_or(nd_cluster_mrks, axis=0)
			left_out_mrk = np.logical_xor(all_mrks, 1)
			num_left = np.count_nonzero(left_out_mrk)




