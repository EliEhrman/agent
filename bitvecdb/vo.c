/* vo.c */
#define _GNU_SOURCE
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <search.h>
#include <execinfo.h>
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
#include "bitvecdb.h"
#include "bdb.h"

typedef struct SIntList {
	int * pl;
	int len;
} tSIntList;


typedef struct SIntPairList {
	intpair * pl;
	int len;
	int num_alloc;
} tSIntPairList;

typedef struct SStrList {
	char ** pl;
	int len;
	int num_alloc;
} tSStrList;

typedef int intquad[4];

char * rec_def_type_names[] = {"None", "obj", "like"};
typedef enum eRecDefType {
	etRecDefNone,
	etRecDefObj,
	etRecDefLike
} teRecDefType;

typedef struct SPhraseEl {
	teRecDefType el_type;
	char * val; // bitvec, pointer to memory allocated elsewhere
	int hd;
} tSPhraseEl;

typedef struct SPhrase {
	tSPhraseEl * pl;
	int len;
	int num_alloc;
} tSPhrase;

typedef struct SMatchPhrase {
	int istage;
	bool b_matched;
	tSPhrase phrase;
} tSMatchPhrase;

void phrase_el_init(tSPhraseEl* pel, teRecDefType tet, char * val, int hd) {
	pel->el_type = tet;
	pel->val = val;
	pel->hd = hd;
}

void phrase_el_print(tSPhraseEl* pel, tSBDBApp * pdbels) {
	printf("%s, val: %s, hd: %d\n", rec_def_type_names[(int)(pel->el_type)], get_name_exact(pdbels, 1, pel->val), pel->hd);
}

void phrase_print(tSPhrase * pphrase, tSBDBApp * pdbels) {
	int i;
	for (i=0;i<pphrase->len;i++) {
		phrase_el_print(&(pphrase->pl[i]), pdbels);
	}
}

//void phrase_free(tSPhrase * pphrase) {
//	int iel;
//	for (iel=0;iel<pphrase->len;iel++) {
//		vofree(pphrase->pl)
//	}
//}

void match_phrase_print(tSMatchPhrase * ppm, tSBDBApp * pdbels) {
	printf("stage: %d, b_matched: %s, phrase: \n", ppm->istage, (ppm->b_matched ? "True" : "False"));
	phrase_print(&(ppm->phrase), pdbels);
	
}

//void match_phrase_set(tSMatchPhrase * ppm, int istage, bool b_matched, tSPhrase * phrase) {
//	int iel;
//	ppm->istage = istage;
//	ppm->b_matched = b_matched;
//	ppm->phrase.len = phrase->len;
////	ppm->phrase.pl = (tSPhraseEl *)bdbmalloc(ppm->phrase.len * sizeof(tSPhraseEl));
//	for (iel=0;iel<ppm->phrase.len;iel++) {
//		ppm->phrase.pl[iel].el_type = phrase->pl[iel].el_type;
//		ppm->phrase.pl[iel].val = phrase->pl[iel].val;
//		ppm->phrase.pl[iel].hd = phrase->pl[iel].hd;
//	}
//	
//}
//
void match_phrase_set2(tSMatchPhrase * ppm, int istage, bool b_matched, tSPhrase * phrase) {
	int iel;
	ppm->istage = istage;
	ppm->b_matched = b_matched;
	ppm->phrase.len = phrase->len;
	ppm->phrase.pl = (tSPhraseEl*)bdballoc(ppm->phrase.pl, &(ppm->phrase.num_alloc), sizeof(tSPhraseEl), ppm->phrase.len);
//	ppm->phrase.pl = (tSPhraseEl *)bdbmalloc(ppm->phrase.len * sizeof(tSPhraseEl));
	for (iel=0;iel<ppm->phrase.len;iel++) {
		ppm->phrase.pl[iel].el_type = phrase->pl[iel].el_type;
		ppm->phrase.pl[iel].val = phrase->pl[iel].val;
		ppm->phrase.pl[iel].hd = phrase->pl[iel].hd;
	}
	
}



typedef struct SNtVars {
	int loc;
	int b_bound;
	int b_must_bind;
	char * val; // pointer to bitvec array from another db (story or perms)
	int hd;
	int iext_var;
	int b_resolved;
	tSStrList l_var_vals;
} tSNtVars;

void print_nt_var(tSNtVars * var_opt) {
	printf(	"loc = %d, b_bound = %d, b_must_bind = %d, val = %s, hd = %d, iext_var = %d, b_resolved = %d.\n",
			var_opt->loc, var_opt->b_bound, var_opt->b_must_bind, var_opt->val,
			var_opt->hd, var_opt->iext_var, var_opt->b_resolved);
}


typedef struct SVOState {
	tSBDBApp * pdbrules ;
	tSBDBApp * pdb ;
	tSBDBApp * pdbstory ;
	tSBDBApp * pdbels;
	int num_vars_alloc;
	int num_vars;
	tSNtVars * pnv;
	int num_ext_vars;
	int max_phrase_len;
	int phrase_starts_num_alloc;
	int * l_phrase_starts; // 1 longer than l_phrases_len_len
	int var_vals_num_alloc;
//	tSStrList* l_var_vals; // len num_vars
	int var_locs_num_alloc;
	int * l_var_locs; // len num_vars
	int var_all_locs_num_alloc;
	tSIntPairList * l_var_all_locs; // len num_vars
//	tSPairDict d_var_opts;
	int src_pat_num_alloc;
	int src_pat_num_els_alloc;
	char *** ll_src_pat;
	int hd_max_num_alloc;
	int hd_max_num_els_alloc;
	int ** ll_hd_max;
	char * db_name; // not stored locally; like all strings
	int mpdb_story_rphrase_size; // length of the following mrk arrays
	int ilen_mrk_num_alloc;
	char * l_ilen_mrk; // list of bools (char size) size of the srphrases of mpdb, true if the len of current stage matches the len of the ilen of the srphrase
	int match_num_alloc;
	char * m_match; // local match vector holding matches so far from mpdb story bin recs
	int mrks_num_alloc;
	char * m_mrks; // local match vector
	tSPhrase l_phrase_found;
	int stage_phrase_len; // length of next few arrays. A purely local value inside the stage loop
//	int b_unbound_num_alloc;
//	bool * l_b_unbound;
//	int i_unbound_num_alloc;
//	int * l_i_unbound;
//	int i_null_phrases_num_alloc;
//	int i_null_phrases_len;
//	int * l_i_null_phrases;
	int match_phrases_len;
	int match_phrases_num_alloc;
	tSMatchPhrase * l_match_phrases;
	tSPhrase l_story_phrase_found;
	/*
	// Not dealt with any of the test code yet
	int num_test_phrases;
	tSPhrase * l_test_phrases; // not just a pointer, a list.
	int * l_test_stages;
	struct hsearch_data  d_els;
	int test_locs_len;
	tSIntPairList * ll_test_locs;
	 */
	int replace_iopts_len; // len for the next few lists. All used to find var val replacements to the null phrase
	int iopts_num_alloc;
	int * l_iopts; // iopt of the val from var_vals that should be used to replace the var
	int replace_iels_num_alloc;
	int * l_replace_iels; // iel of the value of l_iopts and var_val_lens
	int var_vals_lens_num_alloc;
	int * l_var_vals_lens; // length of the list of vals for that iopt in l_var_vals
	int product_perms_num_alloc;
	int product_perms_els_num_alloc;
	int ** l_product_perms; // holds the list possible combinations of l_var_vals_lens
	tSPhrase perm_phrase;
	// an array of int* each of which holds which var from var_vals was selected for this phrase
	// lenght of the array is match_phrases_len, each of length num_vars. //This last is filled by the time this is used
	// vars that are irrelvant for this phrase are kept at -1
	int match_phrase_var_sels_num_alloc;
	int match_phrase_var_sels_els_num_alloc;
	int ** ll_match_phrase_var_sels; 
	int match_phrase_stage_num_alloc;
	int * l_match_phrase_stage; // Length match_phrases_len. States which stage the match_phrase belongs to.
	int num_forbidden; // number of combs in the forbidden array next
	int forbidden_combs_num_alloc;
	int forbidden_combs_els_num_alloc;
	int ** ll_forbidden_combs; // An array of lenght num_forbidden. Each num_vars ints long
	int comb_vars_num_alloc;
	int * l_comb_vars; // one array num_vars long. Used as a temp variable when translating a product array to all vars
	int num_combos; // number of combos found. The length of the next array
	int match_iphrase_combos_num_alloc;
	int match_iphrase_combos_els_num_alloc;
	int ** ll_match_iphrase_combos; // Each combo has length pvos->pgg->l_phrases_len_len. One index into l_match_phrases per stage
	int comb_cand_num_alloc;
	int * l_comb_cand; // len pvos->pgg->l_phrases_len_len
	char * rule_rec;
	tSRuleRec * prule ;
	int ext_rperm;
	int idb;

} tSVOState;

void match_phrase_append(tSVOState * pvos, int istage, bool b_matched, tSPhrase * pphrase) {
	int old_match_phrases_len = pvos->match_phrases_len;
	pvos->match_phrases_len++;
	pvos->l_match_phrases = (tSMatchPhrase*)bdballoc(pvos->l_match_phrases, &(pvos->match_phrases_num_alloc), 
													sizeof(tSMatchPhrase), pvos->match_phrases_len);
	match_phrase_set2(	&(pvos->l_match_phrases[old_match_phrases_len]), 
						istage, b_matched, pphrase);
}

void match_phrase_var_sel_append2(tSVOState * pvos, int istage) {
	printf("match_phrase_var_sel_append called.\n");
	int old_len = pvos->match_phrases_len - 1;
	pvos->ll_match_phrase_var_sels = 
			(int**)bdballoc(	pvos->ll_match_phrase_var_sels, &(pvos->match_phrase_var_sels_num_alloc),
							sizeof(int*), pvos->match_phrases_len);
	pvos->ll_match_phrase_var_sels[0] = 
			(int*)bdballoc(	pvos->ll_match_phrase_var_sels[0], &(pvos->match_phrase_var_sels_els_num_alloc),
							sizeof(int), pvos->match_phrases_len*pvos->num_vars);
	int * pb = pvos->ll_match_phrase_var_sels[0];
	for (int imatch=0;imatch<pvos->match_phrases_len;imatch++, pb += pvos->num_vars) {
		pvos->ll_match_phrase_var_sels[imatch] = pb;
	}
	pvos->l_match_phrase_stage = (int*)bdballoc(pvos->l_match_phrase_stage, &(pvos->match_phrase_stage_num_alloc),
												sizeof(int), pvos->match_phrases_len);
	int ** new_var_sels = &(pvos->ll_match_phrase_var_sels[old_len]);
	for (int ivar=0; ivar<pvos->num_vars;ivar++) {
		(*new_var_sels)[ivar] = -1;
	}
	for (int iel=0;iel<pvos->prule->phrase_lens[istage];iel++) {
		int ivar = pair_dict_get(&(pvos->prule->d_var_opts), istage, iel);
		(*new_var_sels)[ivar] = 0;
	}
	pvos->l_match_phrase_stage[old_len] = istage;
	printf("match_phrase_var_sel_append returning.\n");
}

int * int_arr_add_val2(int * arr, int* palloc_len, int len, int val)
{
	arr = (int*)bdballoc(arr, palloc_len, sizeof(int), len+1);
	arr[len] = val;
	return arr;
}


