import bitvec
from bitvec import c_bitvec_size as bitvec_size
import csv
from os.path import expanduser
import numpy as np
import itertools
import collections
import copy

c_phrase_fnt = '~/tmp/adv_phrases.txt'

# bitvals are the values that are rounded to make the bits. Kept in this form because uniqueness only calculated at insertion into main dict
# avg_hd is the average hd between the phrase minues the el and the corresponding closest phrases of n shorter length
# devi is the deviation of the corresponding bits  to the el in the closest phrases. deviation calculated as average of diff between rounded average and the src bits
nt_new_el = collections.namedtuple('nt_new_el', 'el, avg_hd, devi, num_hits, bitvals')
# bglove, if True, means the el comes from the glove dict and is not not be changed
# l_iphrases is a list of indices into __l_phrases that the el appears in
nt_el_stats = collections.namedtuple('nt_el_stats', 'el, bglove, bassigned, avg_hd, num_hits, l_iphrases, l_idelayed, bitvals, bitvec')
nt_el_stats.__new__.__defaults__ = ('???', False, False, -1.0, 0, None, None, [], np.zeros(bitvec_size, dtype=np.uint8))

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
		self.__ndbits_by_len = [] # bit representation of phrase, ordered by phrase len
		self.__iphrase_by_len = [] # for each len, entry corresponding to __ndbits_by_len, index into l_phrases
		self.__phrase_by_len_idx = [] # for each entry of l_phrases, -1 if unassigned, index into iphrase by len and ndbits_by len otherwise
		self.__l_phrases = [] # type: List(str)
		self.__l_delayed_iphrases = []
		self.__d_words = dict()
		self.__nd_word_bin = None
		self.__l_els_here = []
		self.__l_els_stats = []
		self.load_sample_texts(c_phrase_fnt)
		for num_try_assign in range(c_num_assign_tries):
			num_unassigned = self.assign_unknown_words()
			if num_unassigned == 0:
				break
		self.learn_pair_bins()
		pass

	def add_new_row(self, phrase):
		i_all_phrases = len(self.__l_phrases)
		self.__l_phrases.append(phrase)
		self.__phrase_by_len_idx.append(-1)
		if (len(phrase) + 1) > len(self.__ndbits_by_len):
			l_grow_init = [[] for _ in range((1 + len(phrase) - len(self.__ndbits_by_len)))]
			self.__ndbits_by_len += l_grow_init
			self.__iphrase_by_len += copy.deepcopy(l_grow_init)
			# by_len_iphrase = 0
			del l_grow_init
		self.process_new_row(i_all_phrases)

	def process_new_row(self, i_all_phrases):
		phrase = self.__l_phrases[i_all_phrases]
		b_add_now = True
		nd_phrase = np.zeros((len(phrase), bitvec_size), dtype=np.uint8)
		num_unassigned, i_last_unassigned = 0, -1
		for iword, word in enumerate(phrase):
			iel = self.__d_words.get(word.lower(), -1)
			if iel == -1:
				iel = len(self.__l_els_stats)
				self.__d_words[word.lower()] = iel
				el_stats = nt_el_stats(el=word, l_iphrases=[i_all_phrases], l_idelayed=[])
				self.__l_els_stats.append(el_stats)
				self.__l_els_here.append(word)
				glv_wid = self.__bitvec_mgr.get_el_id(word.lower())
				if glv_wid == -1:
					b_add_now = False
					num_unassigned += 1
					i_last_unassigned = iword
					nd_wbits = np.zeros(bitvec_size, dtype=np.uint8)
				else:
					nd_wbits = self.__bitvec_mgr.get_bin_by_id(glv_wid)
					el_stats = el_stats._replace(bglove=True, bassigned=True, bitvec=nd_wbits)
					nd_phrase[iword, :] = nd_wbits
				if self.__nd_word_bin == None:
					self.__nd_word_bin = np.expand_dims(nd_wbits, axis=0)
				else:
					iel = self.__nd_word_bin.shape[0]
					self.__nd_word_bin = np.concatenate((self.__nd_word_bin,
														 np.expand_dims(nd_wbits, axis=0)), axis=0)
				del nd_wbits, glv_wid
			else:  # if word already seen
				el_stats = self.__l_els_stats[iel]  # ._replace()
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
			for idelayed in el_stats.l_idelayed:
				if idelayed == i_all_phrases:
					el_stats.l_idelayed.remove(i_all_phrases)
				else:
					self.process_new_row(idelayed)
			del iel, el_stats, word


	# end process unassigned row

	def load_sample_texts(self, phrase_fnt):
		fn = expanduser(phrase_fnt)
		# try:
		if True:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				for row in csvr:
					self.add_new_row(row)
				# end loop over rows


	def dbg_closest_words(self, bins):
		l_closest = []

		nd_hd_iword = np.sum(np.not_equal(bins, self.__nd_word_bin), axis=1)
		idx_of_hd_winners = np.argpartition(nd_hd_iword, c_num_ham_winners)[:c_num_ham_winners]
		hd_of_winners = nd_hd_iword[idx_of_hd_winners]
		iwinners = np.argsort(hd_of_winners)
		hd_idx_sorted = idx_of_hd_winners[iwinners]
		for iclosest in hd_idx_sorted:
			l_closest.append(self.__l_els_here[iclosest])

	def assert_glove_uniqueness(self, bitvec):
		print('Implement shoving a non-glove bitvec out of the way if already taken by a glove')

	def assign_word_from_closest(self, phrase, iel, word, i_last_miss, nd_phrase):
		els_stats = self.__l_els_stats[iel]
		plen = len(phrase)
		nd_bits_db = self.__ndbits_by_len[plen]
		if nd_bits_db in [None, []]:
			return False
		nd_hd = np.zeros(nd_bits_db.shape[0], dtype=int)
		for iword, word in enumerate(phrase):
			if iword == i_last_miss: continue
			slice_iword = nd_bits_db[:, iword, :]
			wid = self.__d_words.get(word.lower(), -1)
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
			new_num_hits = els_stats.num_hits + 1
			old_cd = (bitvec_size - els_stats.avg_hd) / bitvec_size
			new_cd = (bitvec_size - avg_hd) / bitvec_size
			wold = old_cd * els_stats.num_hits
			avg_hd = ((avg_hd*new_cd) + (els_stats.avg_hd*wold))/(new_cd+wold)
			# avg_hd = (avg_hd + (els_stats.avg_hd * els_stats.num_hits)) / new_num_hits
			# new_devi = (devi + (els_stats.devi * els_stats.num_hits)) / new_num_hits
			new_vals = ((new_vals*new_cd) + (els_stats.bitvals * wold)) / (new_cd+wold)
			# new_vals = (new_vals + (els_stats.bitvals * els_stats.num_hits)) / new_num_hits
		else:
			new_num_hits = 1

		new_bits = np.round_(new_vals).astype(np.uint8)
		new_bits = self.create_closest_unique_bits(new_vals, new_bits)
		nd_phrase[i_last_miss, :] = new_bits
		# self.__ndbits_by_len[plen] = np.concatenate((self.__ndbits_by_len[plen],
		# 											 np.expand_dims(nd_phrase, axis=0)), axis=0)

		del phrase

		self.__l_els_stats[iel] = els_stats._replace(bassigned=True, avg_hd=avg_hd, num_hits=new_num_hits, bitvals=new_vals, bitvec=new_bits)

		# now you have to apply binary changes to all phrases that this word appears in
		for iphrase in els_stats.l_iphrases:
			by_len_idx = self.__phrase_by_len_idx[iphrase]
			if by_len_idx == -1: continue
			phrase = self.__l_phrases[iphrase]
			bfix, plen = True, len(phrase)
			nd_phrase2 = np.zeros((plen, bitvec_size), dtype=np.uint8)

			for iword, word in enumerate(phrase):
				iel = self.__d_words.get(word.lower(), -1)
				el_stats = self.__l_els_stats[iel]
				if not el_stats.bassigned:
					bfix = False
					break
				nd_phrase2[iword, :] = els_stats.bitvals

			if bfix:
				self.__ndbits_by_len[plen][by_len_idx, :, :] = nd_phrase
		return True



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
			# nt_el_stats = collections.namedtuple('nt_el_stats',
			# 									 'el, bglove, avg_hd, devi, num_hits, bitvals, l_iphrases')
			self.__l_els_stats.append(nt_el_stats(el=word, bglove=False, avg_hd=-1., num_hits=1,
												  bitvals=[new_vals], l_iphrases=[idelayed]))

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