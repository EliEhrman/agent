import random
import numpy as np

c_num_seeds_initial = 5
c_cluster_thresh = 18

def cluster(ndbits_by_len):
	for plen, ndbits in enumerate(ndbits_by_len):
		if ndbits == None or ndbits == []: continue
		num_recs = ndbits.shape[0]
		if num_recs < c_num_seeds_initial: continue
		l_iseeds = random.sample(range(num_recs), c_num_seeds_initial)
		l_remove = []
		for ii1, iseed1 in enumerate(l_iseeds):
			for ii2, iseed2 in enumerate(l_iseeds):
				if ii2 <= ii1: continue
				if ii2 in l_remove: continue
				hd = np.sum(np.not_equal(ndbits[iseed1], ndbits[iseed2])) / plen
				if hd < c_cluster_thresh:
					l_remove.append(ii2)
				del ii2, iseed2, hd
			del ii1, iseed1
		for ii3 in sorted(l_remove, key=int, reverse=True):
			del l_iseeds[ii3]
		del ii3
		nd_cluster_mrks = np.zeros((len(l_iseeds), num_recs), dtype=np.uint8)
		for ii1, iseed1 in enumerate(l_iseeds):
			hd = np.sum(np.not_equal(ndbits, ndbits[iseed1]), axis=(1,2)) / plen
			frst_cluster_mrks = np.less(hd, c_cluster_thresh).astype(np.uint8)
			cluster_sum = np.sum(np.multiply(np.transpose(ndbits, axes=(1, 2, 0)), frst_cluster_mrks), axis=2)
			fcentroid = cluster_sum / float(np.count_nonzero(frst_cluster_mrks))
			centroid = np.round_(fcentroid).astype(np.uint8)
			hd2 = np.sum(np.not_equal(ndbits, centroid), axis=(1,2)) / plen
			nd_cluster_mrks[ii1, :] = np.less(hd2, c_cluster_thresh).astype(np.uint8)

		all_mrks = np.logical_or(nd_cluster_mrks, axis=0)
		num_left = np.count_nonzero(np.logical_xor(all_mrks, 1))
		while num_left > 0:


