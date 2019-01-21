import timeit
import collections
from bitvecdb import bitvecdb

nt_prof = collections.namedtuple('nt_prof', 'name, total_time, num_calls, b_in_time, start_time')
d_profs = dict()

def profile_decor(fn):
	def wr(*args, **kwargs):
		global d_profs
		# print('calling function:', fn.func_name)
		prof_rec = d_profs.get(fn.func_name, None)
		if prof_rec == None:
			prof_rec = nt_prof(name=fn.func_name, total_time=0., num_calls=0, b_in_time=False, start_time=-1.0)
			d_profs[fn.func_name] = prof_rec
		s = timeit.default_timer()
		b_top = False
		if not prof_rec.b_in_time:
			b_top = True
			prof_rec = prof_rec._replace(b_in_time = True)
			d_profs[fn.func_name] = prof_rec
		r = fn(*args, **kwargs)
		if b_top:
			prof_rec = prof_rec._replace(total_time = prof_rec.total_time + timeit.default_timer() - s)
			# prof_rec.total_time += timeit.default_timer() - s
			prof_rec = prof_rec._replace(b_in_time = False)
			# prof_rec.b_in_time = False
		prof_rec = prof_rec._replace(num_calls=prof_rec.num_calls+1)
		# prof_rec.num_calls += 1
		d_profs[fn.func_name] = prof_rec
		return r

	return wr

def profile_start(pname):
	prof_rec = d_profs.get(pname, None)
	if prof_rec == None:
		prof_rec = nt_prof(name=pname, total_time=0., num_calls=0, b_in_time=True, start_time=-1.0)
	else:
		prof_rec = prof_rec._replace(b_in_time=True)
	prof_rec = prof_rec._replace(start_time=timeit.default_timer())
	d_profs[pname] = prof_rec

def profile_end(pname):
	prof_rec = d_profs.get(pname, None)
	if prof_rec == None:
		return
	if not prof_rec.b_in_time:
		return
	prof_rec = prof_rec._replace(total_time=prof_rec.total_time + timeit.default_timer()-prof_rec.start_time)
	prof_rec = prof_rec._replace(num_calls=prof_rec.num_calls+1)
	prof_rec = prof_rec._replace(b_in_time=False)
	d_profs[pname] = prof_rec

def convert_charvec_to_arr(bin, size=-1):
	if size == -1:
		size = len(bin)
	bin_arr = bitvecdb.charArray(size)
	for ib in range(size): bin_arr[ib] = chr(bin[ib])
	return bin_arr


def convert_intvec_to_arr(bin, size=-1):
	if size == -1:
		size = len(bin)
	bin_arr = bitvecdb.intArray(size)
	for ib in range(size): bin_arr[ib] = int(bin[ib])
	return bin_arr

def full_split(stmt):
	return [w for lw in [el.split() for el in stmt] for w in lw]

def convert_phrase_to_word_list(stmt):
	return [el[1] for el in stmt]
