
class cl_phrase_perms(object):
	def __init__(self):
		# iphrase is the local index for the rphrase. It should be the same as rphrase, bit not assuming this for now
		self.__d_rphrase_to_iphrase = dict()
		self.__l_phrase_rphrases = []
		self.__ll_rperms = []
		self.__l_phrase_perms = [] # type: List[List[int]] # list of phrases each a list of el ids from nlbitvec


	def add_new_phrase(self, rphrase):
		iphrase = len(self.__l_phrase_rphrases)
		self.__d_rphrase_to_iphrase[rphrase] = iphrase
		self.__l_phrase_rphrases.append(rphrase)
		# rperm = len(self.__l_phrase_perms)
		self.__ll_rperms.append([])
		# self.__l_phrase_perms.append(l_phrase_eids)

	def add_perm(self, rphrase, l_phrase_eids):
		iphrase = self.__d_rphrase_to_iphrase[rphrase]
		for rperm in self.__ll_rperms[iphrase]:
			if l_phrase_eids == self.__l_phrase_perms[rperm]:
				return
		rperm_new = len(self.__l_phrase_perms)
		self.__ll_rperms[iphrase].append(rperm_new)
		self.__l_phrase_perms.append(l_phrase_eids)
