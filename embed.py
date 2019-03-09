"""
This module is a stand-alone pre-processor for the agent project

"""
from __future__ import print_function
import csv
import sys
import os
import math
import random
from os.path import expanduser
from shutil import copyfile
import numpy as np
import copy

c_num_gloves = 1000 # 10000 # 400000
c_max_deps = 4
c_dep_vec_factor = 0.1
c_max_samples = 5000

glove_fn = '/devlink2/data/glove/glove.6B.50d.txt'
c_fnt_dict = '~/tmp/glv_bin_dict_small.txt'
c_phrase_freq_fnt = '~/tmp/adv_phrase_freq.txt'
c_phrase_fnt = '~/tmp/adv_phrases.txt'
c_example_word  = 'the'

g_word_vec_len = 0

def load_word_dict():
	global g_word_vec_len
	glove_fh = open(glove_fn, 'rb')
	glove_csvr = csv.reader(glove_fh, delimiter=' ', quoting=csv.QUOTE_NONE)
	
	word_dict, l_vecs, s_word_bit_db = {}, [], set()
	for irow, row in enumerate(glove_csvr):
		word = row[0]
		vec = [float(val) for val in row[1:]]
		l_vecs.append(vec)
		word_dict[word] = irow
		if irow >= c_num_gloves-1:
			break
		# print(row)

	nd_vecs = np.array(l_vecs)
	# glove_fh.seek(0)
	nd_median = np.median(nd_vecs, axis=0)
	nd_bits = np.where(nd_vecs > nd_median, np.ones_like(nd_vecs), np.zeros_like(nd_vecs)).astype(np.int)
	for ivec, nd_one_bits in enumerate(nd_bits):
		bits = tuple(nd_one_bits)
		if bits in s_word_bit_db:
			nd_diff = np.abs(nd_vecs[ivec] - nd_median)
			arglist = np.argsort(nd_diff)
			bfound = False
			for ibit in arglist:
				bits2 = list(bits)
				bits2[ibit] = 1 ^ bits[ibit]
				if tuple(bits2) not in s_word_bit_db:
					nd_bits[ivec, :] = np.array(bits2)
					bits = bits2
					bfound = True
					break
			assert bfound, 'changed all bits but could not find a unique'

		s_word_bit_db.add(tuple(bits))


	assert len(l_vecs) == len(s_word_bit_db), 'Error. word bits db not unique'
	glove_fh.close()
	# g_word_vec_len = len(word_dict[c_example_word])
	return word_dict, nd_bits

