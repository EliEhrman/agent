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
#define true (bool)1
#define false (bool)0
#define min(a,b) (((a)<(b))?(a):(b))
#define max(a,b) (((a)>(b))?(a):(b))

#define D_ELS_SIZE 30

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

typedef struct SIntList {
	int * pl;
	int len;
} tSIntList;


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
void str_list_clear(tSStrList * sl);

void * str_list_create(int len) {
	tSStrList * sl = (tSStrList*)vomalloc(sizeof(tSStrList));
	sl->len = len;
	sl->pl = (char**)vomalloc(len*sizeof(char*));
	memset(sl->pl, 0, len*sizeof(char*));
	return (void*)sl;
}

void str_list_set(void * hl, int ipos, char * val) {
	tSStrList * sl = (tSStrList *)hl;
	sl->pl[ipos] = val;
}

void str_list_delete(void * hl) {
	tSStrList * sl = (tSStrList *)hl;
	str_list_clear(sl);
	vofree(sl);
}

void str_list_init(tSStrList * sl) {
	sl->len = 0;
	sl->pl = NULL;
}

//void str_list_set(tSStrList * sl, char** str_arr, int arr_len) {
//	sl->len = arr_len;
//	sl->pl = (char **)vomalloc(sl->len*sizeof(char*)*sl->len);
//	memcpy(sl->pl, str_arr, arr_len*sizeof(char*));
//}
//
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
//	printf("str_list_print called for %d items.\n", sl->len);
	for (i=0; i<sl->len; i++) {
		printf("%s, ", sl->pl[i]);
	}
	printf("\n");
}

typedef struct SStrListList {
	tSStrList * pl;
	int len;
} tSStrListList;

typedef struct SStrListListList {
	tSStrListList * pl;
	int len;
} tSStrListListList;

void str_l2_init(tSStrListList * psl2) {
	psl2->pl = NULL;
	psl2->len = 0;
}

void str_l2_print(tSStrListList * psl2);

void str_l2_add(tSStrListList * psl2, tSStrList * psl) { // char** str_arr, int arr_len) {
	int old_len = psl2->len;
	tSStrList * old_pl = psl2->pl;
	printf("str_l2_add called. len=%d\n", psl2->len);
	psl2->len++;
	psl2->pl = (tSStrList *)vomalloc(sizeof(tSStrList)*psl2->len);
	if (old_pl != NULL) {
		memcpy(psl2->pl, old_pl, sizeof(tSStrList)*old_len);
		vofree(old_pl);
	}
	psl2->pl[old_len].len = psl->len;
	psl2->pl[old_len].pl = (char**)vomalloc(sizeof(char*)*psl2->pl[old_len].len);
	memcpy(psl2->pl[old_len].pl, psl->pl, sizeof(char*)*psl2->pl[old_len].len);	
//	printf("set len from %d to %d.\n", psl->len, psl2->pl[old_len].len);
//	str_l2_print(psl2);
}

void str_l2_print(tSStrListList * psl2) {
	int i;
//	printf("str_l2_print called for %d items.\n", psl2->len);
	for (i=0;i<psl2->len;i++) {
		printf("%d: ",i);
		str_list_print(&(psl2->pl[i]));
	}
}

void str_l2_clear(tSStrListList * psl2) {
	int i;
	for (i=0;i<psl2->len;i++) {
		str_list_clear(&(psl2->pl[i]));
	}
	vofree(psl2->pl);
}
//
//void str_l3_init(tSStrListListList * psl3) {
//	psl3->pl = NULL;
//	psl3->len = 0;
//}
//
//void str_l3_add_null(tSStrListListList * psl3) {
//	int old_len = psl3->len;
//	tSStrListList * old_pl = psl3->pl;
//	psl3->len++;
//	psl3->pl = (tSStrListList *)vomalloc(sizeof(tSStrListList*))
//}




// hurts not to have templates but I'm not going to start with macros here
void int_list_init(tSIntList * sl) {
	sl->len = 0;
	sl->pl = NULL;
}


void int_list_clear(tSIntList * sl) {
	if (sl == NULL) {
		return;
	}
	if (sl->pl != NULL) {
		vofree(sl->pl);
	}
	
	sl->pl = NULL;
	sl->len = 0;
//	vofree(sl);
}

void int_list_add_val(tSIntList * sl, int val) {
	int old_len = sl->len;
	int * old_pl = sl->pl;
	sl->len++;
	sl->pl = (int *)vomalloc(sl->len*sizeof(int));
	if (old_len > 0) {
		memcpy(sl->pl, old_pl, old_len*sizeof(int));
		vofree(old_pl);
	}
	sl->pl[old_len] = val;
}


