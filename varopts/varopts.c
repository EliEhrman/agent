/* File: varopts.c */
#define _GNU_SOURCE
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <search.h>
#include "varopts.h"

int My_variable = 3;
double density = 4.1;

typedef int intpair[2];
typedef _Bool bool;
#define true 1
#define false 0
#define min(a,b) (((a)<(b))?(a):(b))
#define max(a,b) (((a)>(b))?(a):(b))


int num_mallocs = 0;
int num_frees = 0;

void* vomalloc (size_t size) {
	num_mallocs++;
	return malloc(size);
}

void vofree (void* ptr) {
	num_frees++;
	free(ptr);
}

typedef struct SIntPairList {
	intpair * pl;
	int len;
} tSIntPairList;

typedef struct SStrList {
	char ** pl;
	int len;
} tSStrList;

typedef struct SPairDict {
	int num_rows;
	int num_cols;
	int ** ppdata;
} tSPairDict;

typedef int intquad[4];


void clear_pair_dict(tSPairDict * ppd);

void str_list_init(tSStrList * sl) {
	sl->len = 0;
	sl->pl = NULL;
}

void str_list_add_val(tSStrList * sl, char * val) {
	int old_len = sl->len;
	char ** old_pl = sl->pl;
	sl->len++;
	sl->pl = (char **)vomalloc(sl->len*sizeof(char*));
	if (old_len > 0) {
		memcpy(sl->pl, old_pl, old_len*sizeof(char*));
		vofree(old_pl);
	}
	sl->pl[old_len] = val;
}

void str_list_change_one(tSStrList * sl, int idx, char * val) {
	sl->pl[idx] = val;
}

void str_list_reset_with_one_val(tSStrList * sl, char * val) {
	if (sl->len > 0) {
		vofree(sl->pl);
	}
	sl->len = 0;
	str_list_add_val(sl, val);
}

void str_list_clear(tSStrList * sl) {
	if (sl == NULL) {
		return;
	}
	if (sl->len > 0) {
		vofree(sl->pl);
	}
//	vofree(sl);
}

void str_list_print(tSStrList * sl) {
	int i;
	for (i=0; i<sl->len; i++) {
		printf("%s, ", sl->pl[i]);
	}
	printf("\n");
}

typedef struct SNtVars {
	int loc;
	int b_bound;
	int b_must_bind;
	char * val; // not local memory. Strings created outside the python function and therefore will not have their address changed during the lifetime of the function
	double cd;
	int iext_var;
	int b_resolved;
} tSNtVars;

void print_nt_var(tSNtVars * var_opt) {
	printf(	"loc = %d, b_bound = %d, b_must_bind = %d, val = %s, cd = %f, iext_var = %d, b_resolved = %d.\n",
			var_opt->loc, var_opt->b_bound, var_opt->b_must_bind, var_opt->val,
			var_opt->cd, var_opt->iext_var, var_opt->b_resolved);
}

typedef struct SVOApp {
	int bitvec_size;
	char** el_bin_db; // bitvecs, storage for each bitvec is local
	size_t el_bin_db_len;
	struct hsearch_data * d_words;
	char ** l_els;
} tSVOApp;

void * init_capp(void) {
	tSVOApp * papp = (tSVOApp *)vomalloc(sizeof(tSVOApp));
	papp->el_bin_db_len = 0;
	papp->el_bin_db = NULL;
	papp->d_words = NULL;
	papp->l_els = NULL;
	return (void *)papp;
}

void set_el_bitvec_size(void * happ, int size) {
	tSVOApp * papp = (tSVOApp *)happ;
	papp->bitvec_size = size;
}

void init_el_bin_db(void * happ, int size, int dict_space) {
	tSVOApp * papp = (tSVOApp *)happ;
	int i;
	papp->el_bin_db_len = size;
	papp->l_els = (char **)vomalloc(sizeof(char*)*size);
	papp->el_bin_db = (char **)vomalloc(sizeof(char*)*size);
	for (i=0;i<size;i++) {
		papp->el_bin_db[i] = (char*)vomalloc(sizeof(char)*papp->bitvec_size);
	}
	papp->d_words = (struct hsearch_data *)vomalloc(sizeof(struct hsearch_data));
	memset(papp->d_words, 0, sizeof(struct hsearch_data));
	hcreate_r(dict_space, papp->d_words);
}

// The following sets one of the elements of the array created in init. add_el_bin, adds to the db, requiring a new alloc

void set_el_bin(void * happ, int iel, char * word, char *bin) {
	tSVOApp * papp = (tSVOApp *)happ;
	unsigned hret = 0;
	ENTRY e, *ep;

//	{
//		int i;
//		printf("Setting %s for %d in el_bin: ", word, iel);
//		for (i=0;i<papp->bitvec_size;i++) {
//			printf("%hhd",bin[i]);
//		}
//		printf("\n");
//		
//	}
		
	e.key = word;
	e.data = (void *)(size_t)iel;
	hret = hsearch_r(e, ENTER, &ep, papp->d_words);
	if (hret == 0) {
		printf("Error! Failed to add word to d_words dict\n");
	}

	memcpy(papp->el_bin_db[iel], bin, papp->bitvec_size*sizeof(char));
	papp->l_els[iel] = word;
}

// Change the bin for a word/el already in the database
void change_el_bin(void * happ, int iel, char *bin) {
	tSVOApp * papp = (tSVOApp *)happ;
	memcpy(papp->el_bin_db[iel], bin, papp->bitvec_size*sizeof(char));
}

int add_el_bin(void * happ, char * word, char *bin) {
	tSVOApp * papp = (tSVOApp *)happ;
	unsigned hret = 0;
	ENTRY e, *ep;
	size_t old_len = papp->el_bin_db_len;
	char ** old_el_bin_db = papp->el_bin_db;
	char ** old_l_els = papp->l_els;

	papp->el_bin_db_len++;
	papp->el_bin_db = (char**)vomalloc(papp->el_bin_db_len*sizeof(char*));
	papp->l_els = (char **)vomalloc(papp->el_bin_db_len*sizeof(char*));
	memcpy(papp->el_bin_db, old_el_bin_db, old_len*sizeof(char*));
	memcpy(papp->l_els, old_l_els, old_len*sizeof(char*));
	vofree(old_el_bin_db);
	vofree(old_l_els);
	papp->el_bin_db[old_len] = (char*)vomalloc(sizeof(char)*papp->bitvec_size);

	e.key = word;
	e.data = (void *)old_len;
	hret = hsearch_r(e, ENTER, &ep, papp->d_words);
	if (hret == 0) {
		printf("Error! Failed to add new word to d_words dict\n");
	}

	memcpy(papp->el_bin_db[old_len], bin, papp->bitvec_size*sizeof(char));
	papp->l_els[old_len]  = word;
	return papp->el_bin_db_len;
}

char* get_el_bin(tSVOApp * papp, char * word) {
//	tSVOApp * papp = (tSVOApp *)happ;
	unsigned hret = 0;
	ENTRY e, *ep;
	size_t iel;

	e.key = word;
	hret = hsearch_r(e, FIND, &ep, papp->d_words);
	if (hret == 0) {
		printf("Warning. request to get bin for %s which was not found\n", word);
		return NULL;
	}

	iel = (size_t)ep->data;
	printf("get_el_bin for %s. iel = %zu\n", ep->key, iel);
	return papp->el_bin_db[iel];
}

char* check_el_bin(void * happ, char * word) {
	tSVOApp * papp = (tSVOApp *)happ;
	return get_el_bin(papp, word);
}


char * get_word_by_id(tSVOApp * papp, int iel) {
//	tSVOApp * papp = (tSVOApp *)happ;
	printf("get_word_by_id returned %s\n", papp->l_els[iel]);
	return papp->l_els[iel];
}

void free_capp(void * hcapp) {
	tSVOApp * papp = (tSVOApp *)hcapp;
	if (papp->el_bin_db != NULL) {
		int i;
		for (i=0; i<papp->el_bin_db_len; i++) {
			vofree(papp->el_bin_db[i]);
		}
		vofree(papp->el_bin_db);
		vofree(papp->l_els);
	}
	if (papp->d_words != NULL) {
		hdestroy_r(papp->d_words);
		vofree(papp->d_words);
	}
	vofree(papp);
}

typedef struct SVOGG {
	tSVOApp * pApp; // not owned
	int num_el_reps;
	char ** l_els_reps; // array locally owned of char * ptrs that themselves point to parts of a sing;e block allocced for this
	int * l_hd_max; // locally owned. Array of small integers, one for each el
	int l_wlist_vars_len;
	intquad * l_wlist_vars;
	int * l_phrases_len;
	int l_phrases_len_len;
} tSVOGG;

void * init_cgg(void * hcapp) {
	tSVOApp * pvoapp = (tSVOApp *)hcapp;
	tSVOGG * pgg = (tSVOGG *)vomalloc(sizeof(tSVOGG));
	pgg->pApp = pvoapp; // not owned here
	pgg->num_el_reps = 0;
	pgg->l_els_reps = NULL;
	pgg->l_wlist_vars_len = 0;
	pgg->l_wlist_vars = NULL;
	pgg->l_phrases_len = NULL;
	return (void *)pgg;
}

