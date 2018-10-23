/* File: varopts.c */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "varopts.h"

int My_variable = 3;
double density = 4.1;

typedef int intpair[2];

typedef struct SIntPairList {
	intpair * pl;
	int len;
} tSIntPairList;

typedef struct SPairDict {
	int num_rows;
	int num_cols;
	int ** ppdata;
} tSPairDict;

typedef int intquad[4];


void clear_pair_dict(tSPairDict * ppd);


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


typedef struct SNtVars {
	int loc;
	int b_bound;
	int b_must_bind;
	char * val; // not local memory. Strings created outside the python function and therefore will not have their address changed during the lifetime of the function
	double cd;
	int iext_var;
	int b_resolved;
} tSNtVars;

typedef struct SVOApp {
	int bitvec_size;
} tSVOApp;

void * init_capp(void) {
	tSVOApp * pvoapp = (tSVOApp *)vomalloc(sizeof(tSVOApp));
	return (void *)pvoapp;
}

void set_el_bitvec_size(void * happ, int size) {
	tSVOApp * pvoapp = (tSVOApp *)happ;
	pvoapp->bitvec_size = size;
}


void free_capp(void * hcapp) {
	tSVOApp * pvoapp = (tSVOApp *)hcapp;
	vofree(pvoapp);
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
	char ** l_var_vals; // len num_vars
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
		vofree(pvos->pnv);
		if (pvos->l_var_vals != NULL) {
			vofree(pvos->l_var_vals);
		}
		if (pvos->l_var_locs != NULL) {
			vofree(pvos->l_var_locs);
		}
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

void do_vo(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;
	int i,j;
	int num_loc_pairs = 0;
	int max_phrase_len = 0;

	pvos->l_var_vals = (char **)vomalloc(pvos->num_vars*sizeof(char*));
	pvos->l_var_locs = (int *)vomalloc(pvos->num_vars*sizeof(int));
	for (i=0; i<pvos->num_vars; i++) {
		if (pvos->pnv[i].b_bound) {
			pvos->l_var_vals[i] = pvos->pnv[i].val;
		}
		else {
			pvos->l_var_vals[i] = NULL;
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
	assert(num_loc_pairs == pvos->num_vars);
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
				char ** old_l_var_vals = pvos->l_var_vals;
				pvos->l_var_vals = (char **)vomalloc(pvos->num_vars*sizeof(char*));
				memcpy(pvos->l_var_vals, old_l_var_vals, sizeof(char *) * old_num_vars);
				vofree(old_l_var_vals);
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
		for (ivar=0; ivar < pvos->pgg->l_wlist_vars_len; ivar++) {
			int * wlist_var = pvos->pgg->l_wlist_vars[ivar];
			int src_istage = wlist_var[0];
			int src_iel = wlist_var[1];
			int dest_istage = wlist_var[2];
			int dest_iel = wlist_var[3];
//			printf("%d: src: %d, %d. dest: %d, %d.\n", ivar, src_istage, src_iel, dest_istage, dest_iel);
			int iopt = pair_dict_get(pvos->d_var_opts, src_istage, src_iel);
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
				pvos->l_var_vals[iopt_now] = NULL;
				iopt_now++;
			}
			else {
				tSIntPairList * p_var_locs = &(pvos->l_var_all_locs[iopt]);
				int old_len = p_var_locs->len;
				intpair * old_pl = p_var_locs->pl;
//				printf("var_locs.len was %d\n", p_var_locs->len);
				p_var_locs->len++;
				p_var_locs->pl = (intpair*)vomalloc(p_var_locs->len * sizeof(intpair));
				memcpy(p_var_locs->pl, old_pl, old_len*sizeof(intpair));
				vofree(old_pl);
				p_var_locs->pl[old_len][0] = dest_istage, p_var_locs->pl[old_len][1] = dest_iel;
				pair_dict_set(pvos->d_var_opts, dest_istage, dest_iel, iopt);
//				var_loc_adds[iopt]++;
			}
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
}