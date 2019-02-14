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
	char * val;
	double cd;
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

void phrase_el_init(tSPhraseEl* pel, teRecDefType tet, char * val, double cd) {
	pel->el_type = tet;
	pel->val = val;
	pel->cd = cd;
}

void phrase_el_print(tSPhraseEl* pel) {
	printf("%s, val: %s, cd: %lf\n", rec_def_type_names[(int)(pel->el_type)], pel->val, pel->cd);
}

void phrase_print(tSPhrase * pphrase) {
	int i;
	for (i=0;i<pphrase->len;i++) {
		phrase_el_print(&(pphrase->pl[i]));
	}
}

//void phrase_free(tSPhrase * pphrase) {
//	int iel;
//	for (iel=0;iel<pphrase->len;iel++) {
//		vofree(pphrase->pl)
//	}
//}

void match_phrase_print(tSMatchPhrase * ppm) {
	printf("stage: %d, b_matched: %s, phrase: \n", ppm->istage, (ppm->b_matched ? "True" : "False"));
	phrase_print(&(ppm->phrase));
	
}

void match_phrase_set(tSMatchPhrase * ppm, int istage, bool b_matched, tSPhrase * phrase) {
	int iel;
	ppm->istage = istage;
	ppm->b_matched = b_matched;
	ppm->phrase.len = phrase->len;
//	ppm->phrase.pl = (tSPhraseEl *)vomalloc(ppm->phrase.len * sizeof(tSPhraseEl));
	for (iel=0;iel<ppm->phrase.len;iel++) {
		ppm->phrase.pl[iel].el_type = phrase->pl[iel].el_type;
		ppm->phrase.pl[iel].val = phrase->pl[iel].val;
		ppm->phrase.pl[iel].cd = phrase->pl[iel].cd;
	}
	
}

typedef struct SNtVars {
	int loc;
	int b_bound;
	int b_must_bind;
	char * val; // not local memory. Strings created outside the python function and therefore will not have their address changed during the lifetime of the function
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
	int num_vars_alloc;
	int num_vars;
	tSNtVars * pnv;
	int num_ext_vars;
	int max_phrase_len;
	int phrase_starts_num_alloc;
	int * l_phrase_starts; // 1 longer than l_phrases_len_len
	int var_vals_num_alloc;
	tSStrList* l_var_vals; // len num_vars
	int var_locs_num_alloc;
	int * l_var_locs; // len num_vars
	int var_all_locs_num_alloc;
	tSIntPairList * l_var_all_locs; // len num_vars
	tSPairDict d_var_opts;
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
	int b_unbound_num_alloc;
	bool * l_b_unbound;
	int i_unbound_num_alloc;
	int * l_i_unbound;
	int i_null_phrases_num_alloc;
	int i_null_phrases_len;
	int * l_i_null_phrases;
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

} tSVOState;

void * create_vo(void * hcdb_rules, void * hcdb_all, void * hcdb_story) {
	signal(SIGSEGV, handler);   // install our handler
	printf("handler installed.\n");
	tSVOState * pvos = (tSVOState *)bdbmalloc2(sizeof(tSVOState), 1);
	pvos->pdbrules = (tSBDBApp *) hcdb_rules;
	pvos->pdb = (tSBDBApp *) hcdb_all;
	pvos->pdbstory = (tSBDBApp *) hcdb_story;
//	pvos->pnv = (tSNtVars *)bdbmalloc2(sizeof(tSNtVars), 1);
	return pvos;
}

void init_vo(void * hvos, int irule_rec, char * db_name, int call_num) {
	tSVOState * pvos = (tSVOState *)hvos;
	pvos->rule_rec = &(pvos->pdb->db[pvos->pdbrules->rec_ptrs[irule_rec * pvos->pdbrules->bitvec_size]]);
	pvos->prule = (tSRuleRec *)&(pvos->pdbrules->rule_data[irule_rec]);
	
	tSBDBApp * pdbrules = pvos->pdbrules;
	tSBDBApp * pdb = pvos->pdb;
	tSRuleRec * prule = pvos->prule;
	
	pvos->num_vars = prule->num_vars;
	pvos->pnv = (tSNtVars *)bdballoc(pvos->pnv, &(pvos->num_vars_alloc), sizeof(tSNtVars), pvos->num_vars);
	for (int ivar = 0; ivar < prule->num_vars; ivar++ ) {
		tSVarData * pvar = &(prule->var_tbl[ivar]);
		pvos->pnv[ivar].l_var_vals.len = 1;
		pvos->pnv[ivar].l_var_vals.pl = (char **)bdballoc(	pvos->pnv[ivar].l_var_vals.pl, &(pvos->pnv[ivar].l_var_vals.num_alloc), 
															sizeof(char*), pvos->pnv[ivar].l_var_vals.len);
		if (pvar->hd_thresh == 0) {
			pvos->pnv[ivar].l_var_vals.pl[0] = pvar->default_src_pat;
		}
		else {
			pvos->pnv[ivar].l_var_vals.pl[0] = NULL;
		}
		pvos->pnv[ivar].hd = pvar->hd_thresh;
	}
}

void set_ext_rperm(void * hvos, int rperm) {
	tSVOState * pvos = (tSVOState *)hvos;
	pvos->ext_rperm = rperm;
}

void add_ext_var(void * hvos, int ivar, int b_bound, int b_must_bind, int iel, int hd, int iext_var ) {
	tSBDBApp * pdb = pvos->pdb;
	int rlen = get_rec_len(pdb, rperm);
	char *	pdbrec = get_rec(pdb, rperm);
	
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

void do_vo(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;
	tSBDBApp * pdbrules = pvos->pdbrules;
	tSBDBApp * pdb = pvos->pdb;
	tSRuleRec * prule = pvos->prule;
}