void free_gg(void * hgg) {
	tSVOGG * pgg = (tSVOGG *)hgg;
	if (pgg->l_els_reps != NULL) {
		vofree(pgg->l_els_reps[0]); // first pointer is actually a pointer to the allocated block for all pointers
		vofree(pgg->l_els_reps);
		vofree(pgg->l_hd_max);
	}
	if (pgg->l_wlist_vars != NULL) {
		vofree(pgg->l_wlist_vars);
	}
	if (pgg->l_phrases_len != NULL) {
		vofree(pgg->l_phrases_len);
	}
	vofree(pgg);
//	printf("Memory report: %d allocs and %d frees\n", num_mallocs, num_frees);
}


void set_num_els_reps(void * hgg, int num_reps) {
	tSVOGG * pgg = (tSVOGG *)hgg;
	int i;
	char * pbuf;
	pgg->num_el_reps = num_reps;
	pgg->l_els_reps = (char **)vomalloc(num_reps*sizeof(char *));
	pgg->l_hd_max = (int *)vomalloc(num_reps*sizeof(int));
	char * buf = (char *)vomalloc(num_reps * pgg->pApp->bitvec_size * sizeof(char *));
	for (i=0, pbuf = buf; i<num_reps; i++, pbuf += pgg->pApp->bitvec_size * sizeof(char)) {
		pgg->l_els_reps[i] = pbuf;
	}
}

void set_els_rep(void * hgg, char * bitvec, int hd, int iel) {
	tSVOGG * pgg = (tSVOGG *)hgg;
	//	pgg->l_els_reps[iel] = bitvec;
	memcpy(pgg->l_els_reps[iel], bitvec, pgg->pApp->bitvec_size * sizeof(char));
	pgg->l_hd_max[iel] = hd;
	//	{
	//		int j;
	//		printf("All els_reps till now for this gg.\n");
	//		for (j=0; j<=iel; j++) {
	//			int i;
	//			printf("els_rep for %d: ", j);
	//			for (i=0; i<pgg->pApp->bitvec_size; i++) {
	//				printf("%hhd", pgg->l_els_reps[j][i]);
	//			}
	//			printf("\n");
	//		}
	//		printf("\n");
	//	}
}

void set_l_wlist_vars_len(void * hgg, int size) {
	tSVOGG * pgg = (tSVOGG *)hgg;
	pgg->l_wlist_vars_len = size;
	pgg->l_wlist_vars = (intquad *)vomalloc(size*sizeof(intquad));
}

void set_l_wlist_var(void * hgg, int * varquad, int ivar) {
	tSVOGG * pgg = (tSVOGG *)hgg;
	memcpy(&(pgg->l_wlist_vars[ivar]), varquad, sizeof(intquad));
//	{
//		int i;
//		printf("wlist_var for %d: [", ivar);
//		for (i=0; i<(sizeof(intquad)/sizeof(int)); i++) {
//			printf("%d, ", pgg->l_wlist_vars[ivar][i]);
//		}
//		printf("]\n");
//	}
}

void set_l_phrases_len(void * hgg, int * l_phrases_len, int len) {
	tSVOGG * pgg = (tSVOGG *)hgg;

	pgg->l_phrases_len_len = len;
	pgg->l_phrases_len = (int *)vomalloc(len*sizeof(int));
	memcpy(pgg->l_phrases_len, l_phrases_len, len*sizeof(int));
//	{
//		int i;
//		printf("set_l_phrases_len: l_phrases_len: [");
//		for (i=0; i<pvos->l_phrases_len_len; i++) {
//			printf("%d,", pvos->l_phrases_len[i]);
//		}
//		printf("]\n");
//	}
}

typedef struct SVOState {
	tSVOGG * pgg; // not owned here
	tSNtVars * pnv;
	int num_vars;
	int curr_var_num;
//	int * l_phrases_len; // pointer to an IntArray created at the Python level - no malloc or free
//	int l_phrases_len_len;
	int * l_phrase_starts; // 1 longer than l_phrases_len_len
	tSStrList* l_var_vals; // len num_vars
	int * l_var_locs; // len num_vars
	//	int num_loc_pairs;
	intpair * l_var_loc_pairs; // len num_vars
	tSIntPairList * l_var_all_locs; // len num_vars
	tSPairDict * d_var_opts;
	char *** ll_src_pat;
	int ** ll_hd_max;
} tSVOState;

//tSNtVars * pnv = NULL;
//int num_vars = 0;
//int curr_var_num = 0;

void * init_vo(void * hgg) {
	tSVOState * pvos = (tSVOState *)vomalloc(sizeof(tSVOState));
	pvos->pgg = (tSVOGG *)hgg;
	pvos->pnv = NULL;
	pvos->num_vars = 0;
	pvos->curr_var_num = 0;
	pvos->l_var_vals = NULL;
	pvos->l_var_locs = NULL;
	pvos->l_phrase_starts = NULL;
	pvos->l_var_loc_pairs = NULL;
	pvos->l_var_all_locs = NULL;
	pvos->d_var_opts = NULL;
	pvos->ll_src_pat = NULL;
	pvos->ll_hd_max = NULL;
	return (void *)pvos;
}