void product_fill(int num_in, int * l_in, int ** l_out, int pos) {
	if (num_in==0) {
		return;
	}
	int head = l_in[0];
	int num_in_left = num_in - 1;
	int * left_in = l_in+1;
	int num_reps = 1;
	int irec = 0;
	int icount;
	for (int iin = 0; iin < num_in_left; iin++) {
		num_reps *= left_in[iin];
	}
	for (icount=0, irec=0; icount < head; icount++) {
		for (int irep=0;irep<num_reps;irep++, irec++) {
			l_out[irec][pos] = icount;
		}
	}
	for (icount=0, irec=0; icount < head; icount++) {
		product_fill(num_in_left, left_in, &(l_out[irec]),pos+1);
		irec += num_reps;
	}
	
}

//void cartesian_product(int len_in, int * l_in, int *** pout, int * pnum_out) {
//	int num_out = 1;
//	for (int iin = 0; iin < len_in; iin++) {
//		num_out *= l_in[iin];
//	}
//	int ** l_out = (int**)vomalloc(sizeof(int*)*num_out);
//	int *buf = (int*)vomalloc(sizeof(int)*num_out*len_in);
////	printf("cartesian_product allocated %p and %p.\n", buf, l_out);
//	int* pbuf = buf;
//	for (int iout = 0; iout < num_out; iout++, pbuf+=len_in) {
//		l_out[iout] = pbuf;
//	}
//	product_fill(len_in, l_in, l_out,0);
//	*pnum_out = num_out;
//	*pout = l_out;
////	printf("Cartesian product perms for length %d:\n", len_in);
////	for (int iout = 0; iout < num_out; iout++) {
////		printf("%d: ", iout);
////		for (int ii=0; ii<len_in;ii++) {
////			printf("%d, ", l_out[iout][ii]);
////		}
////		printf("\n");
////	}
//	
//}
//
void cartesian_product2(int len_in, int * l_in, int *** pout, int * pout_alloc_len, int * pout_els_alloc_len, 
						int * pnum_out) {
	int num_out = 1;
	for (int iin = 0; iin < len_in; iin++) {
		num_out *= l_in[iin];
	}
	int ** l_out = *pout;
	l_out = (int**)bdballoc(l_out, pout_alloc_len, sizeof(int*), num_out);
	int *buf = l_out[0];
	buf = (int*)bdballoc(buf, pout_els_alloc_len, sizeof(int), num_out*len_in);
	printf("cartesian_product allocated %p and %p.\n", buf, l_out);
	int* pbuf = buf;
	for (int iout = 0; iout < num_out; iout++, pbuf+=len_in) {
		l_out[iout] = pbuf;
	}
	product_fill(len_in, l_in, l_out,0);
	*pnum_out = num_out;
	*pout = l_out;
	printf("Cartesian product perms for length %d:\n", len_in);
	for (int iout = 0; iout < num_out; iout++) {
		printf("%d: ", iout);
		for (int ii=0; ii<len_in;ii++) {
			printf("%d, ", l_out[iout][ii]);
		}
		printf("\n");
	}
	
}



void * create_vo(void * hcdb_rules, void * hcdb_all, void * hcdb_story, void * hcdb_els) {
	signal(SIGSEGV, handler);   // install our handler
	printf("handler installed.\n");
	tSVOState * pvos = (tSVOState *)bdbmalloc2(sizeof(tSVOState), 1);
	pvos->pdbrules = (tSBDBApp *) hcdb_rules;
	pvos->pdb = (tSBDBApp *) hcdb_all;
	pvos->pdbels = (tSBDBApp *)hcdb_els;
	pvos->pdbstory = (tSBDBApp *) hcdb_story;
//	pvos->pnv = (tSNtVars *)bdbmalloc2(sizeof(tSNtVars), 1);
	return pvos;
}

void init_vo(void * hvos, int irule_rec, int idb, int call_num, int ext_rperm) {
	tSVOState * pvos = (tSVOState *)hvos;
	pvos->rule_rec = &(pvos->pdb->db[pvos->pdbrules->rec_ptrs[irule_rec * pvos->pdbrules->bitvec_size]]);
	pvos->prule = (tSRuleRec *)&(pvos->pdbrules->rule_data[irule_rec]);
	
//	tSBDBApp * pdbrules = pvos->pdbrules;
//	tSBDBApp * pdb = pvos->pdb;
	tSRuleRec * prule = pvos->prule;
	pvos->idb = idb;
	
	pvos->num_vars = prule->num_vars;
	pvos->pnv = (tSNtVars *)bdballoc(pvos->pnv, &(pvos->num_vars_alloc), sizeof(tSNtVars), pvos->num_vars);
	for (int ivar = 0; ivar < prule->num_vars; ivar++ ) {
		tSVarData * pvar = &(prule->var_tbl[ivar]);
		pvos->pnv[ivar].l_var_vals.len = 1;
		pvos->pnv[ivar].l_var_vals.pl = (char **)bdballoc(	pvos->pnv[ivar].l_var_vals.pl, &(pvos->pnv[ivar].l_var_vals.num_alloc), 
															sizeof(char*), pvos->pnv[ivar].l_var_vals.len);
		char * rule_val = &(pvos->pdbrules->db[pvar->src_pat_el*pvos->pdb->bitvec_size]);
		if (pvar->hd_thresh == 0) {
			pvos->pnv[ivar].l_var_vals.pl[0] = rule_val;
		}
		else {
			pvos->pnv[ivar].l_var_vals.pl[0] = NULL;
		}
		pvos->pnv[ivar].hd = pvar->hd_thresh;
		pvos->pnv[ivar].val = rule_val;
		pvos->pnv[ivar].b_bound = pvos->pnv[ivar].b_resolved  = (pvar->hd_thresh == 0);
		pvos->pnv[ivar].iext_var = -1;
	}
	pvos->ext_rperm = ext_rperm;
	pvos->num_combos = 0;
	pvos->num_forbidden = 0;
	pvos->match_phrases_len = 0;

}

