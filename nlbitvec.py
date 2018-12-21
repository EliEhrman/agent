from __future__ import print_function
import bitvec
# from bitvec import c_bitvec_size as bitvec_size
import csv
import os
from os.path import expanduser
from shutil import copyfile
import numpy as np
import itertools
import collections
import copy

import cluster

c_phrase_fnt = '~/tmp/adv_phrases.txt'

c_bitvec_size = 50 # 16
c_bitvec_neibr_divider_offset = 5
c_num_ham_winners = 30
c_num_assign_tries = 5
c_pair_avg_hd_cutoff = 6.0
c_b_find_pairs = True

# bitvals are the values that are rounded to make the bits. Kept in this form because uniqueness only calculated at insertion into main dict
# avg_hd is the average hd between the phrase minues the el and the corresponding closest phrases of n shorter length
# devi is the deviation of the corresponding bits  to the el in the closest phrases. deviation calculated as average of diff between rounded average and the src bits
nt_new_el = collections.namedtuple('nt_new_el', 'el, avg_hd, devi, num_hits, bitvals')
# bglove, if True, means the el comes from the glove dict and is not not be changed
# l_iphrases is a list of indices into __l_phrases that the el appears in
nt_el_stats = collections.namedtuple('nt_el_stats', 'el, bglove, bassigned, avg_hd, num_hits, l_iphrases, l_idelayed, bitvals, bitvec')
nt_el_stats.__new__.__defaults__ = ('???', False, False, -1.0, 0, None, None, [], np.zeros(c_bitvec_size, dtype=np.uint8))
nt_mult_el = collections.namedtuple('nt_mult_el', 'el, iel, pos, len')

divider = np.array(
	range(c_bitvec_neibr_divider_offset,c_num_ham_winners + c_bitvec_neibr_divider_offset),
	np.float32)
divider_sum = np.sum(1. / divider)

class cl_nlb_mgr_notific(object):
	def __init__(self):
		self.__d_iels = dict()

	def notify_on_iel(self, iel):
		self.__d_iels[iel] = True

	def iel_bitvec_changed(self, iel, bitvec):
		balert = self.__d_iels.get(iel, False)
		if not balert: return
		self.iel_bitvec_changed_alert(iel, bitvec)

	def iel_bitvec_changed_alert(self, iel, bitvec):
		print('Error. This should not be called')

	def reset(self):
		self.__d_iels = dict()