void free_vo(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;

	if (pvos->ll_src_pat != NULL) {
		int iphrase;
		for (iphrase=0;iphrase<pvos->pgg->l_phrases_len_len;iphrase++) {
			vofree(pvos->ll_src_pat[iphrase]);
			vofree(pvos->ll_hd_max[iphrase]);
		}
		vofree(pvos->ll_src_pat);
		vofree(pvos->ll_hd_max);
	}
	if (pvos->num_vars > 0) {
		if (pvos->l_var_vals != NULL) {
			int il;
			for (il=0; il<pvos->num_vars; il++) {
//				printf("deleting: ");
//				str_list_print(&(pvos->l_var_vals[il]));
				str_list_clear(&(pvos->l_var_vals[il]));
			}
			vofree(pvos->l_var_vals);
		}
		if (pvos->l_var_locs != NULL) {
			vofree(pvos->l_var_locs);
		}
		vofree(pvos->pnv);
	}
	if (pvos->l_phrase_starts != NULL) {
		vofree(pvos->l_phrase_starts);
	}
	if (pvos->l_var_loc_pairs != NULL) {
		vofree(pvos->l_var_loc_pairs);
	}
	if (pvos->l_var_all_locs != NULL) {
		int il;
		for (il=0; il<pvos->num_vars; il++) {
			vofree(pvos->l_var_all_locs[il].pl);
		}
		vofree(pvos->l_var_all_locs);
	}
	if (pvos->d_var_opts != NULL) {
		clear_pair_dict(pvos->d_var_opts);
	}

	vofree(pvos);
//	printf("Memory report: %d allocs and %d frees, %d unfreed\n", num_mallocs, num_frees, num_mallocs - num_frees);
}


tSPairDict * create_pair_dict(int num_rows, int num_cols) {
	tSPairDict * ppd = (tSPairDict *)vomalloc(sizeof(tSPairDict));
	int r,c;

	ppd->num_rows = num_rows;
	ppd->num_cols = num_cols;
	ppd->ppdata = (int **)vomalloc(sizeof(int*)*num_rows);
	for (r=0; r<num_rows; r++) {
		ppd->ppdata[r] = (int *)vomalloc(sizeof(int)*num_cols);
		for (c=0; c<num_cols; c++) {
			ppd->ppdata[r][c] = -1;
		}
	}
	return ppd;
}

void clear_pair_dict(tSPairDict * ppd) {
	int r;

	for (r=0; r<ppd->num_rows; r++) {
		vofree(ppd->ppdata[r]);
	}
	vofree(ppd->ppdata);

	vofree(ppd);
}

int pair_dict_get(tSPairDict * ppd, int r, int c) {
	assert(r < ppd->num_rows && c < ppd->num_cols);
	return ppd->ppdata[r][c];
}

void pair_dict_set(tSPairDict * ppd, int r, int c, int val) {
	assert(r < ppd->num_rows && c < ppd->num_cols);
	ppd->ppdata[r][c] = val;
}

void pair_dict_print(tSPairDict * ppd) {
	int r, c;
	printf("Pair dict: \n");
	for (r=0; r<ppd->num_rows; r++) {
		printf("[ ");
		for (c=0; c<ppd->num_cols; c++) {
			printf("%d,\t", ppd->ppdata[r][c]);
		}
		printf(" ],\n");
	}
}

void pair_dict_grow(tSPairDict * ppd, int num_rows, int num_cols) {
	int r,c;
	int ** old_ppdata = ppd->ppdata;
	int old_num_rows = ppd->num_rows;
	int old_num_cols = ppd->num_cols;

	assert(num_rows >= old_num_rows && num_cols >= old_num_cols);

	ppd->ppdata = (int **)vomalloc(sizeof(int*)*num_rows);
	for (r=0; r<num_rows; r++) {
		int start_col = 0;
		ppd->ppdata[r] = (int *)vomalloc(sizeof(int)*num_cols);
		if (r < old_num_rows) {
			int * old_row = old_ppdata[r];
			memcpy(ppd->ppdata[r], old_row, sizeof(int)*old_num_cols);
			vofree(old_row);
			start_col = old_num_cols;
		}
		for (c=start_col; c<num_cols; c++) {
			ppd->ppdata[r][c] = -1;
		}
	}
	vofree(old_ppdata);


	ppd->num_rows = num_rows;
	ppd->num_cols = num_cols;

}

void set_num_vars(void * hvos, int n) {
	int old_num_vars;
	tSNtVars * old_pnv;
	tSVOState * pvos = (tSVOState *)hvos;

	old_num_vars = pvos->num_vars;
	pvos->num_vars = n;
	old_pnv = pvos->pnv;
	pvos->pnv = (tSNtVars *)vomalloc(sizeof(tSNtVars) * pvos->num_vars);
	memcpy(pvos->pnv, old_pnv, sizeof(tSNtVars) * old_num_vars);
	if (old_num_vars > 0) {
		vofree(old_pnv);
	}
}