void int_list_print(tSIntList * sl) {
	int i;
	printf("int list: ");
	for (i=0; i<sl->len; i++) {
		printf("%d, ", sl->pl[i]);
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

void phrase_match_print(tSMatchPhrase * ppm) {
	printf("stage: %d, b_matched: %s, phrase: \n", ppm->istage, (ppm->b_matched ? "True" : "False"));
	phrase_print(&(ppm->phrase));
	
}

void match_phrase_set(tSMatchPhrase * ppm, int istage, bool b_matched, tSPhrase * phrase) {
	int iel;
	ppm->istage = istage;
	ppm->b_matched = b_matched;
	ppm->phrase.len = phrase->len;
	ppm->phrase.pl = (tSPhraseEl *)vomalloc(ppm->phrase.len * sizeof(tSPhraseEl));
	for (iel=0;iel<ppm->phrase.len;iel++) {
		ppm->phrase.pl[iel].el_type = phrase->pl[iel].el_type;
		ppm->phrase.pl[iel].val = phrase->pl[iel].val;
		ppm->phrase.pl[iel].cd = phrase->pl[iel].cd;
	}
	
}

typedef struct SVOApp {
	int bitvec_size;
	char** el_bin_db; // bitvecs, storage for each bitvec is local
	size_t el_bin_db_len;
	struct hsearch_data * d_words;
	char ** l_els;
	char ** mpdb_bins;
	int mpdb_num_recs;
	int mpdb_rec_len;
	int num_ilens; // lenth of following array and all ilen-indexed arrays
	tSStrListList * ll_phrases;
} tSVOApp;

void * init_capp(void) {
	tSVOApp * papp = (tSVOApp *)vomalloc(sizeof(tSVOApp));
	papp->el_bin_db_len = 0;
	papp->el_bin_db = NULL;
	papp->d_words = NULL;
	papp->l_els = NULL;
	papp->mpdb_bins = NULL;
	papp->mpdb_num_recs = 0;
	papp->mpdb_rec_len = 0;
	papp->num_ilens = 0;
	papp->ll_phrases = NULL;
	return (void *)papp;
}

void set_el_bitvec_size(void * happ, int size) {
	tSVOApp * papp = (tSVOApp *)happ;
	papp->bitvec_size = size;
}

void app_mpdb_bin_init(void * happ, int num_recs, int rec_len) {
	tSVOApp * papp = (tSVOApp *)happ;
	int irec;
	papp->mpdb_num_recs = num_recs;
	papp->mpdb_rec_len = rec_len;
	papp->mpdb_bins = (char **)vomalloc(sizeof(char*)*papp->mpdb_num_recs);
	for (irec=0;irec<papp->mpdb_num_recs;irec++) {
		papp->mpdb_bins[irec] = (char*)vomalloc(sizeof(char)*papp->mpdb_rec_len);
	}
}

void app_mpdb_bin_free(void * happ) {
	tSVOApp * papp = (tSVOApp *)happ;
	int irec;
	for (irec=0;irec<papp->mpdb_num_recs;irec++) {
		vofree(papp->mpdb_bins[irec]);
	}
	vofree(papp->mpdb_bins);
	papp->mpdb_num_recs = 0;
	papp->mpdb_rec_len = 0;
	papp->mpdb_bins = NULL;
}

void app_mpdb_bin_rec_set(void * happ, int irec, char* rec) {
	tSVOApp * papp = (tSVOApp *)happ;
	memcpy(papp->mpdb_bins[irec], rec, sizeof(char)*papp->mpdb_rec_len);
}

void app_mpdb_bin_rec_add(void * happ, char* rec) {
	tSVOApp * papp = (tSVOApp *)happ;
	int old_num_recs = papp->mpdb_num_recs;
	char ** old_bins = papp->mpdb_bins;
	
	papp->mpdb_num_recs++;
	papp->mpdb_bins = (char **)vomalloc(sizeof(char*)*papp->mpdb_num_recs);
	if (old_num_recs>0) {
		memcpy(papp->mpdb_bins, old_bins, sizeof(char*)*old_num_recs);
		vofree(old_bins);
	}
	papp->mpdb_bins[old_num_recs] = (char*)vomalloc(sizeof(char)*papp->mpdb_rec_len);
	memcpy(papp->mpdb_bins[old_num_recs], rec, sizeof(char)*papp->mpdb_rec_len);	
	printf("app_mpdb_bin_rec_add. Array now %d x %d\n", papp->mpdb_num_recs, papp->mpdb_rec_len);
}

void app_mpdb_bin_rec_del(void * happ, int irec) {
	tSVOApp * papp = (tSVOApp *)happ;
	int rem_len = papp->mpdb_num_recs - irec - 1;
	if (irec >= papp->mpdb_num_recs) {
		printf("app_mpdb_bin_rec_del: Coding error. irec (%d) >= papp->mpdb_num_recs (%d)\n", 
				irec, papp->mpdb_num_recs);
	}
	vofree(papp->mpdb_bins[irec]);
	if (rem_len > 0) {
		memcpy(&(papp->mpdb_bins[irec]), &(papp->mpdb_bins[irec+1]), rem_len*sizeof(char*));
	}
	papp->mpdb_num_recs--;
}

void app_mpdb_bin_print(void * happ) {
	tSVOApp * papp = (tSVOApp *)happ;
	int irec, ibit;
	printf("Full print of mpdb_bins\n");
	for (irec=0;irec<papp->mpdb_num_recs;irec++) {
		printf("%d: ", irec);
		for (ibit=0;ibit<papp->mpdb_rec_len;ibit++) {
			printf("%hhd", papp->mpdb_bins[irec][ibit]);
		}
		printf("\n");
	}
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
		printf("Error! Failed to add word %s to d_words dict\n", e.key);
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
//	printf("get_el_bin for %s. iel = %zu\n", ep->key, iel);
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

void ll_phrases_add_val(void * happ, int ilen, void * hsl) { // char** str_arr, int arr_len) {
	tSVOApp * papp = (tSVOApp *)happ;
	tSStrList * psl = (tSStrList *)hsl;
	printf("ll_phrases_add_val called for ilen %d. Num ilens is %d\n", ilen, papp->num_ilens);
//	str_l2_print(&(papp->ll_phrases[ilen]));
	str_l2_add(&(papp->ll_phrases[ilen]), psl); // str_arr, arr_len);
}

void ll_phrases_add_ilen(void * happ) {
	tSVOApp * papp = (tSVOApp *)happ;
	int old_len = papp->num_ilens;
	tSStrListList * old_pl = papp->ll_phrases;
	papp->num_ilens++;
	papp->ll_phrases = (tSStrListList *)vomalloc(papp->num_ilens*sizeof(tSStrListList));
	if (old_len > 0) {
		memcpy(papp->ll_phrases, old_pl, old_len*sizeof(tSStrListList));
		vofree(old_pl);
	}
	str_l2_init(&(papp->ll_phrases[old_len]));
	printf("ll_phrases_add_ilen done. Num ilens is %d\n", papp->num_ilens);
	
}

void ll_phrases_print(void * happ) {
	tSVOApp * papp = (tSVOApp *)happ;
	int ilen;
	printf("ll_phrases: \n");
	for (ilen=0;ilen<papp->num_ilens;ilen++) {
		printf("ilen %d:\n", ilen);
		str_l2_print(&(papp->ll_phrases[ilen]));
	}
}

void free_capp(void * hcapp) {
	tSVOApp * papp = (tSVOApp *)hcapp;
	if (papp->ll_phrases != NULL) {
		int iilen;
		for (iilen=0;iilen<papp->num_ilens;iilen++) {
			str_l2_clear(&(papp->ll_phrases[iilen]));
		}
		vofree(papp->ll_phrases);
	}
	app_mpdb_bin_free(papp);
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

typedef struct SMPDB {
	tSVOApp * papp;
	struct hsearch_data  d_dn_names;
	tSIntPairList l_srphrases;
	char ** l_idb_mrks;
	int num_dbs;
} tSMPDB;

void * mpdb_init(void * happ, int num_idbs) {
	tSVOApp * papp = (tSVOApp *)happ;
	tSMPDB * pmpdb = (tSMPDB *)vomalloc(sizeof(tSMPDB));
	pmpdb->papp = papp;
	pmpdb->l_srphrases.len = 0;
	pmpdb->l_srphrases.pl = NULL;
	memset(&(pmpdb->d_dn_names), 0, sizeof(struct hsearch_data));
	hcreate_r(num_idbs * 2, &(pmpdb->d_dn_names));
	
	pmpdb->l_idb_mrks = NULL;
	pmpdb->num_dbs = 0;
	
	return (void *)pmpdb;
}

void mpdb_add_db(void * hmpdb, char * dbname, int idb) {
	tSMPDB * pmpdb = (tSMPDB *)hmpdb;
	unsigned hret = 0;
	ENTRY e, *ep;
	int old_num_dbs = pmpdb->num_dbs;
	char ** old_l_idb_mrks = pmpdb->l_idb_mrks;
	int num_srphrases = pmpdb->l_srphrases.len;

	e.key = dbname;
	e.data = (void *)(size_t)idb;
	hret = hsearch_r(e, ENTER, &ep, &(pmpdb->d_dn_names));
	if (hret == 0) {
		printf("Error! Failed to add word %s to d_dn_names dict\n", e.key);
	}
//	else {
//		printf("Succeeded in adding %s to d_dn_names.\n", e.key);		
//	}
	
	pmpdb->num_dbs++;
	pmpdb->l_idb_mrks = (char **)vomalloc(pmpdb->num_dbs * sizeof(char *));
	if (old_num_dbs > 0) {
		memcpy(pmpdb->l_idb_mrks, old_l_idb_mrks, old_num_dbs*sizeof(char*));
		vofree(old_l_idb_mrks);
	}
	pmpdb->l_idb_mrks[old_num_dbs] = (char *)vomalloc(num_srphrases*sizeof(char));
	memset(pmpdb->l_idb_mrks[old_num_dbs], 0, num_srphrases*sizeof(char));
}

int mpdb_get_idb(void * hmpdb, char * dbname) {
	tSMPDB * pmpdb = (tSMPDB *)hmpdb;
	unsigned hret = 0;
	ENTRY e, *ep;
	int idb;

	e.key = dbname;
	hret = hsearch_r(e, FIND, &ep,  &(pmpdb->d_dn_names));
	if (hret == 0) {
		idb = -1;
	}
	else {
		idb = (int)(size_t)ep->data;
	}
	return idb;
}

void mpdb_add_srphrase(void * hmpdb, int ilen, int iphrase) {
	tSMPDB * pmpdb = (tSMPDB *)hmpdb;
	int old_len = pmpdb->l_srphrases.len;
	intpair * old_pl = pmpdb->l_srphrases.pl;
	int idb;
	
	pmpdb->l_srphrases.len++;
	pmpdb->l_srphrases.pl = (intpair*)vomalloc(pmpdb->l_srphrases.len*sizeof(intpair));
	if (old_len>0) {
		memcpy(pmpdb->l_srphrases.pl, old_pl, old_len*sizeof(intpair));
		vofree(old_pl);
	}
	pmpdb->l_srphrases.pl[old_len][0] = ilen;
	pmpdb->l_srphrases.pl[old_len][1] = iphrase;
	
	for (idb=0;idb<pmpdb->num_dbs;idb++) {
		char * old_vec = pmpdb->l_idb_mrks[idb];
		pmpdb->l_idb_mrks[idb] = (char *)vomalloc(pmpdb->l_srphrases.len*sizeof(char));
		memcpy(pmpdb->l_idb_mrks[idb], old_vec, old_len*sizeof(char));
		vofree(old_vec);
		pmpdb->l_idb_mrks[idb][old_len] = (char)0;
	}
	
	{
		int idb, isrphrase;
		printf("mpdb l_srphrases: [");
		for (isrphrase=0; isrphrase<pmpdb->l_srphrases.len; isrphrase++) {
			printf("(%d:%d), ", pmpdb->l_srphrases.pl[isrphrase][0], pmpdb->l_srphrases.pl[isrphrase][1]);
		}
		printf("]\n");
		for (idb=0;idb<pmpdb->num_dbs;idb++) {
			printf("idb: %d. [", idb);
			for (isrphrase=0; isrphrase<pmpdb->l_srphrases.len; isrphrase++) {
				printf("%hhd", pmpdb->l_idb_mrks[idb][isrphrase]);
			}
			printf("]\n");
		}
	}
	
}

void mpdb_set_idb_mrk(void * hmpdb, int idb, int isrphrase, char val) {
	tSMPDB * pmpdb = (tSMPDB *)hmpdb;
	pmpdb->l_idb_mrks[idb][isrphrase] = val;
}

//void mpdb_get_l_idb_mrk(tSMPDB * pmpdb, int idb) {
//	return pmdb->l_idb_mr
//}
//
void mpdb_del_srphrase(void * hmpdb, int isrphrase) {
	tSMPDB * pmpdb = (tSMPDB *)hmpdb;
	int rem_len = pmpdb->l_srphrases.len - isrphrase - 1;
	if (isrphrase >= pmpdb->l_srphrases.len) {
		printf("mpdb_del_srphrase: Coding error. isrphrase (%d) >= pmpdb->l_srphrases.len (%d)\n", 
				isrphrase, pmpdb->l_srphrases.len);
	}
	if (rem_len > 0) {
		int idb;
		memcpy(&(pmpdb->l_srphrases.pl[isrphrase]), &(pmpdb->l_srphrases.pl[isrphrase+1]), rem_len*sizeof(intpair));
		for (idb=0;idb<pmpdb->num_dbs;idb++) {
			memcpy(&(pmpdb->l_idb_mrks[idb][isrphrase]), &(pmpdb->l_idb_mrks[idb][isrphrase]), rem_len*sizeof(char));
		}
	}
	pmpdb->l_srphrases.len--;
}

void mpdb_clear(void * hmpdb) {
	tSMPDB * pmpdb = (tSMPDB *)hmpdb;
	
	if (pmpdb->l_idb_mrks != NULL) {
		int idb;
		for (idb=0;idb<pmpdb->num_dbs;idb++) {
			vofree(pmpdb->l_idb_mrks[idb]);
		}
		vofree(pmpdb->l_idb_mrks);
	}
	if (pmpdb->l_srphrases.pl != NULL) {
		vofree(pmpdb->l_srphrases.pl);
	}
	hdestroy_r(&(pmpdb->d_dn_names));
	vofree(pmpdb);
	printf("Memory report: %d allocs and %d frees, %d unfreed\n", num_mallocs, num_frees, num_mallocs - num_frees);
}



typedef struct SVOGG {
	tSVOApp * pApp; // not owned
	int num_el_reps;
	char ** l_els_reps; // array locally owned of char * ptrs that themselves point to parts of a sing;e block allocced for this
	int * l_hd_max; // locally owned. Array of small integers, one for each el
	int l_wlist_vars_len;
	intquad * l_wlist_vars;
	int * l_phrases_len;
	int * l_phrases_ilen;
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
	pgg->l_phrases_ilen = NULL; // ilen differs from len in that it is an index into various app tables using len
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
	if (pgg->l_phrases_ilen != NULL) {
		vofree(pgg->l_phrases_ilen);
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

void set_l_phrases_len(void * hgg, int * l_phrases_len, int * l_phrases_ilen, int len) {
	tSVOGG * pgg = (tSVOGG *)hgg;

	pgg->l_phrases_len_len = len;
	pgg->l_phrases_len = (int *)vomalloc(len*sizeof(int));
	pgg->l_phrases_ilen = (int *)vomalloc(len*sizeof(int));
	memcpy(pgg->l_phrases_len, l_phrases_len, len*sizeof(int));
	memcpy(pgg->l_phrases_ilen, l_phrases_ilen, len*sizeof(int));
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
	tSMPDB * pmpdb;
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
	char * db_name; // not stored locally; like all strings
	int mpdb_story_rphrase_size; // length of the following mrk arrays
	char * l_ilen_mrk; // list of bools (char size) size of the srphrases of mpdb, true if the len of current stage matches the len of the ilen of the srphrase
	char * m_match; // local match vector holding matches so far from mpdb story bin recs
	char * m_mrks; // local match vector
	tSPhrase l_phrase_found;
	int stage_phrase_len; // length of next few arrays. A purely local value inside the stage loop
	bool * l_b_unbound;
	int * l_i_unbound;
	int stage_vars_len;
	tSIntList * l_stage_vars;
	int i_null_phrases_len;
	int * l_i_null_phrases;
	int match_phrases_len;
	tSMatchPhrase * l_match_phrases;
	int match_bindings_len;
	tSIntList * l_match_bindings;
	tSPhrase l_story_phrase_found;
	int num_test_phrases;
	tSPhrase * l_test_phrases; // not just a pointer, a list.
	int * l_test_stages;
	struct hsearch_data  d_els;
	int test_locs_len;
	tSIntPairList * ll_test_locs;
	int iopts_len;
	int * l_iopts;
} tSVOState;

//tSNtVars * pnv = NULL;
//int num_vars = 0;
//int curr_var_num = 0;

void * init_vo(void * hgg, void * hmpdb, char * db_name) {
	tSVOState * pvos = (tSVOState *)vomalloc(sizeof(tSVOState));
	pvos->pgg = (tSVOGG *)hgg;
	pvos->pmpdb = (tSMPDB*)hmpdb;
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
	pvos->db_name = db_name;
	pvos->mpdb_story_rphrase_size = 0;
	pvos->l_ilen_mrk = NULL;
	pvos->m_match = NULL;
	pvos->m_mrks = NULL;
	pvos->l_phrase_found.len = 0;
	pvos->l_phrase_found.pl = NULL;
	pvos->stage_phrase_len = 0;
	pvos->l_b_unbound = NULL;
	pvos->l_i_unbound = NULL;
	pvos->stage_vars_len = 0;
	pvos->l_stage_vars = NULL;
	pvos->i_null_phrases_len = 0;
	pvos->l_i_null_phrases = NULL;
	pvos->match_phrases_len = 0;
	pvos->l_match_phrases = NULL;
	pvos->match_bindings_len = 0;
	pvos->l_match_bindings = NULL;
	pvos->l_story_phrase_found.len = 0;
	pvos->l_story_phrase_found.pl = NULL;
	pvos->num_test_phrases = 0;
	pvos->l_test_phrases = NULL; // only holding pointer to other memory allocs
	pvos->l_test_stages = NULL; // one stage num for each pointer above. Needs freeing of memory
	pvos->test_locs_len = 0;
	pvos->ll_test_locs = NULL;
	pvos->iopts_len = 0;
	pvos->l_iopts = NULL;
	return (void *)pvos;
}

void free_vo(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;

	if (pvos->l_iopts != NULL) {
		vofree(pvos->l_iopts);
	}
	if (pvos->ll_test_locs != NULL) {
		printf("Error! ll_test_locs must be freed in the test_for_unexpected double function itself.\n");
	
	}
	if (pvos->l_test_stages != NULL) {
		vofree(pvos->l_test_stages);
	}
	// no free of pvos->l_test_phrases. Holder comment.
	if (pvos->l_story_phrase_found.pl != NULL) {
		vofree(pvos->l_story_phrase_found.pl);
	}
	if (pvos->l_match_bindings != NULL) {
		int i;
		for(i=0;i<pvos->match_bindings_len;i++) {
			vofree(pvos->l_match_bindings[i].pl);
		}
		vofree(pvos->l_match_bindings);
	}
	if (pvos->l_match_phrases != NULL) {
		int iphrase;
		for (iphrase=0;iphrase<pvos->match_phrases_len;iphrase++) {
			vofree(pvos->l_match_phrases[iphrase].phrase.pl);
		}
		vofree(pvos->l_match_phrases);
	}
	if (pvos->l_i_null_phrases != NULL) {
		vofree(pvos->l_i_null_phrases);
	}
	if (pvos->l_stage_vars != NULL) {
		int istage = 0;
		for (istage=0;istage<pvos->stage_vars_len;istage++) {
			int_list_clear(&(pvos->l_stage_vars[istage]));
		}
		vofree(pvos->l_stage_vars);
	}
	if (pvos->l_b_unbound != NULL) {
		vofree(pvos->l_b_unbound);
	}
	if (pvos->l_i_unbound != NULL) {
		vofree(pvos->l_i_unbound);
	}
	if (pvos->l_phrase_found.pl != NULL) {
		vofree(pvos->l_phrase_found.pl);
	}
	if (pvos->m_mrks != NULL) {
		vofree(pvos->m_mrks);
	}
	if (pvos->m_match != NULL) {
		vofree(pvos->m_match);
	}
	if (pvos->l_ilen_mrk != NULL) {
		vofree(pvos->l_ilen_mrk);
	}
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
//	printf("a bitvec: ");
//	for (i=0, pa = a; i<size;i++,pa++) {
//		printf("%hhd", *pa);
//	}
//	printf("\n");
//	printf("b bitvec: ");
//	for (i=0, pb = b; i<size;i++,pb++) {
//		printf("%hhd", *pb);
//	}
//	printf("\n");
//	printf("bin_diff_count: ");
	for (i=0, pa = a, pb = b; i<size;i++,pa++,pb++) {
		if (*pa != *pb ) {
			num_diffs++;
		}
	}
//	printf("num diffs = %d\n", num_diffs);
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

void convert_wlist_to_phrase(tSPhrase * pphrase, tSStrList * psl) {
	int iel;
	pphrase->len = psl->len;
	pphrase->pl = (tSPhraseEl *)vomalloc(sizeof(tSPhraseEl)*pphrase->len);
	for (iel=0;iel<pphrase->len;iel++) {
		phrase_el_init(&(pphrase->pl[iel]), etRecDefObj, psl->pl[iel], -1.0 );
	}
	

}

void bin_logical_and(char * dest, char * src1, char * src2, int len) {
	int i;
	char *pd, *p1, *p2;
	for (i=0, pd=dest, p1=src1, p2=src2;i<len;i++, pd++, p1++, p2++) {
		*pd = ((*p1 && *p2) ? (char)1 : (char)0);
	}
}

bool test_for_unexpected_double(tSVOState * pvos) {
	int iistage;
	unsigned hret = 0;
	ENTRY e, *ep;
	bool b_bad_match_found = false;
	memset(&(pvos->d_els), 0, sizeof(struct hsearch_data));
	hcreate_r(D_ELS_SIZE, &(pvos->d_els));
	for (iistage=0;iistage<pvos->num_test_phrases;iistage++) {
		int istage = pvos->l_test_stages[iistage];
		int iel;
		tSPhrase * test_phrase = &(pvos->l_test_phrases[iistage]);
		for (iel=0;iel<test_phrase->len;iel++) {
			tSPhraseEl * full_el = &(test_phrase->pl[iel]);
			if (full_el->el_type != etRecDefObj) {
				continue;
			}
			
			e.key = full_el->val;
			hret = hsearch_r(e, FIND, &ep,  &(pvos->d_els));
			if (hret == 0) {
				size_t old_len = pvos->test_locs_len;
				tSIntPairList * old_list = pvos->ll_test_locs;
				pvos->test_locs_len++;
				pvos->ll_test_locs = (tSIntPairList *)vomalloc(sizeof(tSIntPairList)*pvos->test_locs_len);
				if (old_len>0) {
					memcpy(pvos->ll_test_locs, old_list, old_len*sizeof(tSIntPairList));
					vofree(old_list);
				}
				tSIntPairList * pnew = &(pvos->ll_test_locs[old_len]);
				pnew->len = 1;
				pnew->pl = (intpair*)vomalloc(sizeof(intpair));
				pnew->pl[0][0] = istage;
				pnew->pl[0][1] = iel;
				e.data = (void *)old_len;
				hret = hsearch_r(e, ENTER, &ep,  &(pvos->d_els));
				if (hret == 0) {
					printf("Error! Failed to add word %s to d_els dict. Consider increasing the size of D_ELS_SIZE\n", e.key);
				}
			}
			else {
				size_t ipos = (size_t)ep->data;
				tSIntPairList * l_pos = &(pvos->ll_test_locs[ipos]);
				int ii;
				for (ii=0;ii<l_pos->len;ii++) {
					intpair * ppos = &(l_pos->pl[ii]);
					int ivar = pair_dict_get(pvos->d_var_opts, (*ppos)[0], (*ppos)[1]);
					if (ivar == -1) {
						b_bad_match_found = true;
						break; // out of ii loop
					}
					tSIntPairList * var_all_locs = &(pvos->l_var_all_locs[ivar]);
					bool b_found = false;
					int iloc;
					for (iloc=0;iloc<var_all_locs->len;iloc++) {
						intpair * ploc = &(var_all_locs->pl[iloc]);
						if ((*ploc)[0] == istage && (*ploc)[1] == iel) {
							b_found = true;
							break; // out of iloc loop
						}
					}
					if (b_found) {
						b_bad_match_found = true;
						break;  // out of ii loop
					}
					
				} // end loop over locs that match the var
				if (b_bad_match_found) {
					break; // out of iel loop
				}
				
//				tSIntPairList * l_pos = &(pvos->ll_test_locs[ipos]);
				{
					intpair * old_pl = l_pos->pl;
					int old_len = l_pos->len;
					l_pos->len++;
					l_pos->pl = (intpair*)vomalloc(sizeof(intpair)*l_pos->len);
					memcpy(l_pos->pl, old_pl, sizeof(intpair)*old_len);
					l_pos->pl[old_len][0] = istage;
					l_pos->pl[old_len][1] = iel;
				}
				
			} // end else on test for not find var in d_els
			
		} // loop over iels in test_phrase 
		if (b_bad_match_found) {
			break; // out of iistage loop
		}

	} // loop over test phrases
	for (int i=0;i<pvos->test_locs_len;i++) {
		tSIntPairList * l_pos = &(pvos->ll_test_locs[i]);
		if (l_pos->len > 0) {
			vofree(l_pos->pl);
		}
	}
	vofree(pvos->ll_test_locs);
	pvos->test_locs_len = 0;
	pvos->ll_test_locs = NULL;
	hdestroy_r(&(pvos->d_els));
	return b_bad_match_found;
}

void match_phrase_append(tSVOState * pvos, int istage, bool b_matched, tSPhrase * pphrase) {
	tSMatchPhrase * old_l_match_phrases = pvos->l_match_phrases;
	int old_match_phrases_len = pvos->match_phrases_len;
	pvos->match_phrases_len++;
	pvos->l_match_phrases = (tSMatchPhrase *)vomalloc(sizeof(tSMatchPhrase)*pvos->match_phrases_len);
	if (old_l_match_phrases != NULL) {
		memcpy(pvos->l_match_phrases, old_l_match_phrases, sizeof(tSMatchPhrase)*old_match_phrases_len);
		vofree(old_l_match_phrases);
	}
	match_phrase_set(	&(pvos->l_match_phrases[old_match_phrases_len]), 
						istage, b_matched, pphrase);
}

void match_bindings_append_for_stage(tSVOState * pvos, int istage) {
	tSIntList * old_l_match_bindings = pvos->l_match_bindings;
	int old_match_bindings_len = pvos->match_bindings_len;
	int ibind;
	pvos->match_bindings_len++;
	pvos->l_match_bindings = (tSIntList*)vomalloc(sizeof(tSIntList)*pvos->match_bindings_len);
	if (old_l_match_bindings != NULL) {
		memcpy(pvos->l_match_bindings, old_l_match_bindings, sizeof(tSIntList)*old_match_bindings_len);
		vofree(old_l_match_bindings);
	}
	tSIntList * new_match_binding = &(pvos->l_match_bindings[old_match_bindings_len]);
	new_match_binding->len = 1+pvos->l_stage_vars[istage].len;
	new_match_binding->pl = (int*)vomalloc(sizeof(int)*new_match_binding->len);
	new_match_binding->pl[0] = istage;
	for (ibind=1;ibind<new_match_binding->len;ibind++) {
		new_match_binding->pl[ibind] = 0;
	}
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
			int ivar;
			for (ivar=0; ivar < pvos->pgg->l_wlist_vars_len; ivar++) {
				int * wlist_var = pvos->pgg->l_wlist_vars[ivar];
				int src_istage = wlist_var[0];
				int src_iel = wlist_var[1];
				int dest_istage = wlist_var[2];
				int dest_iel = wlist_var[3];
				memcpy(	pvos->ll_src_pat[dest_istage][dest_iel], pvos->ll_src_pat[src_istage][src_iel], 
						papp->bitvec_size*sizeof(char));
				pvos->ll_hd_max[dest_istage][dest_iel] = pvos->ll_hd_max[src_istage][src_iel];
			}
		}
		{
			// This block aims to finish the job of building the var table by looking for any element not in the
			// var table already that has non-exact value
			int istage;
			for (istage=0;istage<pvos->pgg->l_phrases_len_len;istage++) {
				int phrase_len = pvos->pgg->l_phrases_len[istage];
				int iel;
				for (iel=0; iel<phrase_len;iel++) {
					int ivar = pair_dict_get(pvos->d_var_opts, istage, iel);
					int old_num_vars = pvos->num_vars;
					if (ivar != -1 || pvos->ll_hd_max[istage][iel] == 0)
						continue;
					pvos->num_vars++;
					pair_dict_set(pvos->d_var_opts, istage, iel, old_num_vars);
					int nd_el_match_idx = bin_idx_best_match(	papp->el_bin_db, pvos->ll_src_pat[istage][iel],
																papp->el_bin_db_len, papp->bitvec_size);
					char *el_word = get_word_by_id(papp, nd_el_match_idx);
					{
						tSNtVars * old_pnv = pvos->pnv;
						tSNtVars nv;
						pvos->pnv = (tSNtVars *)vomalloc(sizeof(tSNtVars) * pvos->num_vars);
						memcpy(pvos->pnv, old_pnv, sizeof(tSNtVars) * old_num_vars);
						vofree(old_pnv);
						nv.loc = pvos->l_phrase_starts[istage]+iel, nv.b_bound = false, nv.b_must_bind = false;
						nv.val = el_word, nv.b_resolved = 0, nv.iext_var = -1;
						nv.cd = 1. - ((double)(pvos->ll_hd_max[istage][iel]) / papp->bitvec_size) ; 
						pvos->pnv[old_num_vars] = nv;
					}
					{
						tSStrList * old_l_var_vals = pvos->l_var_vals;				
						pvos->l_var_vals = (tSStrList*)vomalloc(pvos->num_vars*sizeof(tSStrList));
						memcpy(pvos->l_var_vals, old_l_var_vals, sizeof(tSStrList) * old_num_vars);
						vofree(old_l_var_vals);
						str_list_init(&(pvos->l_var_vals[old_num_vars]));
						str_list_add_val(&(pvos->l_var_vals[old_num_vars]), NULL);
					}
					{
						tSIntPairList * old_var_locs = pvos->l_var_all_locs;
						pvos->l_var_all_locs = (tSIntPairList *)vomalloc(pvos->num_vars*sizeof(tSIntPairList));
						memcpy(pvos->l_var_all_locs, old_var_locs, sizeof(tSIntPairList)*old_num_vars);
						pvos->l_var_all_locs[old_num_vars].len = 1;
						pvos->l_var_all_locs[old_num_vars].pl = (intpair*)vomalloc(sizeof(intpair));
						vofree(old_var_locs);
						pvos->l_var_all_locs[old_num_vars].pl[0][0] = istage;
						pvos->l_var_all_locs[old_num_vars].pl[0][1] = iel;
					}
				}
				
			}
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
			{
				int icurr_loc;
				printf("l_var_all_locs: [");
				for (icurr_loc=0; icurr_loc<pvos->num_vars; icurr_loc++) {
					int ipair;
					tSIntPairList * ppl = &(pvos->l_var_all_locs[icurr_loc]);
					printf(" [ ");
					for (ipair=0; ipair<ppl->len; ipair++) {
						printf("(%d, %d), ", ppl->pl[ipair][0] , ppl->pl[ipair][1] );
					}
					printf(" ], ");
				}
				printf("]\n");
				pair_dict_print(pvos->d_var_opts);
			}
		}
    }
	{
		// part b
		int idb = mpdb_get_idb(pvos->pmpdb, pvos->db_name);
		char * nd_default_idb_mrk;
		int istage;
		tSIntPairList * pl_story_rphrases = &(pvos->pmpdb->l_srphrases);
		if (idb < 0) {
			printf("Coding error! no idb for %s\n", pvos->db_name);
		}
		nd_default_idb_mrk = pvos->pmpdb->l_idb_mrks[idb]; //  mpdb_mgr.get_nd_idb_mrk(idb)
		pvos->stage_vars_len = pvos->pgg->l_phrases_len_len;
		pvos->l_stage_vars = (tSIntList*)vomalloc(sizeof(tSIntList)*pvos->stage_vars_len);
		for (istage=0;istage<pvos->pgg->l_phrases_len_len;istage++) {
			int_list_init(&(pvos->l_stage_vars[istage]));
		}
		pvos->mpdb_story_rphrase_size = pl_story_rphrases->len;
		pvos->l_ilen_mrk = (char*)vomalloc(pvos->mpdb_story_rphrase_size*sizeof(char));
		pvos->m_match = (char*)vomalloc(pvos->mpdb_story_rphrase_size*sizeof(char));
		pvos->m_mrks = (char*)vomalloc(pvos->mpdb_story_rphrase_size*sizeof(char));
		for (istage=0;istage<pvos->pgg->l_phrases_len_len;istage++) {
			int phrase_len = pvos->pgg->l_phrases_len[istage];
			int isr, iel;
			char *el_word;
			for (isr=0;isr<pl_story_rphrases->len;isr++) {
				pvos->l_ilen_mrk[isr] = ((pvos->pgg->l_phrases_ilen[istage] == pl_story_rphrases->pl[isr][0]) 
										? (char)1 : (char)0);
//				pvos->m_match[isr] = (char)1;
			}
			bin_logical_and(pvos->m_mrks, nd_default_idb_mrk, pvos->l_ilen_mrk, pvos->mpdb_story_rphrase_size);
			memcpy(pvos->m_match, pvos->m_mrks, pvos->mpdb_story_rphrase_size*sizeof(char));
			pvos->l_phrase_found.len = phrase_len;
			pvos->l_phrase_found.pl = (tSPhraseEl*)vomalloc(sizeof(tSPhraseEl)*pvos->l_phrase_found.len);
			for (iel=0;iel<phrase_len;iel++) {
				phrase_el_init(&(pvos->l_phrase_found.pl[iel]), etRecDefNone, NULL, -1.0);
			}
			if (pvos->l_b_unbound != NULL) {
				vofree(pvos->l_b_unbound);
			}
			if (pvos->l_i_unbound != NULL) {
				vofree(pvos->l_i_unbound);				
			}
			pvos->stage_phrase_len = phrase_len;
			pvos->l_b_unbound = (bool *)vomalloc(sizeof(bool)*pvos->stage_phrase_len);
			pvos->l_i_unbound = (int *)vomalloc(sizeof(int)*pvos->stage_phrase_len);
			for (iel=0;iel<phrase_len;iel++) {
				int iopt = pair_dict_get(pvos->d_var_opts, istage, iel);
				char* src_pat = pvos->ll_src_pat[istage][iel];
				int hd_max = pvos->ll_hd_max[istage][iel];
				int match_start = iel * papp->bitvec_size;
				int match_end = match_start + papp->bitvec_size;
				int irec;
				
				if (iopt == -1 || !pvos->pnv[iopt].b_bound) {
					int nd_el_match_idx = bin_idx_best_match(	papp->el_bin_db, src_pat,
																papp->el_bin_db_len, papp->bitvec_size);
					el_word = get_word_by_id(papp, nd_el_match_idx);
				}
				else {
					el_word = pvos->pnv[iopt].val;
				}
				
				if (hd_max == 0) {
					phrase_el_init(&(pvos->l_phrase_found.pl[iel]), etRecDefObj, el_word, -1.0);
					pvos->l_b_unbound[iel] = false;
					pvos->l_i_unbound[iel] = -1;
					
				}
				else {
					phrase_el_init(	&(pvos->l_phrase_found.pl[iel]), etRecDefLike, el_word, 
									1. - (double)(hd_max) / papp->bitvec_size);					
					pvos->l_b_unbound[iel] = (iopt != -1);
					pvos->l_i_unbound[iel] = iopt;
				}
				
				// Check for the phrase of the rule being longer than the size of the vector in the db
				// Certainly there will noth be any matches in this case
				if (((iel+1)*papp->bitvec_size) > papp->mpdb_rec_len) {
					memset(pvos->m_match, 0, pvos->mpdb_story_rphrase_size*sizeof(char));
					continue; // next iel
				}
				// Build the actual matches
				for (irec=0;irec<papp->mpdb_num_recs;irec++) {
					char * rec = papp->mpdb_bins[irec];
					int ibit, diff_count=0;
					char *pq, *ps, bgood=true; // q for query s for story
					for (ibit=match_start,pq=src_pat,ps=&(rec[match_start]);ibit<match_end;ibit++,pq++,ps++) {
						if (*pq!=*ps) {
							diff_count++;
							if (diff_count > hd_max) {
								bgood = false;
								break;
							}
						}
					}
					pvos->m_match[irec] = (char)((bool)(pvos->m_match[irec]) && bgood);
				}
			} // end loop iel over phrase len
			// following makes little sense, but exists in the original pyhton code
			bin_logical_and(pvos->m_match, pvos->m_match, pvos->m_mrks, papp->mpdb_num_recs);
			// one extra piece. Build a table of var idxs that are used for each el of the stage. At this point
			// even though we are in the middle of the stages loop we can say that we know the var table for this stage
			{
				int ivar;
				for(ivar=0;ivar<pvos->num_vars;ivar++) {
					tSNtVars * var = &(pvos->pnv[ivar]);
					tSIntPairList * var_all_locs = &(pvos->l_var_all_locs[ivar]);
					int iloc;
					if (var->b_bound) {
						continue;
					}
					for (iloc=0;iloc<var_all_locs->len;iloc++) {
						intpair * var_loc = &(var_all_locs->pl[iloc]);
						if ((*var_loc)[0] == istage) {
							int_list_add_val(&(pvos->l_stage_vars[istage]), ivar);
						}
					}
				}
			}
			
			{
				int irec, iistage, iel;
				printf("l_b_unbound: ");
				for (iel=0;iel<pvos->stage_phrase_len;iel++) {
					printf("%s, ", ((pvos->l_b_unbound[iel] == true) ? "True" : "False"));
				}
				printf("\n");
				printf("l_i_unbound: ");
				for (iel=0;iel<pvos->stage_phrase_len;iel++) {
					printf("%d, ", pvos->l_i_unbound[iel]);
				}
				printf("\n");
				printf("l_phrase_found: \n");
				phrase_print(&(pvos->l_phrase_found));
				printf("m_match: ");
				for (irec=0;irec<papp->mpdb_num_recs;irec++) {
					printf("%hhd",pvos->m_match[irec]);
				}
				printf("\n");
				printf("l_stage_vars:\n");
				for (iistage=0; iistage<pvos->stage_vars_len; iistage++) {
					int_list_print(&(pvos->l_stage_vars[iistage]));
				}
			}
			{
				{
					int * old_null_phrases = pvos->l_i_null_phrases;
					int old_i_null_phrases_len = pvos->i_null_phrases_len;
					pvos->i_null_phrases_len++;
					pvos->l_i_null_phrases = (int *)vomalloc(sizeof(int)*pvos->i_null_phrases_len);
					if (old_null_phrases != NULL) {
						memcpy(pvos->l_i_null_phrases, old_null_phrases, sizeof(int)*old_i_null_phrases_len);
						vofree(old_null_phrases);
					}
					pvos->l_i_null_phrases[old_i_null_phrases_len] = pvos->match_phrases_len;
				}
				match_phrase_append(pvos, istage, false, &(pvos->l_phrase_found));

//				{
//					tSMatchPhrase * old_l_match_phrases = pvos->l_match_phrases;
//					int old_match_phrases_len = pvos->match_phrases_len;
//					pvos->match_phrases_len++;
//					pvos->l_match_phrases = (tSMatchPhrase *)vomalloc(sizeof(tSMatchPhrase)*pvos->match_phrases_len);
//					if (old_l_match_phrases != NULL) {
//						memcpy(pvos->l_match_phrases, old_l_match_phrases, sizeof(tSMatchPhrase)*old_match_phrases_len);
//						vofree(old_l_match_phrases);
//					}
//					match_phrase_set(	&(pvos->l_match_phrases[old_match_phrases_len]), 
//										istage, false, &(pvos->l_phrase_found));
//				}
				match_bindings_append_for_stage(pvos, istage);
//				{
//					tSIntList * old_l_match_bindings = pvos->l_match_bindings;
//					int old_match_bindings_len = pvos->match_bindings_len;
//					int ibind;
//					pvos->match_bindings_len++;
//					pvos->l_match_bindings = (tSIntList*)vomalloc(sizeof(tSIntList)*pvos->match_bindings_len);
//					if (old_l_match_bindings != NULL) {
//						memcpy(pvos->l_match_bindings, old_l_match_bindings, sizeof(tSIntList)*old_match_bindings_len);
//						vofree(old_l_match_bindings);
//					}
//					tSIntList * new_match_binding = &(pvos->l_match_bindings[old_match_bindings_len]);
//					new_match_binding->len = 1+pvos->l_stage_vars[istage].len;
//					new_match_binding->pl = (int*)vomalloc(sizeof(int)*new_match_binding->len);
//					new_match_binding->pl[0] = istage;
//					for (ibind=1;ibind<new_match_binding->len;ibind++) {
//						new_match_binding->pl[ibind] = 0;
//					}
//				}
			}
			{
				int imatch;
				for (imatch=0;imatch<pvos->mpdb_story_rphrase_size;imatch++) {
					intpair * story_rphrase;
					tSStrList * p_story_wlist;
					char bmatch = pvos->m_match[imatch];
					if (bmatch==(char)0) {
						continue;
					}
					story_rphrase = &(pvos->pmpdb->l_srphrases.pl[imatch]);
					p_story_wlist = &(papp->ll_phrases[(*story_rphrase)[0]].pl[(*story_rphrase)[1]]);
					convert_wlist_to_phrase(&(pvos->l_story_phrase_found), p_story_wlist);
					printf("l_story_phrase_found for %d: ", imatch);
					phrase_print(&(pvos->l_story_phrase_found));
					pvos->num_test_phrases = 1;
					pvos->l_test_phrases = &(pvos->l_story_phrase_found);
					if (pvos->l_test_stages != NULL) {
						vofree(pvos->l_test_stages);
					}
					pvos->l_test_stages = (int*)vomalloc(sizeof(int));
					bool b_bad_double = test_for_unexpected_double(pvos);
					if (b_bad_double) {
						printf("bad double found on match %d.\n", imatch);
						pvos->m_match[imatch] = (char)0;
						continue;
					}
					match_phrase_append(pvos, istage, true, &(pvos->l_story_phrase_found));
					match_bindings_append_for_stage(pvos, istage);
					for (int iel=0;iel<phrase_len;iel++ ) {
						if (pvos->l_b_unbound[iel]) {
							int ivar = pvos->l_i_unbound[iel];
							tSStrList * l_bindings = &(pvos->l_var_vals[ivar]);
							char * var_binding = p_story_wlist->pl[iel];
							bool b_in_list=false;
							int ivar_val = -1;
							for (int ibind = 0; ibind < l_bindings->len; ibind++) {
								if (l_bindings->pl[ibind] != NULL && strcmp(l_bindings->pl[ibind], var_binding) == 0) {
									b_in_list = true;
									ivar_val = ibind;
									break;
								}
							}
							if (!b_in_list) {
								ivar_val = l_bindings->len;
								str_list_add_val(l_bindings, var_binding);
							}
							tSIntList * stage_ivars = &(pvos->l_stage_vars[istage]);
							b_in_list = false;
							int match_idx = -1;
							for (int iivar=0; iivar<stage_ivars->len;iivar++) {
								if (stage_ivars->pl[iivar] == ivar) {
									b_in_list = true;
									match_idx = iivar;
									break;
								}
							}
							if (!b_in_list) {
								printf("Error! Strange. Python code does not recognise the option of not finding ivar in list.\n");
							}
							pvos->l_match_bindings[pvos->match_bindings_len-1].pl[1+match_idx] = ivar_val;
						}
					}
				}
			}
			
		} // end loop over stages of phrases of parent rule
	}
	{
		printf("%d match phrases:\n", pvos->match_phrases_len );
		for (int i=0; i<pvos->match_phrases_len;i++) {
			phrase_match_print(&(pvos->l_match_phrases[i]));
		}
		printf("%d match bindings:\n", pvos->match_bindings_len );
		for (int i=0; i<pvos->match_bindings_len; i++) {
			int_list_print(&(pvos->l_match_bindings[i]));
		}
		printf("l_var_vals: \n");
		for (int iopt=0; iopt<pvos->num_vars; iopt++) {
			tSStrList * sl = &(pvos->l_var_vals[iopt]);
			printf("%d: ", iopt);
			str_list_print(sl);
		}
	}
	{
		for (int iphrase=0;iphrase<pvos->i_null_phrases_len;iphrase++) {
			int i_null_phrase = pvos->l_i_null_phrases[iphrase];
			tSMatchPhrase * null_match_phrase = &(pvos->l_match_phrases[i_null_phrase]);
			int istage = null_match_phrase->istage;
			for (int iel=0;iel<pvos->pgg->l_phrases_len[istage];iel++) {
				int iopt = pair_dict_get(pvos->d_var_opts, istage, iel);
				if (iopt == -1 || pvos->pnv[iopt].b_bound) {
					continue;
				}
			}

		}
	}
	return 1;
	
}