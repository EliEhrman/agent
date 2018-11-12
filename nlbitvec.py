import bitvec
from bitvec import c_bitvec_size as bitvec_size
import csv
from os.path import expanduser
import numpy as np
import itertools
import collections

c_phrase_fnt = '~/tmp/adv_phrases.txt'

# bitvals are the values that are rounded to make the bits. Kept in this form because uniqueness only calculated at insertion into main dict
# avg_hd is the average hd between the phrase minues the el and the corresponding closest phrases of n shorter length
# devi is the deviation of the corresponding bits  to the el in the closest phrases. deviation calculated as average of diff between rounded average and the src bits
nt_new_el = collections.namedtuple('nt_new_el', 'el, avg_hd, devi, num_hits, bitvals')

c_bitvec_neibr_divider_offset = 5
c_num_ham_winners = 30
c_num_assign_tries = 5

divider = np.array(
	range(c_bitvec_neibr_divider_offset,c_num_ham_winners + c_bitvec_neibr_divider_offset),
	np.float32)
divider_sum = np.sum(1. / divider)


class cl_nlb_mgr(object):
	def __init__(self, bitvec_mgr):
		self.__bitvec_mgr = bitvec_mgr
		self.__ndbits_by_len = []
		self.__iphrase_by_len = [] # for each len, entry corresponding to __ndbits_by_len, index into l_phrases
		self.__l_phrases = []
		self.__l_delayed_iphrases = []
		self.__d_words = dict()
		self.__nd_word_bin = None
		self.__l_els_here = []
		self.load_sample_texts(c_phrase_fnt)
		for num_try_assign in range(c_num_assign_tries):
			num_unassigned = self.assign_unknown_words()
			if num_unassigned == 0:
				break
		self.learn_pair_bins()
		pass

	def load_sample_texts(self, phrase_fnt):
		fn = expanduser(phrase_fnt)
		# try:
		if True:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				for row in csvr:
					i_all_phrases = len(self.__l_phrases)
					self.__l_phrases.append(row)
					if (len(row) + 1) > len(self.__ndbits_by_len):
						l_grow_init = [[] for _ in range((1 + len(row) - len(self.__ndbits_by_len)))]
						self.__ndbits_by_len += l_grow_init
						self.__iphrase_by_len += l_grow_init
						by_len_iphrase = 0
					else:
						if self.__ndbits_by_len[len(row)] == []:
							by_len_iphrase = 0
						else:
							by_len_iphrase = self.__ndbits_by_len[len(row)].shape[0]
					b_add_now = True
					nd_phrase = np.zeros((len(row), bitvec_size), dtype=np.uint8)
					for iword, word in enumerate(row):
						wid = self.__bitvec_mgr.get_el_id(word.lower())
						if wid == -1:
							b_add_now = False
							self.__l_delayed_iphrases += [i_all_phrases]
						else:
							nd_wbits = self.__bitvec_mgr.get_bin_by_id(wid)
							nd_phrase[iword, :] = nd_wbits
							i_word_here = self.__d_words.get(word.lower(), -1)
							if i_word_here == -1:
								if self.__nd_word_bin == None:
									i_word_here = 0
									self.__nd_word_bin = np.expand_dims(nd_wbits, axis=0)
								else:
									i_word_here = self.__nd_word_bin.shape[0]
									self.__nd_word_bin = np.concatenate((self.__nd_word_bin,
																		 np.expand_dims(nd_wbits, axis=0)), axis=0)
								self.__d_words[word.lower()] = i_word_here
								self.__l_els_here.append(word)
					if b_add_now:
						self.__iphrase_by_len[len(row)].append(i_all_phrases)
						if by_len_iphrase == 0:
							self.__ndbits_by_len[len(row)] = np.expand_dims(nd_phrase, axis=0)
						else:
							self.__ndbits_by_len[len(row)] = np.concatenate((self.__ndbits_by_len[len(row)],
																			np.expand_dims(nd_phrase, axis=0)), axis=0)


	def dbg_closest_words(self, bins):
		l_closest = []

		nd_hd_iword = np.sum(np.not_equal(bins, self.__nd_word_bin), axis=1)
		idx_of_hd_winners = np.argpartition(nd_hd_iword, c_num_ham_winners)[:c_num_ham_winners]
		hd_of_winners = nd_hd_iword[idx_of_hd_winners]
		iwinners = np.argsort(hd_of_winners)
		hd_idx_sorted = idx_of_hd_winners[iwinners]
		for iclosest in hd_idx_sorted:
			l_closest.append(self.__l_els_here[iclosest])

	def create_closest_unique_bits(self, new_vals, new_bits):
		s_word_bit_db = self.__bitvec_mgr.get_s_word_bit_db()
		if tuple(new_bits) in s_word_bit_db:
			bfound = False
			while True:
				can_flip = np.argsort(np.square(new_vals - 0.5))
				for num_flip in range(1, bitvec_size):
					try_flip = can_flip[:num_flip]
					l = [list(itertools.combinations(try_flip, r)) for r in range(num_flip + 1)]
					lp = [item for sublist in l for item in sublist]
					for p in lp:
						pbits = list(new_bits)
						for itf in try_flip:
							pbits[itf] = 1 if itf in p else 0
						if tuple(pbits) not in s_word_bit_db:
							new_bits = pbits
							bfound = True
							break
					if bfound:
						break
				if bfound:
					break
		self.__bitvec_mgr.add_unique_bits_ext(new_bits)
		return new_bits

	def assign_unknown_words(self):
		l_failed_assign = []
		for idelayed in self.__l_delayed_iphrases:
			phrase = self.__l_phrases[idelayed]
			plen = len(phrase)
			nd_phrase = np.zeros((plen, bitvec_size), dtype=np.uint8)
			for iword, word in enumerate(phrase):
				miss_count, i_last_miss = 0, -1
				wid = self.__d_words.get(word.lower(), -1)
				if wid == -1:
					miss_count += 1
					i_last_miss = iword
				else:
					nd_phrase[iword, :] = self.__nd_word_bin[wid]

				if miss_count > 1:
					break
			if miss_count == 0:
				continue # happens because word has since been assigned
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
			# std_dev = np.average(np.minimum(np.count_nonzero(obits, axis=0), bitvec_size - np.count_nonzero(obits, axis=0)))
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
		self.__l_delayed_iphrases = l_failed_assign
		return len(l_failed_assign)

	def learn_pair_bins(self):
		# nt_new_el = collections.namedtuple('nt_new_el', 'el, avg_hd, num_hits, bitvals')
		d_new_els, l_new_els = dict(), []
		num_lens = len(self.__iphrase_by_len)
		for delta in range(1,3):
			for len1 in range(num_lens-delta):
				if self.__iphrase_by_len[len1] == [] or self.__iphrase_by_len[len1+delta] == []:
					continue;
				nd_bits_db = self.__ndbits_by_len[len1]
				for pos in range(len1):
					for iphrase_big in self.__iphrase_by_len[len1+delta]:
						phrase = self.__l_phrases[iphrase_big]
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
							l_closest.append(self.__l_phrases[iphrase])
						slice_iword = nd_bits_db[:, pos, :]
						obits = slice_iword[hd_idx_sorted]
						new_vals = np.sum(obits.transpose() / divider, axis=1) / divider_sum
						new_bits = np.round_(new_vals).astype(np.uint8)
						devi = np.average(np.not_equal(new_bits, obits))
						# std_dev = np.average(np.std(obits, axis=0))
						std_dev = np.average(
							np.minimum(np.count_nonzero(obits, axis=0), bitvec_size - np.count_nonzero(obits, axis=0)))
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