//void set_ext_rperm(void * hvos, int rperm) {
//	tSVOState * pvos = (tSVOState *)hvos;
//	pvos->ext_rperm = rperm;
//}

void add_ext_var(void * hvos, int ivar, int b_bound, int b_must_bind, int iel, int hd, int iext_var ) {
	tSVOState * pvos = (tSVOState *)hvos;
	tSBDBApp * pdb = pvos->pdb;
//	int rlen = get_rec_len(pdb, pvos->ext_rperm);
	char *	pdbrec = get_rec(pdb, pvos->ext_rperm);
	tSRuleRec * prule =  pvos->prule;
	int i_result_phrase = prule->num_phrases-1;
	if (ivar != pair_dict_get(&(prule->d_var_opts), i_result_phrase, iel)) {
		printf("Error! ivar given does not match the var expected for the result val at iel %d.\n", iel);
		exit(1);
	}
	if (b_bound) {
		pvos->pnv[ivar].val = &(pdbrec[iel * pdb->bitvec_size]);
		pvos->pnv[ivar].l_var_vals.pl[0] = &(pdbrec[iel * pdb->bitvec_size]);
		pvos->pnv[ivar].hd = 0;
		pvos->pnv[ivar].b_bound = pvos->pnv[ivar].b_must_bind = true;
		printf("Binding var %d to %s.\n", ivar, get_name_exact(pvos->pdbels, 1, pvos->pnv[ivar].l_var_vals.pl[0]));
	}
	else {
		printf("Coding warning. Reconsider logic if code gets here. Should probably be the tighter of the two options rather than both.\n");
		pvos->pnv[ivar].l_var_vals.pl = (char **)bdballoc(	pvos->pnv[ivar].l_var_vals.pl, &(pvos->pnv[ivar].l_var_vals.num_alloc), 
															sizeof(char*), pvos->pnv[ivar].l_var_vals.len);
		pvos->pnv[ivar].l_var_vals.pl[pvos->pnv[ivar].l_var_vals.len] = &(pdbrec[iel * pdb->bitvec_size]);
		pvos->pnv[ivar].l_var_vals.len++;
		pvos->pnv[ivar].b_bound = pvos->pnv[ivar].b_must_bind = false;
	}
	pvos->pnv[ivar].iext_var = iext_var;

	
}

//void add_ext_var(void * hvos, int ivar, int b_bound, int b_must_bind, char * val, int hd, int iext_var) {
//	tSNtVars nv;
//	tSVOState * pvos = (tSVOState *)hvos;
//	nv.loc = loc, nv.b_bound = b_bound, nv.b_must_bind = b_must_bind, nv.val = val;
//	nv.cd = cd, nv.iext_var = iext_var; nv.b_resolved = 0;
////	printf("ptr %p, alloc size %d, curr %d\n", pvos->pnv, pvos->num_vars_alloc, pvos->curr_var_num);
//	pvos->pnv[pvos->curr_var_num++] = nv;
//
//	//	int i;
//	//	for (i=0; i<curr_var_num; i++) {
//	//		printf("loc: %d, val: %s\n", pnv[i].loc, pnv[i].val);
//	//	}
//}

int get_num_match_phrases(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;
	return pvos->match_phrases_len;
}

int get_match_phrase_istage(void * hvos, int imatch) {
	tSVOState * pvos = (tSVOState *)hvos;
	return pvos->l_match_phrases[imatch].istage;
}

int get_match_phrase_b_matched(void * hvos, int imatch) {
	tSVOState * pvos = (tSVOState *)hvos;
	return (int)(pvos->l_match_phrases[imatch].b_matched);
}


int get_num_phrase_els(void * hvos, int imatch) {
	tSVOState * pvos = (tSVOState *)hvos;
	return pvos->l_match_phrases[imatch].phrase.len;
}

int get_phrase_el_def_type(void * hvos, int imatch, int iel) {
	tSVOState * pvos = (tSVOState *)hvos;
	return (int)(pvos->l_match_phrases[imatch].phrase.pl[iel].el_type);
}

int get_phrase_el_hd(void * hvos, int imatch, int iel) {
	tSVOState * pvos = (tSVOState *)hvos;
	return pvos->l_match_phrases[imatch].phrase.pl[iel].hd;
}

int get_phrase_el_val(void * hvos, int imatch, int iel) {
	tSVOState * pvos = (tSVOState *)hvos;
	tSBDBApp * pdbels = pvos->pdbels;
	return get_irec_exact(pdbels, 1, pvos->l_match_phrases[imatch].phrase.pl[iel].val);
}

int get_num_combos(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;
	return pvos->num_combos;
}

int get_combo_len(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;
	return pvos->prule->num_phrases;
}

int get_combo_val(void * hvos, int icombo, int ival) {
	tSVOState * pvos = (tSVOState *)hvos;
	return pvos->ll_match_iphrase_combos[icombo][ival];
}

