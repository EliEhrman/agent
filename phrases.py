"""
Maintains the list of all phrases seen.
The list is unique
Other modules should not store the text but refer to a phrase by its hpm which is the handle provided by this module
hpm might also be called rphrase, iphrase, i_all_phrases and such like in the other modules which are clients to
this one.


"""

import csv
from os.path import expanduser


class cl_phrase_mgr(object):
	def __init__(self, b_restart_from_glv, phrases_fnt):
		self.__l_phrases = [] # type : List[List[str]] # The list of phrases. Unique. For nl, phrase is comprised of single words.
		self.__map_phrase_to_rphrase = dict() # type : Dict[str, int] # map the text of the phrase
		self.__phraseperms = None
		self.__b_restart_from_glv = b_restart_from_glv
		self.__l_rule_name = []
		self.__phrases_fnt = phrases_fnt

	def set_phraseperms(self, phraseperms):
		self.__phraseperms = phraseperms

	def add_phrase(self, phrase_src, creating_rule_name=''):
		phrase = [w for lw in [el.split() for el in phrase_src] for w in lw]
		rphrase = self.__map_phrase_to_rphrase.get(tuple(phrase), -1)
		if rphrase == -1:
			rphrase = len(self.__l_phrases)
			self.__l_phrases.append(phrase)
			self.__map_phrase_to_rphrase[tuple(phrase)] = rphrase
			self.__phraseperms.add_new_phrase(rphrase)
		if creating_rule_name != '':
			grow = 1 + rphrase - len(self.__l_rule_name)
			if grow > 0:
				self.__l_rule_name += [[] for _ in range(grow)]
			if creating_rule_name not in self.__l_rule_name[rphrase]:
				self.__l_rule_name[rphrase].append(creating_rule_name)

		return rphrase

	def get_rphrase(self, phrase_src):
		phrase = [w for lw in [el.split() for el in phrase_src] for w in lw]
		return self.__map_phrase_to_rphrase.get(tuple(phrase), -1)

	def get_phrase(self, rphrase):
		assert rphrase < len(self.__l_phrases), 'Error! rphrase is longer than the length of the list of phrases'
		return self.__l_phrases[rphrase]

	def init_data(self):
		if self.__b_restart_from_glv:
			saved_phrases = self.load_saved_phrases()
			self.load_sample_texts(saved_phrases)
			if self.__phraseperms != None:
				self.__phraseperms.init(self.__l_rule_name)
		else:
			if self.__phraseperms != None:
				self.__phraseperms.init_from_load()


	def load_saved_phrases(self):
		saved_phrases = []
		fn = expanduser(self.__phrases_fnt)
		try:
			with open(fn, 'rb') as o_fhr:
				csvr = csv.reader(o_fhr, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				_, snum_els = next(csvr)
				version, num_els = int(version_str), int(snum_els)
				if version != 1:
					raise IOError
				for irow, row in enumerate(csvr):
					saved_phrases.append(row)

		except IOError:
			print('Cannot open or read ', fn)

		return saved_phrases

	def load_sample_texts(self, saved_phrases):
		for phrase_data in saved_phrases:
			self.add_phrase(phrase_data[1].split(), phrase_data[0])

	def get_num_phrases(self):
		return len(self.__l_phrases)