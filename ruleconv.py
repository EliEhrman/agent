from __future__ import print_function
import sys
import csv
from enum import Enum
from StringIO import StringIO
from os.path import expanduser

conn_type = Enum('conn_type', 'single AND OR start end Insert Remove Modify IF THEN Broadcast replace_with_next, Unique')
rec_def_type = Enum('rec_def_type', 'obj conn var error set like err')

class cl_fixed_rules(object):
	def __init__(self, fn):
		self.__l_rules = []
		self.__l_categories = []
		self.__l_names = []
		self.load_rules(fn)

	def load_rules(self, fn):
		l_rules_data = []
		try:
		# if True:
			with open(fn, 'rb') as fh:
				csvr = csv.reader(fh, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\')
				_, _, version_str = next(csvr)
				if int(version_str) != 1:
					raise ValueError('rules2 rules file', fn, 'version cannot be used. Starting from scratch')
				rule_start_marker = next(csvr)[0]
				if rule_start_marker != 'rules start':
					raise IOError('no rules start marker')
				# for irule in xrange(int(num_rules)):
				while True:
					trule = next(csvr)
					if trule[0] == 'rules end':
						break
					rule_name, category, srule = trule
					srule = self.extract_ml_srule(srule, csvr)
					l_rules_data.append((rule_name, category, srule))
		except ValueError as verr:
			print(verr.args)
		except IOError:
		# except:
			print('Could not open db_len_grps file! Starting from scratch.')
		except:
			print('Unexpected error:', sys.exc_info()[0])
			raise

		for rule_name, category, srule in l_rules_data:
			rule_pre = self.extract_rec_from_str(srule)
			rule, var_dict = [], dict()
			for iel, el in enumerate(rule_pre):
				if el[0] in [rec_def_type.like, rec_def_type.obj] and len(el) > 3:
					var_dict[el[3]] = iel
					rule += [el[:3]]
				elif el[0] == rec_def_type.var:
					rule += [[el[0], var_dict[el[1]]]]
					if len(el) > 2:
						rule[-1] += [el[2]]
				elif el[0] == rec_def_type.conn \
						and el[1] in [conn_type.Insert, conn_type.Modify, conn_type.Broadcast,
									  conn_type.Remove, conn_type.Unique, conn_type.start] \
						and len(el) > 2:
					rule += [el[:2] + [var_dict[e] for e in el[2:]]]
				else:
					rule += [el]

			self.__l_categories.append(category)
			self.__l_rules.append(rule)
			self.__l_names.append(rule_name)

		pass

	def extract_ml_srule(self, srule, csvr):
		ret = ''
		if srule[:3] == 'ml,':
			srule = srule[3:]
			while srule[-4:] != ',mle':
				ret += srule
				srule = next(csvr)[-1]
			ret += srule[:-4]
			return  ret
		return srule

	def extract_rec_from_str(self, srec):
		if srec == '':
			return None

		f = StringIO(srec)
		# csvw = csv.writer(l)
		rec = []
		lelr = csv.reader(f, delimiter=',')
		row = next(lelr)
		for lcvo in row:
			fcvo = StringIO(lcvo)
			lelf = next(csv.reader(fcvo, delimiter=':'))
			if lelf[0] == 'c':
				el = [rec_def_type.conn]
				if lelf[1] == 'a':
					el += [conn_type.AND]
				elif lelf[1] == 'r':
					el += [conn_type.OR]
				elif lelf[1] == 's':
					el += [conn_type.start]
				elif lelf[1] == 'e':
					el += [conn_type.end]
				elif lelf[1] == 'i':
					el += [conn_type.Insert]
				elif lelf[1] == 'u':
					el += [conn_type.Unique]
				elif lelf[1] == 'm':
					el += [conn_type.Modify]
				elif lelf[1] == 'd':
					el += [conn_type.Remove]
				elif lelf[1] == 'f':
					el += [conn_type.IF]
				elif lelf[1] == 't':
					el += [conn_type.THEN]
				elif lelf[1] == 'b':
					el += [conn_type.Broadcast]
				else:
					print('Unknown rec def. Exiting.')
					exit()
				if lelf[1] in ['s', 'i', 'u', 'm', 'd', 'b']:
					if len(lelf) > 2:
						el += [int(v) for v in lelf[2:]]
			elif lelf[0] == 'v':
				el = [rec_def_type.var]
				el += [int(lelf[1])]
				if len(lelf) > 2 and lelf[2] == 'r':
					el += [conn_type.replace_with_next]
			elif lelf[0] == 'o':
				el = [rec_def_type.obj]
				el += [lelf[1]]
				if len(lelf) > 2 and lelf[2] == 'r':
					el += [conn_type.replace_with_next]
			elif lelf[0] == 'l':
				el = [rec_def_type.like]
				el += [lelf[1], float(lelf[2])]
				if len(lelf) > 3:
					el += [int(lelf[3])]

			else:
				el = [rec_def_type.error]
				el += [lelf[1]]

			rec += [el]

		return rec

	def write_rules(self, fnt):
		fnw = expanduser(fnt)
		fhw = open(fnw, 'wb')
		# csvw = csv.writer(fhw, quoting=csv.QUOTE_NONE, escapechar='\\')
		for cat, rname, rule in zip(self.__l_categories, self.__l_names, self.__l_rules):
			# csvw.writerow([rname+'\t'+cat+'\t'+'ml,\n\t\t\t\t\t\t\t\t\t\t,mle'])
			nlstr = '\n\t\t\t\t\t\t\t\t\t\t\t'
			wstr = rname + '\t' + cat + '\t' + 'ml,'
			for iel, el in enumerate(rule):
				bspace = False; breplace = False
				if el[0] == rec_def_type.conn:
					if el[1] == conn_type.IF:
						wstr += 'c:f,'
					elif el[1] == conn_type.AND:
						wstr += 'c:a,'
					elif el[1] == conn_type.start:
						wstr += 'c:s,'
					elif el[1] == conn_type.end:
						wstr += 'c:e,'
						if rule[iel+1][0] == rec_def_type.conn and rule[iel+1][1] == conn_type.end: continue
						wstr += nlstr
					elif el[1] == conn_type.Insert:
						wstr += 'c:i,'
					elif el[1] == conn_type.Unique:
						wstr += 'c:u,'
					elif el[1] == conn_type.Modify:
						wstr += 'c:m,'
					elif el[1] == conn_type.Remove:
						wstr += 'c:r,'
					elif el[1] == conn_type.Broadcast:
						wstr += 'c:b,'
					elif el[1] == conn_type.THEN:
						wstr += 'c:t,'
					else:
						exit(1)
				elif el[0] == rec_def_type.like:
					wstr += el[1]; bspace = True
					if el[2] != 1.0:
						wstr += ':' + str(el[2])
				elif el[0] == rec_def_type.var:
					w = rule[el[1]][1]; bspace = True; breplace = True
				elif el[0] == rec_def_type.obj:
					w = el[1]; bspace = True; breplace = True
				else:
					exit()
				if breplace:
					br = False
					if len(el) > 2:
						if el[2] == conn_type.replace_with_next:
							br = True
						else:
							assert False
					lel = w.split()
					for ii, s in enumerate(lel):
						wstr += s
						if br: wstr += '::r'
						if ii < len(lel) - 1:
							wstr += ' '

				if bspace:
					if iel == (len(rule) - 1) or rule[iel+1][0] == rec_def_type.conn:
						wstr += ','
					else:
						wstr += ' '
			wstr += 'mle\n'
			fhw.write(wstr)
		fhw.close()


def main():
	old_rules_obj = cl_fixed_rules('adv/rules.txt')
	old_rules_obj.write_rules('~/tmp/rules.new.txt')
	print('Important note. Add the header and footer and modify rule gen_rule_now_held_in to only replace the word free')
	pass

if __name__ == "__main__":
    main()


