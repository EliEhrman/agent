"""
This module is a stand-alone pre-processor for the agent project

"""
from __future__ import print_function
import csv
import sys
import os
# import math
# import random
from os.path import expanduser
from shutil import copyfile
import numpy as np
import copy

c_num_gloves = 10000 # 400000
c_max_deps = 4
c_dep_vec_factor = 0.1
c_max_samples = 5000

glove_fn = '/devlink2/data/glove/glove.6B.50d.txt'
c_fnt_dict = '~/tmp/glv_bin_dict.txt'
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
		if irow > c_num_gloves:
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

def main():
	word_dict, nd_vecs = load_word_dict()
	save_word_db(word_dict, nd_vecs, c_fnt_dict)

	# load_sample_texts(c_phrase_freq_fnt, c_phrase_fnt)

	print('done')

if __name__ == "__main__":
	# create_wd()
    main()