class cl_nlb_mgr(object):
	def __init__(	self, b_restart_from_glv, phrase_mgr, phraseperms_mgr, bdb_all,
					bitvec_dict_glv_fnt, rule_grp_fnt, saved_phrases_fnt,
					bitvec_dict_output_fnt, cluster_fnt):
		self.__phrase_mgr = phrase_mgr
		self.__phraseperms = phraseperms_mgr
		self.__bdb_all = bdb_all
		bitvec_dict_fnt = bitvec_dict_glv_fnt if b_restart_from_glv else bitvec_dict_output_fnt
		self.__cluster_fnt = cluster_fnt
		self.__d_words = dict()
		d_words, nd_bit_db, s_word_bit_db, l_els, l_els_stats = self.load_word_db(bitvec_dict_fnt)
		self.__bitvec_dict_output_fnt = bitvec_dict_output_fnt
		self.__d_words = d_words
		self.__s_word_bit_db = s_word_bit_db
		self.__nd_word_bin = nd_bit_db
		self.__l_els_here = l_els
		self.__l_els_stats = l_els_stats # type: List(nt_el_stats)
		# self.__bitvec_mgr = bitvec_mgr
		# self.__map_phrase_to_rphrase = dict() # type : Dict[str, int] # map the text of the phrase
		self.__ndbits_by_len = [] # bit representation of phrase, ordered by phrase len
		self.__iphrase_by_len = [] # for each len, entry corresponding to __ndbits_by_len, index into l_phrases
		self.__phrase_by_len_idx = [] # for each entry of l_phrases, -1 if unassigned, index into iphrase by len and ndbits_by len otherwise
		# self.__l_phrases = [] # type: List(str)
		self.__l_delayed_iphrases = []
		self.__l_rule_name  = [] # for each entry of l_phrases, the name of the rule that created it
		self.__rule_grp_fnt = rule_grp_fnt
		# self.__d_rule_grps = dict()
		# self.load_rule_grps()
		self.__bitvec_saved_phrases_fnt = saved_phrases_fnt
		self.__l_saved_phrases = []
		self.__b_restart_from_glv = b_restart_from_glv
		# if b_restart_from_glv:
		# 	self.load_save_phrases()
		# 	l_nd_centroids, ll_cent_hd_thresh = self.load_sample_texts(c_phrase_fnt)
		# else:
		# 	l_nd_centroids, ll_cent_hd_thresh = cluster.load_clusters(cluster_fnt, c_bitvec_size)
		self.__mpdb_mgr = None
		self.__mpdb_bins = []
		# self.__l_nd_centroids = l_nd_centroids
		# self.__ll_cent_hd_thresh = ll_cent_hd_thresh
		self.__l_nd_centroids = []
		self.__ll_cent_hd_thresh = []
		self.__l_notifics = [] # type: List[cl_nlb_mgr_notific]
		# for num_try_assign in range(c_num_assign_tries):
		# 	num_unassigned = self.assign_unknown_words()
		# 	if num_unassigned == 0:
		# 		break
		# self.learn_pair_bins()
		pass

	# def init_data(self):
	# 	if self.__b_restart_from_glv:
	# 		self.load_save_phrases()
	# 		l_nd_centroids, ll_cent_hd_thresh = self.load_sample_texts(c_phrase_fnt)
	# 	else:
	# 		l_nd_centroids, ll_cent_hd_thresh = cluster.load_clusters(self.__cluster_fnt, c_bitvec_size)
	# 	self.__l_nd_centroids = l_nd_centroids
	# 	self.__ll_cent_hd_thresh = ll_cent_hd_thresh
	def get_bitvec_size(self):
		return c_bitvec_size

	def load_word_db(self, bitvec_dict_fnt):
		fn = expanduser(bitvec_dict_fnt)
		# if True:
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				_, snum_els = next(csvr)
				next(csvr); next(csvr)
				version, num_els = int(version_str), int(snum_els)
				if version != 2:
					raise IOError
				d_words, s_word_bit_db, nd_bit_db = dict(), set(), np.zeros((num_els, c_bitvec_size), dtype=np.uint8)
				l_els = ['' for _ in xrange(num_els)]
				l_els_stats = [nt_el_stats(bglove=True, bassigned=True) for _ in xrange(num_els)]
				for irow in range(num_els):
					row = next(csvr)
					word, iel, sbits = row[0], row[1], row[2:]
					rowdata = next(csvr)
					bglove, bassigned, avg_hd = rowdata[0]=='True', rowdata[1]=='True', float(rowdata[2])
					num_hits, bitvals = int(rowdata[3]), rowdata[4:]
					if bitvals == ['[]']:
						bitvals = []
					else:
						bitvals = np.array(map(float, bitvals), dtype=float)
					bits = map(int, sbits)
					ndbits = np.array(bits, dtype=np.uint8)
					d_words[word] = int(iel)
					l_els[int(iel)] = word
					l_els_stats[int(iel)] = nt_el_stats(el=word, bglove=bglove, bassigned=bassigned,
														avg_hd=avg_hd, num_hits=num_hits, bitvals=bitvals, bitvec=ndbits,
														l_idelayed=[], l_iphrases=[])
					nd_bit_db[int(iel)] = ndbits
					s_word_bit_db.add(tuple(bits))  # if asserts here check bitvec.bitvec_size

		except IOError:
			raise ValueError('Cannot open or read ', fn)

		return d_words, nd_bit_db, s_word_bit_db, l_els, l_els_stats

	def save_word_db(self):
		# d_words, nd_bit_db, fnt_dict):
		fn = expanduser(self.__bitvec_dict_output_fnt)

		if os.path.isfile(fn):
			copyfile(fn, fn + '.bak')
		fh = open(fn, 'wb')
		csvw = csv.writer(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
		csvw.writerow(['Glv Dict', 'Version', '2'])
		csvw.writerow(['Num Els:', len(self.__d_words)])
		csvw.writerow(['el', 'eid', 'bitvec'])
		csvw.writerow(['bglove', 'bassigned', 'avg_hd', 'num_hits', 'bitvals'])
		for kword, virow in self.__d_words.iteritems():
			els_stats = self.__l_els_stats[virow]
			assert kword==els_stats.el.lower(), 'save_word_db: dict mismatch'
			csvw.writerow([kword, virow] + els_stats.bitvec.tolist())
			lbitvals = ['[]']
			if els_stats.bitvals != []:
				lbitvals = els_stats.bitvals.tolist()
			csvw.writerow([els_stats.bglove, els_stats.bassigned, els_stats.avg_hd, els_stats.num_hits] + lbitvals)

		fh.close()

	def get_el_id(self, word):
		return self.__d_words.get(word, -1)

	def get_bin_by_id(self, id):
		return self.__nd_word_bin[id]

	def get_el_by_eid(self, eid):
		return self.__l_els_stats[eid].el

	def add_unique_bits(self, new_bits):
		self.__s_word_bit_db.add(tuple(new_bits))

	def remove_unique_bits(self, bits):
		self.__s_word_bit_db.remove(tuple(bits))

	def set_mpdb_mgr(self, mpdb_mgr):
		self.__mpdb_mgr = mpdb_mgr

	def get_mpdb_mgr(self):
		return self.__mpdb_mgr

	def clear_mpdb_bins(self):
		self.__mpdb_bins = []

	def add_phrase(self, phrase_src, creating_rule_name=''):
		phrase = [w for lw in [el.split() for el in phrase_src] for w in lw]
		i_all_phrases = self.__add_phrase(phrase)
		if creating_rule_name != '':
			grow = 1 + i_all_phrases - len(self.__l_rule_name)
			if grow > 0:
				self.__l_rule_name += [[] for _ in range(grow)]
			if creating_rule_name not in self.__l_rule_name[i_all_phrases]:
				self.__l_rule_name[i_all_phrases].append(creating_rule_name)

		return i_all_phrases

	def __add_phrase(self, phrase):
		rphrase = self.__phrase_mgr.get_rphrase(phrase)
		# rphrase = self.__map_phrase_to_rphrase.get(tuple(phrase), -1)
		if rphrase != -1:
			return rphrase
		return self.add_new_row(phrase)

	def new_phrase_from_phrase_mgr(self, rphrase):
		phrase = self.__phrase_mgr.get_phrase(rphrase)
		self.__bdb_all.add_new_phrase(rphrase)
		return self.__add_new_row(rphrase, phrase)

	def add_new_row(self, phrase):
		i_all_phrases = self.__phrase_mgr.add_phrase(phrase)
		self.__phraseperms.add_new_phrase(i_all_phrases)
		self.__bdb_all.add_new_phrase(i_all_phrases)
		self.__add_new_row(i_all_phrases, phrase)

	def __add_new_row(self, i_all_phrases, phrase):
		grow = 1 + i_all_phrases - len(self.__phrase_by_len_idx)
		self.__phrase_by_len_idx += [-1 for _ in range(grow)]
		del grow
		if (len(phrase) + 1) > len(self.__ndbits_by_len):
			l_grow_init = [[] for _ in range((1 + len(phrase) - len(self.__ndbits_by_len)))]
			self.__ndbits_by_len += l_grow_init
			self.__iphrase_by_len += copy.deepcopy(l_grow_init)
			# by_len_iphrase = 0
			del l_grow_init
		return self.process_new_row(i_all_phrases)

	def process_new_row(self, i_all_phrases):
		phrase = self.__phrase_mgr.get_phrase(i_all_phrases)
		# phrase = self.__l_phrases[i_all_phrases]
		b_add_now = True
		nd_phrase = np.zeros((len(phrase), c_bitvec_size), dtype=np.uint8)
		l_phrase_iels = []
		num_unassigned, i_last_unassigned = 0, -1
		for iword, word in enumerate(phrase):
			iel = self.__d_words.get(word.lower(), -1)
			if iel == -1:
				iel = len(self.__l_els_stats)
				self.__d_words[word.lower()] = iel
				el_stats = nt_el_stats(el=word, l_iphrases=[i_all_phrases], l_idelayed=[])
				self.__l_els_stats.append(el_stats)
				self.__l_els_here.append(word)
				b_add_now = False
				num_unassigned += 1
				i_last_unassigned = iword
				nd_wbits = np.zeros(c_bitvec_size, dtype=np.uint8)
				# glv_wid = self.get_el_id(word.lower())
				# if glv_wid == -1:
				# else:
				# 	nd_wbits = self.get_bin_by_id(glv_wid)
				# 	el_stats = el_stats._replace(bglove=True, bassigned=True, bitvec=nd_wbits)
				# 	nd_phrase[iword, :] = nd_wbits
				if self.__nd_word_bin is None:
					self.__nd_word_bin = np.expand_dims(nd_wbits, axis=0)
					self.__s_word_bit_db.add(np.zeros(c_bitvec_size, dtype=np.uint8))
				else:
					iel = self.__nd_word_bin.shape[0]
					self.__nd_word_bin = np.concatenate((self.__nd_word_bin,
														 np.expand_dims(nd_wbits, axis=0)), axis=0)
				assert self.__nd_word_bin.shape[0] == len(self.__d_words), 'Error. Forgot to add word bin'

				del nd_wbits # , glv_wid
			else:  # if word already seen
				el_stats = self.__l_els_stats[iel]  # ._replace()
				if el_stats.l_iphrases == None: el_stats = el_stats._replace(l_iphrases = [])
				if i_all_phrases not in el_stats.l_iphrases:
					el_stats.l_iphrases.append(i_all_phrases)
				if el_stats.bassigned:
					nd_phrase[iword, :] = el_stats.bitvec
				else:
					b_add_now = False
					num_unassigned += 1
					i_last_unassigned = iword
			# end else of if iel == -1

			# self.__l_els_stats.append(nt_el_stats(el=word, bglove=True, avg_hd=-1., num_hits=1,
			# 									  bitvals=[], l_iphrases=[]))
			self.__l_els_stats[iel] = el_stats
			l_phrase_iels.append(iel)
			del el_stats, iel
		del word, iword
		# end loop over words

		i_just_assigned = -1
		if not b_add_now and num_unassigned == 1:
			word = phrase[i_last_unassigned] # type: str
			iel = self.__d_words[word.lower()]
			bassigned = self.assign_word_from_closest(phrase, iel, word, i_last_unassigned, nd_phrase)
			if bassigned:
				i_just_assigned = i_last_unassigned
				b_add_now = True
			del word, iel, bassigned

		del i_last_unassigned

		# If all the words in the phrase had already been assigned we can adjust the non-glove bitvecs
		# of the words in the phrase based on the other words
		if num_unassigned == 0: # this is the orig value, not updated if the single unassigned is assigned
			for iword, word in enumerate(phrase):
				iel = self.__d_words.get(word.lower(), -1)
				el_stats = self.__l_els_stats[iel]
				if not el_stats.bglove:
					self.assign_word_from_closest(phrase, iel, word, iword, nd_phrase)
				del iel, el_stats

		if b_add_now:
			self.__iphrase_by_len[len(phrase)].append(i_all_phrases)
			if self.__ndbits_by_len[len(phrase)] == []:
				by_len_iphrase = 0
				self.__ndbits_by_len[len(phrase)] = np.expand_dims(nd_phrase, axis=0)
			else:
				by_len_iphrase = self.__ndbits_by_len[len(phrase)].shape[0]
				self.__ndbits_by_len[len(phrase)] = np.concatenate((self.__ndbits_by_len[len(phrase)],
																	np.expand_dims(nd_phrase, axis=0)), axis=0)
			self.__phrase_by_len_idx[i_all_phrases] = by_len_iphrase
			self.__phraseperms.add_perm(i_all_phrases, l_phrase_iels)
		else:
			self.__l_delayed_iphrases += [i_all_phrases]
			# if the phrase cannot have a bitvec representation added due to there being more
			# than one unassigned word in the phrase, the unassigned words must list the phrase as delayer
			for iword, word in enumerate(phrase):
				iel = self.__d_words.get(word.lower(), -1)
				el_stats = self.__l_els_stats[iel]
				if not el_stats.bassigned:
					if i_all_phrases not in el_stats.l_idelayed:
						el_stats.l_idelayed.append(i_all_phrases)
				del iel, el_stats
			del iword, word

		if i_just_assigned != -1:
			word = phrase[i_just_assigned]
			iel = self.__d_words.get(word.lower(), -1)
			el_stats = self.__l_els_stats[iel]
			l_undelay = copy.deepcopy(el_stats.l_idelayed)
			el_stats.l_idelayed[:] = []
			for idelayed in l_undelay:
				# if idelayed == i_all_phrases:
				# 	el_stats.l_idelayed.remove(i_all_phrases)
				# else:
				if idelayed != i_all_phrases:
					self.process_new_row(idelayed)
			del iel, el_stats, word

		if c_b_find_pairs:
			self.find_pair_bins_for_phrase(phrase, l_phrase_iels, i_all_phrases)

		return i_all_phrases

	# end process unassigned row

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

	def load_save_phrases(self):
		fn = expanduser(self.__bitvec_saved_phrases_fnt)
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				_, snum_els = next(csvr)
				version, num_els = int(version_str), int(snum_els)
				if version != 1:
					raise IOError
				for irow, row in enumerate(csvr):
					self.__l_saved_phrases.append(row)

		except IOError:
			print('Cannot open or read ', fn)



	def load_sample_texts(self, phrase_fnt):
		# fn = expanduser(phrase_fnt)
		# # try:
		# if True:
		# 	with open(fn, 'rb') as o_fhr:
		# 		csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
		# 		for row in csvr:
		# 			self.add_new_row(row)
		# 		# end loop over rows

		bitvec_saved_phrases = self.__l_saved_phrases
		for phrase_data in bitvec_saved_phrases:
			self.add_phrase(phrase_data[1].split(), phrase_data[0])

		score, l_nd_centroids, ll_cent_hd_thresh = \
			self.__bdb_all.do_clusters(	self.__ndbits_by_len, self.__l_rule_name, self.__iphrase_by_len,
										self.__d_rule_grps, self.__bdb_all.get_max_plen())
		# self.__l_nd_centroids = l_nd_centroids
		# self.__ll_cent_hd_thresh = ll_cent_hd_thresh
		self.save_word_db()
		cluster.save_cluters(l_nd_centroids, ll_cent_hd_thresh, self.__cluster_fnt)
		return l_nd_centroids, ll_cent_hd_thresh


	def dbg_closest_words(self, bins):
		l_closest = []

		nd_hd_iword = np.sum(np.not_equal(bins, self.__nd_word_bin), axis=1)
		idx_of_hd_winners = np.argpartition(nd_hd_iword, c_num_ham_winners)[:c_num_ham_winners]
		hd_of_winners = nd_hd_iword[idx_of_hd_winners]
		iwinners = np.argsort(hd_of_winners)
		hd_idx_sorted = idx_of_hd_winners[iwinners]
		for iclosest in hd_idx_sorted:
			l_closest.append(self.__l_els_here[iclosest])

	def dbg_closest_word(self, bins):
		nd_hd_iword = np.sum(np.not_equal(bins, self.__nd_word_bin), axis=1)
		iclosest = np.argmin(nd_hd_iword)
		return self.__l_els_here[iclosest]

	def assert_glove_uniqueness(self, bitvec):
		print('Implement shoving a non-glove bitvec out of the way if already taken by a glove')

	def assign_word_from_closest(self, phrase, iel, word, i_last_miss, nd_phrase):
		els_stats = self.__l_els_stats[iel]
		plen = len(phrase)
		if True:
			phrase_eids = []
			for iword, word in enumerate(phrase):
				wid = self.__d_words.get(word.lower(), -1)
				phrase_eids.append(wid)
			l_idx_sorted, l_hds_sorted, nd_obits = self.__bdb_all.get_closest_recs(c_num_ham_winners, phrase_eids, i_last_miss)
			num_winners = len(l_idx_sorted)
			if num_winners == 0:
				return False
			divider_local = divider[:num_winners]
			divider_sum_local = np.sum(1. / divider_local)
			avg_hd = (np.sum(np.array(l_hds_sorted) / divider_local) / divider_sum_local) / (plen - 1)
			if num_winners < 5:
				print('Warning. Learning word', word, 'from only', num_winners, 'examples. avg_hd = ', avg_hd)
			new_vals = np.sum(nd_obits.transpose() / divider_local, axis=1) / divider_sum_local
		else:
			nd_bits_db = self.__ndbits_by_len[plen]
			if nd_bits_db is None or nd_bits_db == []:
				return False
			nd_hd = np.zeros(nd_bits_db.shape[0], dtype=int)
			for iword, word in enumerate(phrase):
				wid = self.__d_words.get(word.lower(), -1)
				if iword == i_last_miss: continue
				slice_iword = nd_bits_db[:, iword, :]
				wbits = self.__nd_word_bin[wid]
				nd_hd_iword = np.sum(np.not_equal(wbits, slice_iword), axis=1)
				nd_hd += nd_hd_iword
			if nd_hd.shape[0] > c_num_ham_winners:
				idx_of_hd_winners = np.argpartition(nd_hd, c_num_ham_winners)[:c_num_ham_winners]
				hd_of_winners = nd_hd[idx_of_hd_winners]
				iwinners = np.argsort(hd_of_winners)
				hd_idx_sorted = idx_of_hd_winners[iwinners]
				hd_of_winners_sorted = hd_of_winners[iwinners]
				del iwinners
			else:
				hd_of_winners = nd_hd
				hd_idx_sorted = np.argsort(hd_of_winners)
				hd_of_winners_sorted = hd_of_winners[hd_idx_sorted]
			num_winners = hd_of_winners_sorted.shape[0]
			l_idx_sorted, l_hds_sorted, nd_obits = self.__bdb_all.get_closest_recs(c_num_ham_winners, phrase_eids, i_last_miss)
			divider_local = divider[:num_winners]
			divider_sum_local = np.sum(1. / divider_local)
			avg_hd = (np.sum(hd_of_winners_sorted / divider_local) / divider_sum_local) / (plen - 1)
			del hd_of_winners_sorted
			# l_closest = []
			# for iclose in hd_idx_sorted.tolist():
			# 	iphrase = self.__iphrase_by_len[plen][iclose]
			# 	l_closest.append(self.__l_phrases[iphrase])
			slice_iword = nd_bits_db[:, i_last_miss, :]
			obits = slice_iword[hd_idx_sorted]
			new_vals = np.sum(obits.transpose() / divider_local, axis=1) / divider_sum_local
		# dev = np.average(np.not_equal(new_bits, obits))
		if els_stats.bassigned:
			# prev_new_el = l_new_els[inewel]
			self.remove_unique_bits(els_stats.bitvec)
			new_num_hits = els_stats.num_hits + 1
			old_cd = (c_bitvec_size - els_stats.avg_hd) / c_bitvec_size
			new_cd = (c_bitvec_size - avg_hd) / c_bitvec_size
			wold = old_cd * els_stats.num_hits
			avg_hd = ((avg_hd*new_cd) + (els_stats.avg_hd*wold))/(new_cd+wold)
			# avg_hd = (avg_hd + (els_stats.avg_hd * els_stats.num_hits)) / new_num_hits
			# new_devi = (devi + (els_stats.devi * els_stats.num_hits)) / new_num_hits
			new_vals = ((new_vals*new_cd) + (els_stats.bitvals * wold)) / (new_cd+wold)
			# new_vals = (new_vals + (els_stats.bitvals * els_stats.num_hits)) / new_num_hits
		else:
			new_num_hits = 1

		new_bits = np.round_(new_vals).astype(np.uint8)
		new_bits = np.array(self.create_closest_unique_bits(new_vals, new_bits), dtype=np.uint8)
		self.__nd_word_bin[iel, :] = new_bits
		self.alert_iel_changed(iel, new_bits)
		nd_phrase[i_last_miss, :] = new_bits
		# self.__ndbits_by_len[plen] = np.concatenate((self.__ndbits_by_len[plen],
		# 											 np.expand_dims(nd_phrase, axis=0)), axis=0)

		del phrase

		self.__l_els_stats[iel] = els_stats._replace(	bassigned=True, avg_hd=avg_hd, num_hits=new_num_hits,
														bitvals=new_vals, bitvec=new_bits)

		# now you have to apply binary changes to all phrases that this word appears in
		for iphrase in els_stats.l_iphrases:
			by_len_idx = self.__phrase_by_len_idx[iphrase]
			if by_len_idx == -1: continue
			phrase = self.__phrase_mgr.get_phrase(iphrase)
			# phrase = self.__l_phrases[iphrase]
			bfix, plen = True, len(phrase)
			nd_phrase2 = np.zeros((plen, c_bitvec_size), dtype=np.uint8)

			for iword, word in enumerate(phrase):
				iel = self.__d_words.get(word.lower(), -1)
				els_stats2 = self.__l_els_stats[iel]
				if not els_stats2.bassigned:
					bfix = False # can't happen
					break
				nd_phrase2[iword, :] = els_stats2.bitvec

			if bfix:
				self.__ndbits_by_len[plen][by_len_idx, :, :] = nd_phrase2
		return True



	def create_closest_unique_bits(self, new_vals, new_bits):
		s_word_bit_db = self.__s_word_bit_db
		if tuple(new_bits) in s_word_bit_db:
			bfound = False
			while True:
				can_flip = np.argsort(np.square(new_vals - 0.5))
				for num_flip in range(1, c_bitvec_size):
					try_flip = can_flip[:num_flip]
					l = [list(itertools.combinations(try_flip, r)) for r in range(num_flip + 1)]
					lp = [item for sublist in l for item in sublist]
					for p in lp:
						pbits = list(new_bits)
						for itf in try_flip:
							if itf in p:
								pbits[itf] ^= 1 # (1 ^ pbits[itf])
						if tuple(pbits) not in s_word_bit_db:
							new_bits = pbits
							bfound = True
							break
					if bfound:
						break
				if bfound:
					break
		self.add_unique_bits(new_bits)
		return new_bits

	def assign_unknown_words(self):
		assert False, 'Code will not be used until recap learning is implemented'
		l_failed_assign = []
		for idelayed in self.__l_delayed_iphrases:
			phrase = self.__phrase_mgr.get_phrase(idelayed)
			# phrase = self.__l_phrases[idelayed]
			plen = len(phrase)
			nd_phrase = np.zeros((plen, c_bitvec_size), dtype=np.uint8)
			for iword, word in enumerate(phrase):
				miss_count, i_last_miss, prov_count, l_wid_provs, i_last_prov = 0, -1, 0, [], -1
				wid = self.__d_words.get(word.lower(), -1)
				if wid == -1:
					miss_count += 1
					i_last_miss = iword
				else:
					nd_phrase[iword, :] = self.__nd_word_bin[wid]
					el_stats = self.__l_els_stats[wid]
					if not el_stats.bglove:
						prov_count += 1
						l_wid_provs.append(wid)
						i_last_prov = iword
				if miss_count > 1:
					break
			if miss_count == 0:
				if prov_count == 0:
					continue # surprising. old comment: # happens because word has since been assigned
				if prov_count > 1:
					# messed up over here. We need a separate list of iphrases for each local el prov or not
					# we need to update it here even if we cannot afford to actually calculate a new bitval set
					# but whenever we do change it,
					continue # not going to try and
			if miss_count > 1:
				l_failed_assign = idelayed
				continue
			nd_bits_db = self.__ndbits_by_len[plen]
			nd_hd = np.zeros(nd_bits_db.shape[0], dtype=int)
			for iword, word in enumerate(phrase):
				if iword == i_last_miss: continue
				slice_iword = nd_bits_db[:,iword,:]
				wid = self.__d_words.get(word.lower(), -1)
				wbits = self.__nd_word_bin[wid]
				nd_hd_iword = np.sum(np.not_equal(wbits, slice_iword), axis=1)
				nd_hd += nd_hd_iword
			idx_of_hd_winners = np.argpartition(nd_hd, c_num_ham_winners)[:c_num_ham_winners]
			hd_of_winners = nd_hd[idx_of_hd_winners]
			iwinners = np.argsort(hd_of_winners)
			hd_idx_sorted = idx_of_hd_winners[iwinners]
			# l_closest = []
			# for iclose in hd_idx_sorted.tolist():
			# 	iphrase = self.__iphrase_by_len[plen][iclose]
			# 	l_closest.append(self.__l_phrases[iphrase])
			slice_iword = nd_bits_db[:, i_last_miss, :]
			obits = slice_iword[hd_idx_sorted]
			new_vals = np.sum(obits.transpose() / divider, axis=1) / divider_sum
			# ref_std_dev = np.average(np.std(np.random.rand(30,50), axis=0))
			# std_dev = np.average(np.std(obits, axis=0))
			# std_dev = np.average(np.minimum(np.count_nonzero(obits, axis=0), c_bitvec_size - np.count_nonzero(obits, axis=0)))
			# round them all and if the pattern is already there switch the closest to 0.5
			new_bits = np.round_(new_vals).astype(np.uint8)
			dev = np.average(np.not_equal(new_bits, obits))
			new_bits = self.create_closest_unique_bits(new_vals, new_bits)
			nd_phrase[i_last_miss, :] = new_bits
			# self.dbg_closest_words(new_bits)
			iel = len(self.__l_els_here)
			self.__l_els_here.append(word)
			self.__ndbits_by_len[plen] = np.concatenate((self.__ndbits_by_len[plen],
															 np.expand_dims(nd_phrase, axis=0)), axis=0)
			self.__d_words[word.lower()] = iel
			self.__nd_word_bin = np.concatenate((self.__nd_word_bin,
												 np.expand_dims(new_bits, axis=0)), axis=0)
			self.__iphrase_by_len[plen].append(idelayed)
			# nt_el_stats = collections.namedtuple('nt_el_stats',
			# 									 'el, bglove, avg_hd, devi, num_hits, bitvals, l_iphrases')
			self.__l_els_stats.append(nt_el_stats(el=word, bglove=False, avg_hd=-1., num_hits=1,
												  bitvals=[new_vals], l_iphrases=[idelayed]))

		self.__l_delayed_iphrases = l_failed_assign
		return len(l_failed_assign)

	def find_pair_bins_for_phrase(self, phrase, l_phrase_iels, igphrase):
		l_mults = []
		phrase_eids = []
		for iword, word in enumerate(phrase):
			wid = self.__d_words.get(word.lower(), -1)
			phrase_eids.append(wid)
		for delta in range(1,3):
			for pos in range(len(phrase) - delta):
				if True:
					l_idx_sorted, l_hds_sorted, nd_obits \
							= self.__bdb_all.get_closest_recs(c_num_ham_winners, phrase_eids, pos, delta)
					num_winners = len(l_idx_sorted)
					if num_winners == 0: continue
					divider_local = divider[:num_winners]
					divider_sum_local = np.sum(1. / divider_local)
					avg_hd = (np.sum(np.array(l_hds_sorted) / divider_local) / divider_sum_local) / (len(phrase) - 1)
					if avg_hd > c_pair_avg_hd_cutoff: continue
					new_vals = np.sum(nd_obits.transpose() / divider_local, axis=1) / divider_sum_local
				else:
					len1 = len(phrase)
					if len1 <= delta or self.__iphrase_by_len[len1-delta] == []:
						continue
					nd_bits_db = self.__ndbits_by_len[len1-delta]

					for pos in range(len1-delta):
						nd_hd = np.zeros(nd_bits_db.shape[0], dtype=int)
						for iword_big, el in enumerate(phrase):
							# bskip = False
							if iword_big - pos in range(delta + 1): continue

							iword_small = iword_big if iword_big < pos else (iword_big - delta)
							slice_iword = nd_bits_db[:, iword_small, :]
							wid = self.__d_words.get(el.lower(), -1)
							wbits = self.__nd_word_bin[wid]
							nd_hd_iword = np.sum(np.not_equal(wbits, slice_iword), axis=1)
							nd_hd += nd_hd_iword

						if nd_hd.shape[0] > c_num_ham_winners:
							idx_of_hd_winners = np.argpartition(nd_hd, c_num_ham_winners)[:c_num_ham_winners]
							hd_of_winners = nd_hd[idx_of_hd_winners]
							iwinners = np.argsort(hd_of_winners)
							hd_idx_sorted = idx_of_hd_winners[iwinners]
							hd_of_winners_sorted = hd_of_winners[iwinners]
							# avg_hd = (np.sum(hd_of_winners_sorted / divider) / divider_sum) / (len1 - 1)
						else:
							hd_of_winners = nd_hd
							hd_idx_sorted = np.argsort(hd_of_winners)
							hd_of_winners_sorted = hd_of_winners[hd_idx_sorted]
						num_winners = hd_of_winners_sorted.shape[0]
						divider_local = divider[:num_winners]
						divider_sum_local = np.sum(1. / divider_local)
						avg_hd = (np.sum(hd_of_winners_sorted / divider_local) / divider_sum_local) / (len1 - delta)

						if avg_hd > c_pair_avg_hd_cutoff:
							continue

						# l_closest = []
						# for iclose in hd_idx_sorted.tolist():
						# 	iphrase = self.__iphrase_by_len[len1][iclose]
						# 	l_closest.append(self.__l_phrases[iphrase])
						slice_iword = nd_bits_db[:, pos, :]
						obits = slice_iword[hd_idx_sorted]
						new_vals = np.sum(obits.transpose() / divider_local, axis=1) / divider_sum_local
				# devi = np.average(np.not_equal(new_bits, obits))
				# std_dev = np.average(np.std(obits, axis=0))
				# std_dev = np.average(
				# 	np.minimum(np.count_nonzero(obits, axis=0), c_bitvec_size - np.count_nonzero(obits, axis=0)))
				new_el = ' '.join(phrase[pos:pos + delta + 1])
				inewel = self.__d_words.get(new_el.lower(), -1)
				if inewel == -1:
					inewel = len(self.__l_els_here)
					self.__d_words[new_el.lower()] = inewel
					self.__l_els_here.append(new_el)
					new_bits = np.round_(new_vals).astype(np.uint8)
					new_bits = np.array(self.create_closest_unique_bits(new_vals, new_bits), dtype=np.uint8)
					self.__nd_word_bin = np.concatenate((self.__nd_word_bin,
														 np.expand_dims(new_bits, axis=0)), axis=0)
					self.__l_els_stats.append(nt_el_stats(	el=new_el, bglove=False, avg_hd=avg_hd, num_hits=1,
															bitvals=new_vals, bitvec=new_bits,
															l_iphrases=[igphrase]))
				else:
					# prev_new_el = self.__l_els_here[inewel]
					els_stats = self.__l_els_stats[inewel]
					self.remove_unique_bits(els_stats.bitvec) # put back in the create_closest_unique_bits call a few lines down
					new_num_hits = els_stats.num_hits + 1
					old_cd = (c_bitvec_size - els_stats.avg_hd) / c_bitvec_size
					new_cd = (c_bitvec_size - avg_hd) / c_bitvec_size
					wold = old_cd * els_stats.num_hits
					avg_hd = ((avg_hd * new_cd) + (els_stats.avg_hd * wold)) / (new_cd + wold)
					new_vals = ((new_vals * new_cd) + (els_stats.bitvals * wold)) / (new_cd + wold)
					new_bits = np.round_(new_vals).astype(np.uint8)
					new_bits = np.array(self.create_closest_unique_bits(new_vals, new_bits), dtype=np.uint8)
					self.__nd_word_bin[inewel, :] = new_bits
					self.alert_iel_changed(inewel, new_bits)
					self.__l_els_stats[inewel] = nt_el_stats(	el=new_el, bglove=False, avg_hd=avg_hd,
																num_hits=new_num_hits,
																bitvals=new_vals, bitvec=new_bits,
																l_iphrases=els_stats.l_iphrases+[igphrase])
				# end if/else new_el seen before or not
				l_mults.append(nt_mult_el(el=new_el, iel=inewel, pos=pos, len=delta+1))
			# end for pos along phrase
		#end delta/number of words in new_el
		for num_mults in range(1, len(l_mults)+1):
			for ticomb in itertools.combinations(range(len(l_mults)), num_mults):
				l_used = [False for _ in phrase]
				l_new_iels = copy.deepcopy(l_phrase_iels)
				b_comb_valid = True
				for icomb in ticomb:
					mult = l_mults[icomb]
					for pos in range(mult.pos, mult.pos+mult.len):
						if l_used[pos]:
							b_comb_valid = False
							break
						l_used[pos] = True
						l_new_iels[pos] = mult.iel if pos == mult.pos else -1
					if not b_comb_valid:
						break
				if b_comb_valid:
					l_phrase_iels_new = filter(lambda a: a != -1, l_new_iels)
					self.__phraseperms.add_perm(igphrase, l_phrase_iels_new)
					pass
				pass
	#end fn find_pair_bins for phrase


	def learn_pair_bins(self):
		# nt_new_el = collections.namedtuple('nt_new_el', 'el, avg_hd, num_hits, bitvals')
		assert False, 'unused code suspected.'
		d_new_els, l_new_els = dict(), []
		num_lens = len(self.__iphrase_by_len)
		for delta in range(1,3):
			for len1 in range(num_lens-delta):
				if self.__iphrase_by_len[len1] == [] or self.__iphrase_by_len[len1+delta] == []:
					continue
				nd_bits_db = self.__ndbits_by_len[len1]
				for pos in range(len1):
					for iphrase_big in self.__iphrase_by_len[len1+delta]:
						phrase = self.__phrase_mgr.get_phrase(iphrase_big)
						# phrase = self.__l_phrases[iphrase_big]
						nd_hd = np.zeros(nd_bits_db.shape[0], dtype=int)
						for iword_big, el in enumerate(phrase):
							# bskip = False
							if iword_big - pos in range(delta+1): continue
							# if iword_big == pos or iword_big == pos+1: continue
							iword_small = iword_big if iword_big < pos else (iword_big - delta)
							slice_iword = nd_bits_db[:, iword_small, :]
							wid = self.__d_words.get(el.lower(), -1)
							wbits = self.__nd_word_bin[wid]
							nd_hd_iword = np.sum(np.not_equal(wbits, slice_iword), axis=1)
							nd_hd += nd_hd_iword
						idx_of_hd_winners = np.argpartition(nd_hd, c_num_ham_winners)[:c_num_ham_winners]
						hd_of_winners = nd_hd[idx_of_hd_winners]
						iwinners = np.argsort(hd_of_winners)
						hd_idx_sorted = idx_of_hd_winners[iwinners]
						hd_of_winners_sorted = hd_of_winners[iwinners]
						avg_hd = (np.sum(hd_of_winners_sorted / divider) / divider_sum) / (len1-1)
						l_closest = []
						for iclose in hd_idx_sorted.tolist():
							iphrase = self.__iphrase_by_len[len1][iclose]
							# l_closest.append(self.__l_phrases[iphrase])
							l_closest.append(self.__phrase_mgr.get_phrase(iphrase))
						slice_iword = nd_bits_db[:, pos, :]
						obits = slice_iword[hd_idx_sorted]
						new_vals = np.sum(obits.transpose() / divider, axis=1) / divider_sum
						new_bits = np.round_(new_vals).astype(np.uint8)
						devi = np.average(np.not_equal(new_bits, obits))
						# std_dev = np.average(np.std(obits, axis=0))
						std_dev = np.average(
							np.minimum(np.count_nonzero(obits, axis=0), c_bitvec_size - np.count_nonzero(obits, axis=0)))
						new_el = ' '.join(phrase[pos:pos+delta+1])
						inewel = d_new_els.get(new_el, -1)
						if inewel == -1:
							d_new_els[new_el] = len(l_new_els)
							l_new_els.append(nt_new_el(el=new_el, avg_hd=avg_hd, num_hits=1, bitvals=new_vals, devi=devi))
						else:
							prev_new_el = l_new_els[inewel]
							new_num_hits = prev_new_el.num_hits + 1
							new_avg_hd = (avg_hd + (prev_new_el.avg_hd * prev_new_el.num_hits)) / new_num_hits
							new_devi = (devi + (prev_new_el.devi * prev_new_el.num_hits)) / new_num_hits
							new_bitvals = (new_vals + (prev_new_el.bitvals * prev_new_el.num_hits)) / new_num_hits
							l_new_els[inewel] = nt_new_el(	el=new_el, avg_hd=new_avg_hd, num_hits=new_num_hits,
															bitvals=new_bitvals, devi=new_devi)
					# end loop over phrases of the bigger len
				# end loop over pos (i.e. first two words, second etc.
			# end loop over lens
		best_els = sorted(l_new_els, key=lambda x: x.avg_hd)
		print('sorted')
	# end class fn

	def register_notific(self, notific):
		self.__l_notifics.append(notific)

	def alert_iel_changed(self, iel, new_bits):
		for notific in self.__l_notifics:
			notific.iel_bitvec_changed(iel, new_bits)