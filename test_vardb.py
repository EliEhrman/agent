"""
Stand-alone module
Tests the low-level c lib vardb which is called by bitvecdb
"""
from __future__ import print_function
import csv
import numpy as np
from os.path import expanduser

glove_fnt = '~/data/glove/glove.6B.50d.txt'
c_num_gloves = 100000 # 10000 # 400000
c_bitvec_size = 50
c_num_bits_padded = 64
c_num_nibs = c_num_bits_padded / 4
c_samples_fnt = '~/tmp/vardb_samples.txt'

g_samples = ['where are you', 'hit the ball', 'the ball in here is in the water', 'the cat is on the mat', 'the cat is on the table',
			 'the ball is on the mat', 'the ball is on the floor', 'the cat is on the chair', 'the dog is on the mat', 'the ball is on the chair',
			 'the ball is in the box', 'the dog is on the box']
g_queries = ['the cat:50 is on the table:50']

def get_nibs(lnibs):
	v = 0
	for inib, nib in enumerate(lnibs):
		if nib != 0:
			v += 2 ** (3 - inib)
	return hex(v)[2:]

def convert_ones(l_bins):
	str_val = ''
	bins = l_bins + ([0] * (c_num_bits_padded - len(l_bins)))
	for inib in range(c_num_nibs):
		str_val += get_nibs(bins[inib*4:(inib+1)*4])
	return str_val

def load_word_dict():
	global g_word_vec_len
	glove_fn = expanduser(glove_fnt)
	glove_fh = open(glove_fn, 'rb')
	glove_csvr = csv.reader(glove_fh, delimiter=' ', quoting=csv.QUOTE_NONE)

	word_dict, l_vecs, s_word_bit_db = {}, [], set()
	for irow, row in enumerate(glove_csvr):
		word = row[0]
		vec = [float(val) for val in row[1:]]
		l_vecs.append(vec)
		word_dict[word] = irow
		if irow >= c_num_gloves - 1:
			break
	# print(row)

	nd_vecs = np.array(l_vecs)
	# glove_fh.seek(0)
	nd_median = np.median(nd_vecs, axis=0)
	nd_bits = np.where(nd_vecs > nd_median, np.ones_like(nd_vecs), np.zeros_like(nd_vecs)).astype(np.int)
	l_str_vals = []
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
		l_str_vals.append(convert_ones(list(bits)))

		s_word_bit_db.add(tuple(bits))

	return word_dict, l_str_vals

def write_row(fh, word_dict, l_str_vals, sample, bquery):
	lw = sample.split(' ')
	fh.write('1' if bquery else '0')
	fh.write('%03d' % len(lw))
	var_dict = dict()
	for iwc, wc in enumerate(lw):
		lwc = wc.split(':')
		w = lwc[0]
		hd = '00'; var_delta = '00'
		if len(lwc) > 1:
			hd = '%02d' % (int(lwc[1]))
		ivar = var_dict.get(w, -1)
		if ivar == -1:
			var_dict[w] = iwc
		else:
			var_delta = '%02d' % (int(iwc - ivar))
		idx = word_dict.get(w, -1)
		assert idx != -1, ('Error! The word \'%s\' from the samples is not in the glv based dictionary' % w)
		fh.write(l_str_vals[idx] + hd + var_delta)
	fh.write('\n')


def make_samples(word_dict, l_str_vals):
	fn = expanduser(c_samples_fnt)
	fh = open(fn, 'wb')
	for sample in g_samples:
		write_row(fh, word_dict, l_str_vals, sample, bquery=False)
	for sample in g_queries:
		write_row(fh, word_dict, l_str_vals, sample, bquery=True)
	fh.close





def main():
	word_dict, l_str_vals = load_word_dict()
	make_samples(word_dict, l_str_vals)

if __name__ == "__main__":
    main()