//void set_l_phrases_len(void * hvos, int * l_phrases_len, int len) {
//	tSVOState * pvos = (tSVOState *)hvos;
//
//	pvos->l_phrases_len = l_phrases_len;
//	pvos->l_phrases_len_len = len;
////	{
////		int i;
////		printf("set_l_phrases_len: l_phrases_len: [");
////		for (i=0; i<pvos->l_phrases_len_len; i++) {
////			printf("%d,", pvos->l_phrases_len[i]);
////		}
////		printf("]\n");
////	}
//}


void cnt_vars(void * hvos, int loc, int b_bound, int b_must_bind, char * val, double cd, int iext_var) {
	tSNtVars nv;
	tSVOState * pvos = (tSVOState *)hvos;
	nv.loc = loc, nv.b_bound = b_bound, nv.b_must_bind = b_must_bind, nv.val = val;
	nv.cd = cd, nv.iext_var = iext_var; nv.b_resolved = 0;
	pvos->pnv[pvos->curr_var_num++] = nv;

	//	int i;
	//	for (i=0; i<curr_var_num; i++) {
	//		printf("loc: %d, val: %s\n", pnv[i].loc, pnv[i].val);
	//	}
//	return nv;
}

int bin_diff_count(char * a, char * b, int size) {
	int i;
	char *pa, *pb;
	int num_diffs = 0;
	printf("a bitvec: ");
	for (i=0, pa = a; i<size;i++,pa++) {
		printf("%hhd", *pa);
	}
	printf("\n");
	printf("b bitvec: ");
	for (i=0, pb = b; i<size;i++,pb++) {
		printf("%hhd", *pb);
	}
	printf("\n");
	printf("bin_diff_count: ");
	for (i=0, pa = a, pb = b; i<size;i++,pa++,pb++) {
		if (*pa != *pb ) {
			num_diffs++;
		}
	}
	printf("num diffs = %d\n", num_diffs);
	return num_diffs;
}

int bin_idx_best_match(char ** db, char * q, int dbsize, int binsize) {
	int idx_best = 0, best_count = 0;
	int i;
	char **pdb;
	for (i=0, pdb=db;i<dbsize;i++, pdb++) {
		int j;
		char *pq, *ppdb;
		int match_count = 0;
		for (j=0,pq=q,ppdb=*pdb;j<binsize;j++, pq++, ppdb++) {
			if (*pq==*ppdb) {
				match_count++;
			}
		}
		if (match_count > best_count) {
			best_count = match_count;
			idx_best = i;
		}
	}
	printf("bin_idx_best_match returning best = %d, match_count = %d\n", idx_best, best_count);
	return idx_best;
}