void do_vo(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;
//	tSBDBApp * pdbrules = pvos->pdbrules;
//	tSBDBApp * pdb = pvos->pdb;
	tSRuleRec * prule = pvos->prule;
	tSBDBApp * pdbels = pvos->pdbels;
	tSBDBApp * pdbstory = pvos->pdbstory;

	for (int iphrase=0;iphrase<prule->num_phrases;iphrase++) {
		int plen = prule->phrase_lens[iphrase];
		pvos->l_phrase_found.len = plen;
		pvos->l_phrase_found.pl = (tSPhraseEl*)bdballoc(pvos->l_phrase_found.pl, &(pvos->l_phrase_found.num_alloc), 
														sizeof(tSPhraseEl), pvos->l_phrase_found.len);
		for (int iel=0;iel<plen;iel++) {
			int ivar = pair_dict_get(&(prule->d_var_opts), iphrase, iel);
			teRecDefType et = etRecDefLike;
			if (pvos->pnv[ivar].hd == 0) et = etRecDefObj;
			phrase_el_init(&(pvos->l_phrase_found.pl[iel]), et, pvos->pnv[ivar].val, pvos->pnv[ivar].hd);
		}
		// These first phrases, embedded in match_phrase are the null phrase.
		// The null phrase is used to build other phrases when the null values are replaced by 
		// found values
//		{
//			int old_i_null_phrases_len = pvos->i_null_phrases_len;
////			printf("pvos->l_i_null_phrases len %d increasing..\n", old_i_null_phrases_len);
//			pvos->i_null_phrases_len++;
//			pvos->l_i_null_phrases = (int *)bdballoc(pvos->l_i_null_phrases, &(pvos->i_null_phrases_num_alloc), 
//													sizeof(int), pvos->i_null_phrases_len);
//			pvos->l_i_null_phrases[old_i_null_phrases_len] = pvos->match_phrases_len;
//		}
		// use the l_phrase_found to create a match phrase and append it to the list.
		// This is one of the null phrases.
		// Note, the l_match_phrase memory is not used. It is copied to its own list owned memory.
		match_phrase_append(pvos, iphrase, false, &(pvos->l_phrase_found));


		// Add an array num_vars long to the pvos->ll_match_phrase_var_sels array. Each relevant var
		// will be zero; the first entry in the var_vals. The remainder are -1
		// Note the first entry will be null for rec def like and the actual value for an obj
		// This function also records the stage of the match phrase
		match_phrase_var_sel_append2(pvos, iphrase);
	}

	for (int iphrase = 0; iphrase < prule->num_phrases; iphrase++) {
		int plen = prule->phrase_lens[iphrase];
		char * match_pat[plen];
		int match_hd[plen];
		for (int iel = 0; iel < plen; iel++) {
			int ivar = pair_dict_get(&(prule->d_var_opts), iphrase, iel);
			match_pat[iel] = pvos->pnv[ivar].val;
			match_hd[iel] = pvos->pnv[ivar].hd;
		}
		pvos->l_phrase_found.len = plen;
		pvos->l_phrase_found.pl = (tSPhraseEl*)bdballoc(pvos->l_phrase_found.pl, &(pvos->l_phrase_found.num_alloc), 
														sizeof(tSPhraseEl), pvos->l_phrase_found.len);
		for (int iel=0;iel<plen;iel++) {
//			int ivar = pair_dict_get(&(prule->d_var_opts), iphrase, iel);
//			teRecDefType et = etRecDefLike;
//			if (pvos->pnv[ivar].hd == 0) et = etRecDefObj;
			phrase_el_init(&(pvos->l_phrase_found.pl[iel]), etRecDefObj, NULL, 0);
		}
		// These first phrases, embedded in match_phrase are the null phrase.
		int irec = -1;
		while (true) {
			irec = get_next_irec(pdbstory, irec, pvos->idb, plen, match_pat, match_hd);
			if (irec < 0) break;
			printf("do_vo found match in story at irec: %d\n", irec);
			char * vals_found[plen];
			bool bforbidden = false;
			for (int iel = 0; iel < plen; iel++) {
				char * val = get_el_in_rec(pdbstory, irec, iel);
				for (int iel2 = 0; iel2 < iel; iel2++) {
					if (memcmp(val, vals_found[iel2], pdbstory->bitvec_size) == 0) {
						printf(	"do_vo: possible forbidden equality WITHIN phrase for word %s in pos %d and %d.\n",
								val, iel, iel2);
						int ivar1 = pair_dict_get(&(prule->d_var_opts), iphrase, iel);
						int ivar2 = pair_dict_get(&(prule->d_var_opts), iphrase, iel2);
						if (ivar1 != ivar2) {
							printf(	"do_vo: confirmed forbidden equality WITHIN phrase for word %s in pos %d at ivar %d and %d at ivar %d.\n",
									val, iel, ivar1, iel2, ivar2);
							bforbidden = true;
							exit(1);
							break;
						}
					}
				}
				if (bforbidden) break;
				vals_found[iel] = val;
			} // loop over els
			if (bforbidden) continue;
			// add match phrase and var sels with default values and correct immediately
			match_phrase_append(pvos, iphrase, true, &(pvos->l_phrase_found));
			match_phrase_var_sel_append2(pvos, iphrase);
			for (int iel = 0; iel < plen; iel++) {
				char * val = vals_found[iel];
				printf("%s ", get_name_exact(pdbels, 1, val));
				int ivar = pair_dict_get(&(prule->d_var_opts), iphrase, iel);
				pvos->l_match_phrases[pvos->match_phrases_len-1].phrase.pl[iel].val = val;
				if (pvos->pnv[ivar].b_bound) continue;
				// Now see if we want to add a new value to the var vals for that var
				printf(" (%d %d %d %d) ", iphrase, iel, ivar, pvos->pnv[ivar].l_var_vals.len);
				printf("<2>");
				int ifound = -1 ;
				for (int ival_poss = 0; ival_poss < pvos->pnv[ivar].l_var_vals.len; ival_poss++) {
					if (pvos->pnv[ivar].l_var_vals.pl[ival_poss] == NULL) continue;
					if (memcmp(pvos->pnv[ivar].l_var_vals.pl[ival_poss], val, pdbstory->bitvec_size) == 0) {
						ifound = ival_poss;
						break;
					}
				}
				printf("<3>");
				if (ifound == -1) {
					ifound = pvos->pnv[ivar].l_var_vals.len;
					pvos->pnv[ivar].l_var_vals.len++;
					pvos->pnv[ivar].l_var_vals.pl = (char **)bdballoc(	pvos->pnv[ivar].l_var_vals.pl, 
																		&(pvos->pnv[ivar].l_var_vals.num_alloc), 
																		sizeof(char*), pvos->pnv[ivar].l_var_vals.len);
					pvos->pnv[ivar].l_var_vals.pl[ifound] = val;
					printf("(Added val to pos %d of var vals for ivar %d.) ", ifound, ivar);
				}
				pvos->ll_match_phrase_var_sels[pvos->match_phrases_len-1][ivar] = ifound;
				printf("<4>");
			} // loop over els of rec found
			printf("\n");
		} // keep looping whiile more recs found
	} // loop over phrases/stages
	{
		// Here we search for forbidden combinations. Any values of one var that is equal to the value of
		// another var is forbidden becuase in that case there would be a new var 
		for (int ivar1 = 0; ivar1 < pvos->num_vars; ivar1++) {
			for (int ivar2 = ivar1+1; ivar2 < pvos->num_vars; ivar2++) {
				for (int ival1 = 0; ival1 < pvos->pnv[ivar1].l_var_vals.len;ival1++) {
					if (pvos->pnv[ivar1].l_var_vals.pl[ival1] == NULL) continue;
					for (int ival2 = 0; ival2 < pvos->pnv[ivar2].l_var_vals.len;ival2++) {
						if (pvos->pnv[ivar2].l_var_vals.pl[ival2] == NULL) continue;
						if (memcmp(	pvos->pnv[ivar1].l_var_vals.pl[ival1], pvos->pnv[ivar2].l_var_vals.pl[ival2], 
									pdbstory->bitvec_size) == 0) {
							printf("Hit a forbidden combi for ivar1 %d, ival1 %d, ivar2 %d, ival2 %d, val %s.\n",
									ivar1, ival1, ivar2, ival2, 
									get_name_exact(pdbels, 1, pvos->pnv[ivar1].l_var_vals.pl[ival1]));
							int old_len = pvos->num_forbidden;
							pvos->num_forbidden++;
							pvos->ll_forbidden_combs = 
									(int**)bdballoc(pvos->ll_forbidden_combs, &(pvos->forbidden_combs_num_alloc),
													sizeof(int*), pvos->num_forbidden);
							pvos->ll_forbidden_combs[0] = 
									(int*)bdballoc(	pvos->ll_forbidden_combs[0], &(pvos->forbidden_combs_els_num_alloc),
													sizeof(int), pvos->num_forbidden*pvos->num_vars);
							int * pb = pvos->ll_forbidden_combs[0];
							for (int iforbid=0;iforbid<pvos->num_forbidden;iforbid++, pb += pvos->num_vars) {
								pvos->ll_forbidden_combs[iforbid] = pb;
							}
							int * pvec = pvos->ll_forbidden_combs[old_len];
							for (int ivar=0; ivar<pvos->num_vars; ivar++) {
								if (ivar==ivar1) {
									pvec[ivar] = ival1;
								}
								else if (ivar == ivar2) {
									pvec[ivar] = ival2;
								}
								else {
									pvec[ivar] = -1;
								}
							}
						}
					}
				}
				
			}
		}
		{
			for (int imatch=pvos->match_phrases_len-1; imatch>=0;imatch--) { // note reversed
				bool bmatch = true;
				for (int iforbid=0; iforbid<pvos->num_forbidden;iforbid++) {
					for (int ivar=0; ivar<pvos->num_vars;ivar++) {
						if (pvos->ll_forbidden_combs[iforbid][ivar] == -1) continue;
						if (pvos->ll_match_phrase_var_sels[imatch][ivar] != pvos->ll_forbidden_combs[iforbid][ivar]) {
							bmatch = false;
							break;
						}
					}
					if (bmatch) {
						printf("Coding surprise: imatch %d forbidden by comb %d\n", imatch, iforbid);
						int rem = pvos->match_phrases_len - 1 - imatch; 
						if (rem > 0) {
							memcpy(	&(pvos->l_match_phrases[imatch]), &(pvos->l_match_phrases[imatch+1]), 
									rem * sizeof(tSMatchPhrase));
							memcpy(	&(pvos->ll_match_phrase_var_sels[imatch]), 
									&(pvos->ll_match_phrase_var_sels[imatch+1]), rem * sizeof(int*));
						}
						pvos->match_phrases_len--;
					}

				}				
			}
		}
		{
			printf("%d forbidden combinations found.\n", pvos->num_forbidden);
			for (int ifbd=0; ifbd<pvos->num_forbidden; ifbd++) {
				printf("%d: ", ifbd);
				for (int ivar=0; ivar<pvos->num_vars; ivar++) {
					printf("%d:%d, ", ivar, pvos->ll_forbidden_combs[ifbd][ivar]);
				}
				printf("\n");
			}
		}
	}
	{
		printf("%d match phrases:\n", pvos->match_phrases_len );
		for (int i=0; i<pvos->match_phrases_len;i++) {
			match_phrase_print(&(pvos->l_match_phrases[i]), pdbels);
		}
//		printf("l_var_vals: \n");
//		for (int iopt=0; iopt<pvos->num_vars; iopt++) {
//			tSStrList * sl = &(pvos->l_var_vals[iopt]);
//			printf("%d: ", iopt);
//			str_list_print(sl);
//		}
		printf("%d match phrase stages: ", pvos->match_phrases_len);
		for (int i=0; i<pvos->match_phrases_len;i++) {
			printf("%d: %d, ", i, pvos->l_match_phrase_stage[i]);
		}
		printf("\n");
		printf("%d ll_match_phrase_var_sels: \n", pvos->match_phrases_len);
		for (int i=0; i<pvos->match_phrases_len;i++) {
			printf("match phrase: %d: ", i);
			for (int ivar=0; ivar<pvos->num_vars; ivar++) {
				printf("%d:%d,", ivar, pvos->ll_match_phrase_var_sels[i][ivar]);
			}
			printf("\n");
		}
	}
	{
		// Now we add the fictional match phrases. We build these by taking the var vals for each var
		// and trying different combinations of them
		// First we build an array of limits for each element of the combination. The cartesian_product function,
		// later, will take this array of limits and create all the combinations, each the same length as the input
		// of numbers where each element is less than the limit at that location.
		// This is done by finding the ivar for each el of the phrase. If the var for that position is not 
		// bound, we make the limit simply the number of elements of the l_var_vals for that var. In ohter
		// words, every perm will have an index into the l_var_vals for that val,
		// We also record the var number and iel for later use
		for (int iphrase=0;iphrase<prule->num_phrases;iphrase++) {
			// the first match phrase are the null match phrases, one per rule phrase
			tSMatchPhrase * null_match_phrase = &(pvos->l_match_phrases[iphrase]);
			printf("Null match phrase for phrase %d: \n", iphrase);
			match_phrase_print(null_match_phrase, pdbels);
			int istage = null_match_phrase->istage;
			pvos->replace_iopts_len = 0;
			for (int iel=0;iel<prule->phrase_lens[istage];iel++) {
				int iopt = pair_dict_get(&(pvos->prule->d_var_opts), istage, iel);
				if (iopt == -1 || pvos->pnv[iopt].b_bound) {
					continue;
				}
//				printf("Adding elements %d, %d, %d to replace lists.\n", iopt, iel, pvos->l_var_vals[iopt].len);
				pvos->l_iopts = int_arr_add_val2(pvos->l_iopts, &(pvos->iopts_num_alloc), pvos->replace_iopts_len, iopt);
				pvos->l_replace_iels = int_arr_add_val2(pvos->l_replace_iels, &(pvos->replace_iels_num_alloc), 
														pvos->replace_iopts_len, iel);
				pvos->l_var_vals_lens = int_arr_add_val2(	pvos->l_var_vals_lens, &(pvos->var_vals_lens_num_alloc), 
															pvos->replace_iopts_len, pvos->pnv[iopt].l_var_vals.len);
				pvos->replace_iopts_len++;				
			}
			// here is the function calls that makes the perms
			int num_products = 0;
			cartesian_product2(	pvos->replace_iopts_len, pvos->l_var_vals_lens, &(pvos->l_product_perms), 
								&(pvos->product_perms_num_alloc), &(pvos->product_perms_els_num_alloc), &num_products);
			pvos->l_comb_vars = (int*)bdballoc(pvos->l_comb_vars, &(pvos->comb_vars_num_alloc), sizeof(int), pvos->num_vars);
			// loop through the perms
			for (int iperm=0; iperm<num_products;iperm++) {
				bool b_match_exists = false;
				int * perm = pvos->l_product_perms[iperm];
				// for this perm set up a translation to an array of all vars where the vals of that perm, if relevant,
				// appear in the var location otherwise -1
				// first initialize using the null phrase's var sels.
				memcpy(pvos->l_comb_vars, pvos->ll_match_phrase_var_sels[iphrase], sizeof(int)*pvos->num_vars);
//				for (int ivar=0;ivar<pvos->num_vars;ivar++) {
//					pvos->l_comb_vars[ivar] = -1;
//				}
				// now replace the var sels with those the perm is suggesting
				for (int ii=0;ii<pvos->replace_iopts_len;ii++) {
					int ivar = pvos->l_iopts[ii];
					pvos->l_comb_vars[ivar] = perm[ii];
				}
				// now check this perm against the forbidden combs. See the comment above describing the creation 
				// of this data structure
				bool bforbid = false;
				for (int iforbidden=0;iforbidden<pvos->num_forbidden;iforbidden++) {
					bool bmatch = true;
					for (int ivar=0;ivar<pvos->num_vars;ivar++) {
						if (pvos->ll_forbidden_combs[iforbidden][ivar] == -1) continue;
						if (pvos->ll_forbidden_combs[iforbidden][ivar] != pvos->l_comb_vars[ivar]) {
							bmatch = false;
							break;
						}
					}
					if (bmatch) {
//						printf("perm %d forbidden by comb %d\n", iperm, iforbidden);
						bforbid = true;
						break;
					}
				}
				if (bforbid) continue; // next perm
				// Now loop through all the match phrases for this stage looking to see whether
				// this perm is already there. We compare to the ll_match_phrase_var_sels where the
				// var_val index is already alligned with the vars index
				for (int imatch=0;imatch<pvos->match_phrases_len;imatch++) {
					if (pvos->l_match_phrase_stage[imatch] != istage) continue;
					bool bmatched = true;
					for (int ii=0;ii<pvos->replace_iopts_len;ii++) {
						int iel = pvos->l_replace_iels[ii];
						int ivar = pair_dict_get(&(pvos->prule->d_var_opts), istage, iel);
						if (pvos->ll_match_phrase_var_sels[imatch][ivar] != perm[ii]) {
							bmatched = false;
//							printf("No match between perm %d and match phrase %d\n", iperm, imatch);
							break;
						}
					}
					if (bmatched) {
//						printf("Match between perm %d and match phrase %d\n", iperm, imatch);
						b_match_exists = true;
						break;
					}
				}
				if (b_match_exists) continue;
				// If the comb does not already exist, create a new one
				printf("Creating new match phrase for perm %d\n", iperm);
				tSPhrase * null_phrase = &(pvos->l_match_phrases[iphrase].phrase);
				pvos->perm_phrase.len = null_phrase->len;
				pvos->perm_phrase.pl = (tSPhraseEl*)bdballoc(pvos->perm_phrase.pl, &(pvos->perm_phrase.num_alloc),
										sizeof(tSPhraseEl), pvos->perm_phrase.len);
//				pvos->perm_phrase.pl = (tSPhraseEl*)vomalloc(sizeof(tSPhraseEl)*null_phrase->len);
				memcpy(pvos->perm_phrase.pl, null_phrase->pl, sizeof(tSPhraseEl)*null_phrase->len);
//				printf("%d perm els. null phrase len %d.\n", pvos->replace_iopts_len, null_phrase->len);
				for (int ii=0;ii<pvos->replace_iopts_len;ii++) {
					int iel = pvos->l_replace_iels[ii];
					int ivar = pair_dict_get(&(pvos->prule->d_var_opts), istage, iel);
					char * val = pvos->pnv[ivar].l_var_vals.pl[perm[ii]];
//					printf("iel: %d, ivar %d, val %s.\n", iel, ivar, val);
					if (val == NULL) continue;
					pvos->perm_phrase.pl[iel].hd = 0;
					pvos->perm_phrase.pl[iel].val = val;
					pvos->perm_phrase.pl[iel].el_type = etRecDefObj;
				}
				match_phrase_append(pvos, istage, false, &(pvos->perm_phrase));
				match_phrase_print(&(pvos->l_match_phrases[pvos->match_phrases_len-1]), pvos->pdbels);
				match_phrase_var_sel_append2(pvos, istage);
				int * new_var_sels = pvos->ll_match_phrase_var_sels[pvos->match_phrases_len-1];
				for (int ii=0;ii<pvos->replace_iopts_len;ii++) {
					int iel = pvos->l_replace_iels[ii];
					int ivar = pair_dict_get(&(pvos->prule->d_var_opts), istage, iel);
					new_var_sels[ivar] = perm[ii];
				}
			}
			
		}
	}
	{
		// Last stage. We build the combos.
		// Again we will use the cartesian_product function. But this time we will use as input all the
		// lengths of all the vars. So that we will create all combinations of all var vals
		for (int ivar=0;ivar<pvos->num_vars;ivar++) {
			pvos->l_var_vals_lens = int_arr_add_val2(	pvos->l_var_vals_lens, &(pvos->var_vals_lens_num_alloc), 
														ivar, pvos->pnv[ivar].l_var_vals.len);
		}
		int num_products = 0;
		cartesian_product2(	pvos->replace_iopts_len, pvos->l_var_vals_lens, &(pvos->l_product_perms), 
							&(pvos->product_perms_num_alloc), &(pvos->product_perms_els_num_alloc), &num_products);
		cartesian_product2(pvos->num_vars, pvos->l_var_vals_lens, &(pvos->l_product_perms), 
							&(pvos->product_perms_num_alloc), &(pvos->product_perms_els_num_alloc), &num_products);
		pvos->l_comb_cand = (int*)bdballoc(	pvos->l_comb_cand, &(pvos->comb_cand_num_alloc), sizeof(int), 
											pvos->prule->num_phrases);
		for (int iperm=0; iperm<num_products;iperm++) {
			int * perm = pvos->l_product_perms[iperm];
			// First check that this perm is not forbidden
			
			bool bforbid = false;
			for (int iforbidden=0;iforbidden<pvos->num_forbidden;iforbidden++) {
				bool bmatch = true;
				for (int ivar=0;ivar<pvos->num_vars;ivar++) {
					if (pvos->ll_forbidden_combs[iforbidden][ivar] == -1) continue;
					if (pvos->ll_forbidden_combs[iforbidden][ivar] != perm[ivar]) {
						bmatch = false;
						break;
					}
				}
				if (bmatch) {
					printf("combo perm %d forbidden by comb %d\n", iperm, iforbidden);
					bforbid = true;
					break;
				}
			}
			if (bforbid) continue; // next perm
			
			// Next for each stage of the rule, find all the match phrases for that stage. See whether
			// the match phrase var indexes match the perm's. 
			bool b_all_stages_found = true;
			for (int istage=0;istage<pvos->prule->num_phrases;istage++) {
//				printf("Stage %d\n", istage);
				bool b_this_stage_matched = false;
				for (int imatch=0; imatch<pvos->match_phrases_len;imatch++) {
					bool b_this_matched = true;
					if (pvos->l_match_phrase_stage[imatch] != istage) continue;
					for (int ivar = 0; ivar < pvos->num_vars; ivar++) {
						if (pvos->ll_match_phrase_var_sels[imatch][ivar] == -1) continue;
						if (pvos->ll_match_phrase_var_sels[imatch][ivar] != perm[ivar]) {
							b_this_matched = false;
							break;									
						}
					}
					if (b_this_matched) {
						pvos->l_comb_cand[istage] = imatch;
						b_this_stage_matched = true;
						break;
					}						
				}
				if (!b_this_stage_matched) {
					b_all_stages_found = false;
					break;
				}
			}
			if (b_all_stages_found) {
				int old_len = pvos->num_combos;
				pvos->num_combos++;
				pvos->ll_match_iphrase_combos = (int **)bdballoc(pvos->ll_match_iphrase_combos, 
																&(pvos->match_iphrase_combos_num_alloc),
																sizeof(int*), pvos->num_combos);
				pvos->ll_match_iphrase_combos[0] = (int *)bdballoc(	pvos->ll_match_iphrase_combos[0], 
																	&(pvos->match_iphrase_combos_els_num_alloc),
																	sizeof(int), 
																	pvos->num_combos* pvos->prule->num_phrases);
				int * pb = pvos->ll_match_iphrase_combos[0];
				for (int icombo=0;icombo<pvos->num_combos;icombo++, pb += pvos->prule->num_phrases) {
					pvos->ll_match_iphrase_combos[icombo] = pb;
				}
				memcpy(pvos->ll_match_iphrase_combos[old_len], pvos->l_comb_cand, sizeof(int)*pvos->prule->num_phrases);
			}
		}
		
	}
	{
		printf("vo summary:\n");
		printf("%d match phrases:\n", pvos->match_phrases_len );
		for (int i=0; i<pvos->match_phrases_len;i++) {
			printf("%d: ", i);
			match_phrase_print(&(pvos->l_match_phrases[i]), pdbels);
		}
		printf("%d match phrase combos.\n", pvos->num_combos);
		for (int i=0; i<pvos->num_combos; i++) {
			printf("%d: ", i);
			for (int j=0; j<pvos->prule->num_phrases;j++) {
				printf("%d, ", pvos->ll_match_iphrase_combos[i][j]);
			}
			printf("\n");
		}

	}
}