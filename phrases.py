"""
Maintains the list of all phrases seen.
The list is unique
Other modules should not store the text but refer to a phrase by its hpm which is the handle provided by this module
hpm might also be called rphrase, iphrase, i_all_phrases and such like in the other modules which are clients to
this one.


"""

class cl_phrase_mgr(object):
	def __init__(self):
		self.__l_phrases = [] # type : List[List[str]] # The list of phrases. Unique. For nl, phrase is comprised of single words.
		self.__map_phrase_to_rphrase = dict() # type : Dict[str, int] # map the text of the phrase
		self.__phraseperms = None

	def set_phraseperms(self, phraseperms):
		self.__phraseperms = phraseperms

	def add_phrase(self, phrase_src):
		phrase = [w for lw in [el.split() for el in phrase_src] for w in lw]
		rphrase = self.__map_phrase_to_rphrase.get(tuple(phrase), -1)
		if rphrase != -1:
			return rphrase
		rphrase = len(self.__l_phrases)
		self.__l_phrases.append(phrase)
		self.__map_phrase_to_rphrase[tuple(phrase)] = rphrase
		self.__phraseperms.add_new_phrase(rphrase)
		return rphrase

	def get_rphrase(self, phrase):
		return self.__map_phrase_to_rphrase.get(tuple(phrase), -1)

	def get_phrase(self, rphrase):
		assert rphrase < len(self.__l_phrases), 'Error! rphrase is longer than the length of the list of phrases'
		return self.__l_phrases[rphrase]