int do_vo(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;
	tSVOApp * papp = pvos->pgg->pApp;
	int i,j;
	int num_loc_pairs = 0;
	int max_phrase_len = 0;

	pvos->l_var_vals = (tSStrList *)vomalloc(pvos->num_vars*sizeof(tSStrList));
	pvos->l_var_locs = (int *)vomalloc(pvos->num_vars*sizeof(int));
	for (i=0; i<pvos->num_vars; i++) {
		str_list_init(&(pvos->l_var_vals[i]));
		if (pvos->pnv[i].b_bound) {
			str_list_add_val(&(pvos->l_var_vals[i]), pvos->pnv[i].val);
//			pvos->l_var_vals[i] = pvos->pnv[i].val;
		}
		else {
			str_list_add_val(&(pvos->l_var_vals[i]), NULL);
//			pvos->l_var_vals[i] = NULL;
		}
		pvos->l_var_locs[i] = pvos->pnv[i].loc;
	}

//	printf("pvos->pgg->l_phrases_len_len = %d\n", pvos->pgg->l_phrases_len_len);
//	{
//		int k;
//		printf("pvos->pgg->l_phrases_len = [");
//		for (k=0; k< pvos->pgg->l_phrases_len_len; k++ ) {
//			printf("%d, ", pvos->pgg->l_phrases_len[k]);
//		}
//		printf("]\n");
//	}
	pvos->l_phrase_starts = (int *)vomalloc((pvos->pgg->l_phrases_len_len+1)*sizeof(int));
	pvos->l_phrase_starts[0] = 0;
	for (i=0; i<pvos->pgg->l_phrases_len_len; i++) {
		pvos->l_phrase_starts[i+1] = pvos->l_phrase_starts[i] + pvos->pgg->l_phrases_len[i];
		if (pvos->pgg->l_phrases_len[i] > max_phrase_len) {
			max_phrase_len = pvos->pgg->l_phrases_len[i];
		}
	}
	for (i=0; i<pvos->num_vars; i++) {
		for (j=0; j<= pvos->pgg->l_phrases_len_len; j++ ) {
			if (pvos->l_var_locs[i] < pvos->l_phrase_starts[j]) {
				num_loc_pairs++;
				break;
			}
		}
	}
	if (num_loc_pairs != pvos->num_vars) {
		printf("Coding error! num_loc_pairs != pvos->num_vars");
	}
	pvos->l_var_loc_pairs = (intpair *)vomalloc(pvos->num_vars*sizeof(intpair));
	pvos->l_var_all_locs = (tSIntPairList *)vomalloc(pvos->num_vars*sizeof(tSIntPairList));
	pvos->d_var_opts = create_pair_dict(pvos->pgg->l_phrases_len_len, max_phrase_len);
	{
		int icurr_loc = 0;
		int iopt, itlen;
		for (iopt=0; iopt<pvos->num_vars; iopt++) {
			for (itlen=0; itlen<= pvos->pgg->l_phrases_len_len; itlen++ ) {
				if (pvos->l_var_locs[iopt] < pvos->l_phrase_starts[itlen]) {
					int r = itlen-1;
					int c = pvos->l_var_locs[iopt]-pvos->l_phrase_starts[itlen-1];
					pvos->l_var_loc_pairs[icurr_loc][0] = r;
					pvos->l_var_loc_pairs[icurr_loc][1] = c;
					pvos->l_var_all_locs[icurr_loc].len = 1;
					pvos->l_var_all_locs[icurr_loc].pl = (intpair*)vomalloc(sizeof(intpair));
					pvos->l_var_all_locs[icurr_loc].pl[0][0] = r;
					pvos->l_var_all_locs[icurr_loc].pl[0][1] = c;
					pair_dict_set(pvos->d_var_opts, r, c, icurr_loc);
					icurr_loc++;
					break;
				}
			}
		}
//		printf("l_var_loc_pairs: [");
//		for (icurr_loc=0; icurr_loc<pvos->num_vars; icurr_loc++) {
//			printf("(%d, %d), ", pvos->l_var_loc_pairs[icurr_loc][0] , pvos->l_var_loc_pairs[icurr_loc][1] );
//		}
//		printf("]\n");
//		printf("l_var_all_locs: [");
//		for (icurr_loc=0; icurr_loc<pvos->num_vars; icurr_loc++) {
//			int ipair;
//			tSIntPairList * ppl = &(pvos->l_var_all_locs[icurr_loc]);
//			printf(" [ ");
//			for (ipair=0; ipair<ppl->len; ipair++) {
//				printf("(%d, %d), ", ppl->pl[0][0] , ppl->pl[0][1] );
//			}
//			printf(" ], ");
//		}
//		printf("]\n");
//		pair_dict_print(pvos->d_var_opts);
	}
	{
		int iphrase;
		pvos->ll_src_pat = (char ***)vomalloc(pvos->pgg->l_phrases_len_len*sizeof(char**));
		pvos->ll_hd_max = (int **)vomalloc(pvos->pgg->l_phrases_len_len*sizeof(int*));
		for (iphrase=0;iphrase<pvos->pgg->l_phrases_len_len;iphrase++) {
			int iel;
			pvos->ll_src_pat[iphrase] = (char**)vomalloc(pvos->pgg->l_phrases_len[iphrase]*sizeof(char*));
			pvos->ll_hd_max[iphrase] = (int*)vomalloc(pvos->pgg->l_phrases_len[iphrase]*sizeof(int));
			for (iel=0; iel<pvos->pgg->l_phrases_len[iphrase];iel++) {
				pvos->ll_src_pat[iphrase][iel] = pvos->pgg->l_els_reps[pvos->l_phrase_starts[iphrase]+iel];
				pvos->ll_hd_max[iphrase][iel] = pvos->pgg->l_hd_max[pvos->l_phrase_starts[iphrase]+iel];
			}
		}
//		printf("ll_src_pat: \n");
//		for (iphrase=0;iphrase<pvos->pgg->l_phrases_len_len;iphrase++) {
//			int iel;
//			printf("phrase: %d: \n", iphrase);
//			for (iel=0; iel<pvos->pgg->l_phrases_len[iphrase];iel++) {
//				int ib;
//				printf("iel: %d. ", iel);
//				for (ib=0; ib<pvos->pgg->pApp->bitvec_size; ib++) {
//					printf("%hhd", pvos->ll_src_pat[iphrase][iel][ib]);
//				}
//				printf("\n");
//			}
//		}
	}
	printf("7\n");
	{
		int ivar;
		int iopt_now = pvos->num_vars;
		int num_new_vars = 0;
//		int * var_loc_adds;
		for (ivar=0; ivar < pvos->pgg->l_wlist_vars_len; ivar++) {
			int * wlist_var = pvos->pgg->l_wlist_vars[ivar];
			int src_istage = wlist_var[0];
			int src_iel = wlist_var[1];
			int iopt = pair_dict_get(pvos->d_var_opts, src_istage, src_iel);
			if (iopt == -1) {
				// This code is not quite right. Once we add vars, later refs to the
				// the same var will not be -1. Better to add as necessary and not pre-count
				num_new_vars++;
			}
		}
		if (num_new_vars > 0) {
			int old_num_vars = pvos->num_vars;
			pvos->num_vars += num_new_vars;
			{
				tSNtVars * old_pnv = pvos->pnv;
				pvos->pnv = (tSNtVars *)vomalloc(sizeof(tSNtVars) * pvos->num_vars);
				memcpy(pvos->pnv, old_pnv, sizeof(tSNtVars) * old_num_vars);
				vofree(old_pnv);
			}
			{
				tSStrList * old_l_var_vals = pvos->l_var_vals;				
				pvos->l_var_vals = (tSStrList*)vomalloc(pvos->num_vars*sizeof(tSStrList));
				memcpy(pvos->l_var_vals, old_l_var_vals, sizeof(tSStrList) * old_num_vars);
				vofree(old_l_var_vals);
				for (ivar=old_num_vars; ivar < pvos->num_vars; ivar++) {
					str_list_init(&(pvos->l_var_vals[ivar]));
				}
			}
//			do the same for l_var_all_locs but figure out the pair list thingy
			{
				tSIntPairList * old_var_locs = pvos->l_var_all_locs;
				int ivar;
				pvos->l_var_all_locs = (tSIntPairList *)vomalloc(pvos->num_vars*sizeof(tSIntPairList));
				memcpy(pvos->l_var_all_locs, old_var_locs, sizeof(tSIntPairList)*old_num_vars);
				for (ivar=old_num_vars; ivar < pvos->num_vars; ivar++) {
					pvos->l_var_all_locs[ivar].len = 2;
					pvos->l_var_all_locs[ivar].pl = (intpair*)vomalloc(2 * sizeof(intpair));
				}
				vofree(old_var_locs);
			}
			iopt_now = old_num_vars;
		}
//		var_loc_adds = (int *)vomalloc(pvos->num_vars*sizeof(int));
//		memset(var_loc_adds, 0, sizeof(int)*pvos->num_vars);
//		printf("l_wlist_vars:\n");
//		printf("l_wlist_vars_len = %d\n", pvos->pgg->l_wlist_vars_len);
		for (ivar=0; ivar < pvos->pgg->l_wlist_vars_len; ivar++) {
			int * wlist_var = pvos->pgg->l_wlist_vars[ivar];
			int src_istage = wlist_var[0];
			int src_iel = wlist_var[1];
			int dest_istage = wlist_var[2];
			int dest_iel = wlist_var[3];
//			printf("%d: src: %d, %d. dest: %d, %d.\n", ivar, src_istage, src_iel, dest_istage, dest_iel);
			int iopt = pair_dict_get(pvos->d_var_opts, src_istage, src_iel);
			printf("ivar: %d. iopt = %d. iopt_now = %d. pvos->num_vars = %d\n", ivar, iopt, iopt_now, pvos->num_vars);
			if (iopt == -1) {
				tSNtVars nv;
				nv.loc = pvos->l_phrase_starts[src_istage]+src_iel, nv.b_bound = 0, nv.b_must_bind = 0, nv.val = NULL;
				nv.cd = 0., nv.iext_var = -1, nv.b_resolved = 0;
				pvos->pnv[iopt_now] = nv;
				pair_dict_set(pvos->d_var_opts, src_istage, src_iel, iopt_now);
				pair_dict_set(pvos->d_var_opts, dest_istage, dest_iel, iopt_now);
				pvos->l_var_all_locs[iopt_now].pl[0][0] = src_istage;
				pvos->l_var_all_locs[iopt_now].pl[0][1] = src_iel;
				pvos->l_var_all_locs[iopt_now].pl[1][0] = dest_istage;
				pvos->l_var_all_locs[iopt_now].pl[1][1] = dest_iel;
				str_list_add_val(&(pvos->l_var_vals[iopt_now]), NULL);
				iopt_now++;
			}
			else {
				tSIntPairList * p_var_locs = &(pvos->l_var_all_locs[iopt]);
				int old_len = p_var_locs->len;
				intpair * old_pl = p_var_locs->pl;
				printf("var_locs.len was %d\n", p_var_locs->len);
				p_var_locs->len++;
				p_var_locs->pl = (intpair*)vomalloc(p_var_locs->len * sizeof(intpair));
				memcpy(p_var_locs->pl, old_pl, old_len*sizeof(intpair));
				vofree(old_pl);
				p_var_locs->pl[old_len][0] = dest_istage, p_var_locs->pl[old_len][1] = dest_iel;
				pair_dict_set(pvos->d_var_opts, dest_istage, dest_iel, iopt);
//				var_loc_adds[iopt]++;
			}
			printf("end if iopt == -1\n");
		}
//		vofree(var_loc_adds);
//		{
//			int icurr_loc;
//			printf("l_var_all_locs: [");
//			for (icurr_loc=0; icurr_loc<pvos->num_vars; icurr_loc++) {
//				int ipair;
//				tSIntPairList * ppl = &(pvos->l_var_all_locs[icurr_loc]);
//				printf(" [ ");
//				for (ipair=0; ipair<ppl->len; ipair++) {
//					printf("(%d, %d), ", ppl->pl[ipair][0] , ppl->pl[ipair][1] );
//				}
//				printf(" ], ");
//			}
//			printf("]\n");
//			pair_dict_print(pvos->d_var_opts);
//		}
	}

	{
		int iopt;
		for (iopt=0; iopt<pvos->num_vars; iopt++) {
			tSNtVars * var_opt = &(pvos->pnv[iopt]);
			tSIntPairList * var_all_locs = &(pvos->l_var_all_locs[iopt]);
			int src_istage = var_all_locs->pl[0][0];
			int src_iel = var_all_locs->pl[0][1];
			if (!var_opt->b_resolved) {
				bool b_set_by_int = true;
				char* int_els_rep = pvos->ll_src_pat[src_istage][src_iel];
				int int_hd_max = pvos->ll_hd_max[src_istage][src_iel];
				if (var_opt->iext_var >= 0) {
//					ext_var_opt = pvos->pnv[var_opt.iext_var]
					char * ext_els_rep = get_el_bin(papp, var_opt->val);
					int ext_hd_max = 0;
					int max_of_max_hd;
					int bin_diff = bin_diff_count(int_els_rep, ext_els_rep,papp->bitvec_size);
					if (var_opt->cd >= 0.0 ) {
						ext_hd_max = (int)((double)(papp->bitvec_size) * (1. - var_opt->cd));
					}
					max_of_max_hd = max(int_hd_max, ext_hd_max);
					printf("bin_diff = %d, max_of_max_hd = %d\n", bin_diff, max_of_max_hd);
					if (bin_diff > max_of_max_hd) {
						printf("Exiting! \n");
						return 0;
					}
					if (int_hd_max > ext_hd_max) {
						pvos->ll_src_pat[src_istage][src_iel] = ext_els_rep;
						pvos->ll_hd_max[src_istage][src_iel] = ext_hd_max;
						b_set_by_int = false;
						var_opt->b_resolved=true;
					}
				}
				if (b_set_by_int) {
					int nd_el_match_idx = bin_idx_best_match(	papp->el_bin_db, int_els_rep,
																papp->el_bin_db_len, papp->bitvec_size);
					char *el_word = get_word_by_id(papp, nd_el_match_idx);
					bool b_exact = (pvos->ll_hd_max[src_istage][src_iel] == 0);
					var_opt->b_bound=b_exact, var_opt->b_must_bind=b_exact, var_opt->val = el_word;
					var_opt->b_resolved = true;
					var_opt->cd = 1.-((double)((pvos->ll_hd_max[src_istage][src_iel]) / papp->bitvec_size));
					if (b_exact) {
						str_list_reset_with_one_val(&(pvos->l_var_vals[iopt]), el_word);
					}
				}
			}
		}
		{
			
		}
		{
			int i;
			printf("ll_hd_max: \n");
			for (i=0; i<pvos->pgg->l_phrases_len_len; i++) {
				int j;
				printf("stage %d: [", i);
				for (j=0; j<pvos->pgg->l_phrases_len[i];j++) {
					printf("%d, ", pvos->ll_hd_max[i][j]);
				}
				printf("], ");
			}
			printf("\n");
			printf("ll_src_pat: \n");
			for (i=0; i<pvos->pgg->l_phrases_len_len; i++) {
				int j;
				printf("stage %d: [", i);
				for (j=0; j<pvos->pgg->l_phrases_len[i];j++) {
					int k;
					for (k=0;k<papp->bitvec_size;k++) {
						printf("%hhd", pvos->ll_src_pat[i][j][k]);
					}
					printf(", ");
				}
				printf("], ");
			}
			printf("\n");
			printf("l_vars: \n");
			for (iopt=0; iopt<pvos->num_vars; iopt++) {
				tSNtVars * var_opt = &(pvos->pnv[iopt]);
				print_nt_var(var_opt);
			}
			printf("l_var_vals: \n");
			for (iopt=0; iopt<pvos->num_vars; iopt++) {
				tSStrList * sl = &(pvos->l_var_vals[iopt]);
				printf("%d: ", iopt);
				str_list_print(sl);
			}
		}
    }
	return 1;
}