def load_sample_texts(phrase_freq_fnt, phrase_fnt):
	fn = expanduser(phrase_freq_fnt)
	fnw = expanduser(phrase_fnt)
	# try:
	if True:
		with open(fn, 'rb') as o_fhr:
			fhw = open(fnw, 'wb')
			csvw = csv.writer(fhw, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
			csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
			_, _, version_str, _, snum_items = next(csvr)
			# _, snum_els = next(csvr)
			version, num_items = int(version_str), int(snum_items)
			if version != 1:
				raise IOError
			for irow, row in enumerate(csvr):
				if irow >= num_items or irow >= c_max_samples:
					break
				if irow % 2 == 1: continue
				phrase = row[2:]
				# l_words = []
				# for el in phrase:
				# 	l_words += [w for w in el.split()]
				l_words = [w for el in phrase for w in el.split()]
				csvw.writerow(l_words)





def save_word_db(d_words, nd_bit_db, fnt_dict):
	fn = expanduser(fnt_dict)

	if os.path.isfile(fn):
		copyfile(fn, fn + '.bak')
	fh = open(fn, 'wb')
	csvw = csv.writer(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
	csvw.writerow(['Glv Dict', 'Version', '2'])
	csvw.writerow(['Num Els:', len(d_words)])
	csvw.writerow(['el', 'eid', 'bitvec'])
	csvw.writerow(['bglove', 'bassigned', 'avg_hd', 'num_hits', 'bitvals'])
	for kword, virow in d_words.iteritems():
		csvw.writerow([kword, virow] + nd_bit_db[virow].tolist())
		csvw.writerow([True, True, -1.0, 0, []])

	fh.close()

def make_var_list(l_phrases):
	l_vars = ()
	vars_dict = dict()
	for iphrase, phrase in enumerate(l_phrases):
		for iel, el in enumerate(phrase):
			src_pos = vars_dict.get(el, ())
			if src_pos == ():
				vars_dict[el] = (iphrase, iel)
			else:
				src_iphrase, src_iel = src_pos
				l_vars += (src_iphrase, src_iel, iphrase, iel),
	return l_vars

def make_canon_var_list(l_src_phrases):
	def cmp_quads(q1, q2):
		if q1[0] > q2[0]:
			return 1
		if q1[0] < q2[0]:
			return -1
		if q1[1] > q2[1]:
			return 1
		if q1[1] < q2[1]:
			return -1
		if q1[3] > q2[3]:
			return 1
		if q1[3] < q2[3]:
			return -1
		return 0
	l_iorder = range(len(l_src_phrases))
	b_keep_going = True
	isanity = 100
	swap_set = set()
	while b_keep_going:
		if isanity <= 0:
			print('make_canon_var_list in endless loop.')
			return l_vars, l_iorder
		l_phrases = [l_src_phrases[i] for i in l_iorder]
		l_vars = make_var_list(l_phrases)
		l_vars = sorted(l_vars, cmp=cmp_quads)
		l_bmentioned = [False for _ in l_phrases]
		l_bmentioned[0] = True
		highest_mentioned = 0
		b_keep_going = False
		for one_var in l_vars:
			i_dest_phrase = one_var[2]
			if i_dest_phrase == 0: continue # don't move the first phrase
			if not l_bmentioned[i_dest_phrase]:
				if highest_mentioned > i_dest_phrase:
					assert highest_mentioned != 0
					swap_pair = (i_dest_phrase, highest_mentioned)
					if swap_pair in swap_set:
						print('looping badly.')
						return l_vars, l_iorder
					swap_set.add(swap_pair)
					t = l_iorder[i_dest_phrase]
					l_iorder[i_dest_phrase] = l_iorder[highest_mentioned]
					l_iorder[highest_mentioned] = t
					b_keep_going = True
					break
				highest_mentioned = i_dest_phrase
				l_bmentioned[i_dest_phrase] = True

	return l_vars, l_iorder

def test_cannon():
	random.seed(9329)
	src = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
	lctot = 0; lstot = 0
	for itest in range(100):
		print('test num', itest)
		num_phrases = random.randint(2, 7)
		l_phrases = []
		for iphrase in range(num_phrases):
			plen = random.randint(3, 12)
			l_phrases.append([random.choice(src) for _ in range(plen)])
		saved_order = []; saved_vars = []
		cannon_set = set(); simple_set = set()
		for ishuffle in range(2 * math.factorial(num_phrases - 1)):
			shuf_stick = range(1, num_phrases)
			# if saved_order != []:
			random.shuffle(shuf_stick)
			l_iorder = [0] + shuf_stick
			l_shuf_phrases = [l_phrases[i] for i in l_iorder]
			l_vars, l_cannon_order = make_canon_var_list(l_shuf_phrases)
			l_cannon_shuf_order = [l_iorder[i] for i in l_cannon_order]
			cannon_set.add((tuple(l_cannon_shuf_order), tuple(l_vars)))
			simple_set.add((tuple(l_iorder), tuple(l_vars)))
			# if saved_order == []:
			# 	saved_order = l_cannon_shuf_order
			# 	saved_vars = l_vars
			# else:
			# 	print('l_cannon_shuf_order', l_cannon_shuf_order, 'saved_order', saved_order)
			# 	if l_cannon_shuf_order != saved_order:
			# 		print('order not the same!')
			# 	else:
			# 		if l_vars != saved_vars:
			# 			print('saved order the same but not the vars')
		lc = len(cannon_set); ls = len(simple_set)
		print('cannon', lc, 'simple', ls)
		lctot += lc; lstot += ls
	print('totals. cannon', lctot, 'simple', lstot)


def main():
	test_cannon()
	# make_canon_var_list(((1, 0, 2, 0), (0, 1, 3, 4), (0, 0, 3, 0)))
	word_dict, nd_vecs = load_word_dict()
	exit()
	save_word_db(word_dict, nd_vecs, c_fnt_dict)

	# load_sample_texts(c_phrase_freq_fnt, c_phrase_fnt)

	print('done')

if __name__ == "__main__":
	# create_wd()
    main()
