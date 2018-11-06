/* File: varopts.c */
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

void handler(int sig) {
	void *array[10];
	size_t size;

	// get void*'s for all entries on the stack
	size = backtrace(array, 10);

	// print out all the frames to stderr
	printf("Error: signal %d:\n", sig);
	backtrace_symbols_fd(array, size, STDOUT_FILENO);
	printf("Caught but died.\n");
	exit(1);
}
void perm_free(int** l_out);

#define MALLOC_HASH_MAX 100000
#define MAX_ADDR_STR 32
struct hsearch_data  d_mallocs;
int imalloc = 0;
bool b_malloc_init = false;
//int malloc_hash_max = 100000;
bool malloc_arr[MALLOC_HASH_MAX];
char addr_str_arr[MALLOC_HASH_MAX][MAX_ADDR_STR];
char * pbad = 0;
int vo_call_num = -1;

void vo_malloc_init(void) {
	imalloc = 0;
	memset(&(d_mallocs), 0, sizeof(struct hsearch_data));
	hcreate_r(MALLOC_HASH_MAX, &d_mallocs);
	memset(malloc_arr, 0, MALLOC_HASH_MAX*sizeof(bool));
}

void vo_malloc_reset(void) {
	hdestroy_r(&d_mallocs);
	b_malloc_init = false;
}

void vo_malloc_test(void) {
	for (int i=0; i<imalloc; i++) {
		if (malloc_arr[i]) {
			printf("malloc at # %d not freed, vo_call_num %d.\n", i, vo_call_num);
		}
	}
}
void* vomalloc (size_t size) {
	if (!b_malloc_init) {
		vo_malloc_init();
		b_malloc_init = true;
	}
	num_mallocs++;
	if (imalloc == 83 && vo_call_num == 11) {
		printf("imalloc # %d hit for vo_call_num %d.\n", imalloc, vo_call_num);
//		raise(SIGSEGV);
	}
	void * p = malloc(size);
	malloc_arr[imalloc] = true;
//	char sbuf[32];
	snprintf(addr_str_arr[imalloc], MAX_ADDR_STR, "%p", p);
	printf("Allocated ptr %s\n", addr_str_arr[imalloc]);
	unsigned hret = 0;
	ENTRY e, *ep;
	e.key = addr_str_arr[imalloc];
	hret = hsearch_r(e, FIND, &ep, &d_mallocs);
	if (hret != 0) {
		ep->data = (void *)&(malloc_arr[imalloc]);
	}
	else {
		e.data = (void *)&(malloc_arr[imalloc]);
		hsearch_r(e, ENTER, &ep, &d_mallocs);
	}
	imalloc++;
	return p;
}

void vofree (void* ptr) {
	signal(SIGSEGV, handler);   // install our handler
	num_frees++;
	free(ptr);

//	memcpy(pbad, ptr, 100000);
//	raise(SIGSEGV);
	
	if (ptr == NULL) {
		printf("trying to free NULL pointer\n");
		raise(SIGSEGV);
	}
	unsigned hret = 0;
	ENTRY e, *ep;
	char sbuf[32];
	snprintf(sbuf, 32, "%p", ptr);
	printf("Freeing pointer %s\n", sbuf);
	if (strcmp(sbuf, "(nil)") == 0) {
		printf("trying to free nil pointer\n");
		raise(SIGSEGV);
	}
	e.key = sbuf;
	hret = hsearch_r(e, FIND, &ep, &d_mallocs);
	if (hret == 0) {
		printf("Warning. free called for pointer %s which was not found\n", sbuf);
		return;
	}
	bool * pb = (bool *)(ep->data);
	if (!*pb) {
		printf("Trying to free pointer %s which has already been freed.\n", sbuf);
	}
	*pb = false;
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
	printf("int list len %d: ", sl->len);
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

void match_phrase_print(tSMatchPhrase * ppm) {
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
	if (papp->mpdb_bins == NULL) {
		papp->mpdb_num_recs = 0;
		return;
	}
	int irec;
	printf("app_mpdb_bin_free asked to free %d recs.\n", papp->mpdb_num_recs);
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
	int replace_iopts_len; // len for the next few lists. All used to find var val replacements to the null phrase
	int * l_iopts; // iopt of the val from var_vals that should be used to replace the var
	int * l_replace_iels; // iel of the value of l_iopts and var_val_lens
	int * l_var_vals_lens; // length of the list of vals for that iopt in l_var_vals
	int ** l_product_perms; // holds the list possible combinations of l_var_vals_lens
	tSPhrase perm_phrase;
	// an array of int* each of which holds which var from var_vals was selected for this phrase
	// lenght of the array is match_phrases_len, each of length num_vars. //This last is filled by the time this is used
	// vars that are irrelvant for this phrase are kept at -1
	int ** ll_match_phrase_var_sels; 
	int * l_match_phrase_stage; // Length match_phrases_len. States which stage the match_phrase belongs to.
	int num_forbidden; // number of combs in the forbidden array next
	int ** ll_forbidden_combs; // An array of lenght num_forbidden. Each num_vars ints long
	int * l_comb_vars; // one array num_vars long. Used as a temp variable when translating a product array to all vars
	int num_combos; // number of combos found. The length of the next array
	int ** ll_match_iphrase_combos; // Each combo has length pvos->pgg->l_phrases_len_len. One index into l_match_phrases per stage
	int * l_comb_cand; // len pvos->pgg->l_phrases_len_len
} tSVOState;

//tSNtVars * pnv = NULL;
//int num_vars = 0;
//int curr_var_num = 0;

void * init_vo(void * hgg, void * hmpdb, char * db_name, int call_num) {
	printf("Memory report at init_vo: %d allocs and %d frees, %d unfreed\n", num_mallocs, num_frees, num_mallocs - num_frees);
	printf("init_vo called.\n");
	vo_call_num = call_num;
	vo_malloc_reset();
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
	pvos->replace_iopts_len = 0;
	pvos->l_iopts = NULL;
	pvos->l_replace_iels = NULL;
	pvos->l_var_vals_lens = NULL;
	pvos->l_product_perms = NULL;
	pvos->perm_phrase.len = 0;
	pvos->perm_phrase.pl = NULL;
	pvos->ll_match_phrase_var_sels = NULL;
	pvos->l_match_phrase_stage = NULL;
	pvos->num_forbidden = 0;
	pvos->ll_forbidden_combs = NULL;
	pvos->l_comb_vars = NULL;
	pvos->num_combos = 0; 
	pvos->ll_match_iphrase_combos = NULL;
	pvos->l_comb_cand = NULL; 
	
	return (void *)pvos;
}

void free_vo(void * hvos) {
	tSVOState * pvos = (tSVOState *)hvos;

	if (pvos->l_comb_cand != NULL) {
		vofree(pvos->l_comb_cand);
	}
	if (pvos->ll_match_iphrase_combos != NULL) {
		for (int i=0; i<pvos->num_combos;i++) {
			vofree(pvos->ll_match_iphrase_combos[i]);
		}
		vofree(pvos->ll_match_iphrase_combos);
	}
	if (pvos->l_comb_vars != NULL) {
		vofree(pvos->l_comb_vars);
	}
	if (pvos->ll_forbidden_combs != NULL) {
		for (int i=0;i<pvos->num_forbidden;i++) {
			vofree(pvos->ll_forbidden_combs[i]);
		}
		vofree(pvos->ll_forbidden_combs);
	}
	if (pvos->l_match_phrase_stage != NULL) {
		vofree(pvos->l_match_phrase_stage);
	}
	if (pvos->ll_match_phrase_var_sels != NULL) {
		for (int imatch=0;imatch<pvos->match_phrases_len;imatch++) {
			vofree(pvos->ll_match_phrase_var_sels[imatch]);
		}
		vofree(pvos->ll_match_phrase_var_sels);
	}
	if (pvos->perm_phrase.pl != NULL) {
		vofree(pvos->perm_phrase.pl);
		pvos->perm_phrase.len=0;
	}
	perm_free(pvos->l_product_perms);
	if (pvos->l_var_vals_lens != NULL) {
		vofree(pvos->l_var_vals_lens);
	}
	if (pvos->l_replace_iels != NULL) {
		vofree(pvos->l_replace_iels);
	}
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
	printf("Memory report on vo free: %d allocs and %d frees, %d unfreed\n", num_mallocs, num_frees, num_mallocs - num_frees);
	vo_malloc_test();
	vo_call_num = -1;

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
	printf("convert_wlist_to_phrase allocated ptr at %p.\n", pphrase->pl);
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

void match_phrase_var_sel_append(tSVOState * pvos, int istage) {
	printf("match_phrase_var_sel_append called.\n");
	int ** old_var_sels = pvos->ll_match_phrase_var_sels;
	int * old_stages = pvos->l_match_phrase_stage;
	int old_len = pvos->match_phrases_len - 1;
	pvos->ll_match_phrase_var_sels = (int**)vomalloc(sizeof(int*)*pvos->match_phrases_len);
	pvos->l_match_phrase_stage = (int*)vomalloc(sizeof(int)*pvos->match_phrases_len);
	if (old_len>0) {
		memcpy(pvos->ll_match_phrase_var_sels, old_var_sels, old_len*sizeof(int*));
		vofree(old_var_sels);
		memcpy(pvos->l_match_phrase_stage, old_stages, old_len*sizeof(int));
		vofree(old_stages);
	}
	int ** new_var_sels = &(pvos->ll_match_phrase_var_sels[old_len]);
	*new_var_sels = (int*)vomalloc(sizeof(int)*pvos->num_vars);
	for (int ivar=0; ivar<pvos->num_vars;ivar++) {
		(*new_var_sels)[ivar] = -1;
	}
	for (int iel=0;iel<pvos->pgg->l_phrases_len[istage];iel++) {
		int ivar = pair_dict_get(pvos->d_var_opts, istage, iel);
		(*new_var_sels)[ivar] = 0;
	}
	pvos->l_match_phrase_stage[old_len] = istage;
	printf("match_phrase_var_sel_append returning.\n");
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

int * int_arr_add_val(int * arr, int len, int val)
{
	int*new_arr = (int*)vomalloc(sizeof(int)*(len+1));
	if (arr != NULL) {
		memcpy(new_arr, arr, sizeof(int)*len);
		vofree(arr);
	}
	new_arr[len] = val;
	return new_arr;
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

void cartesian_product(int len_in, int * l_in, int *** pout, int * pnum_out) {
	int num_out = 1;
	for (int iin = 0; iin < len_in; iin++) {
		num_out *= l_in[iin];
	}
	int ** l_out = (int**)vomalloc(sizeof(int*)*num_out);
	int *buf = (int*)vomalloc(sizeof(int)*num_out*len_in);
//	printf("cartesian_product allocated %p and %p.\n", buf, l_out);
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

void perm_free(int** l_out) {
	if (l_out != NULL) {
//		printf("perm_free freeing %p and %p \n", l_out[0], l_out);
		vofree(l_out[0]);
		vofree(l_out);
	}
	l_out = NULL;
}

int do_vo(void * hvos) {
	signal(SIGSEGV, handler);   // install our handler

	tSVOState * pvos = (tSVOState *)hvos;
	tSVOApp * papp = pvos->pgg->pApp;
	int i,j;
	int num_loc_pairs = 0;
	int max_phrase_len = 0;

	// put the values we already know in l_var_vals. This array holds all the possible
	// values for all vars through all the phrases of the rule. For some of the elements of
	// this list, there is only one value. 
	// This one value could either be a string or NULL.
	// It is a string if the rule itself gives an exact string, such as rec_def_obj
	// It is also a string if the external conditions that the function was called for gives an exact 
	// string. Externel conditions are the l_var_opts that are passed to the module using cnt_vars.
	// Note, even externally set vars may not be exact. In that case b_bound field is false and l_var_vals will hold a
	// null.
	// It is null if the external is not bound or if the rule itself gives no exact value
	// If the var_val is not excact, the var_val will be a list containing a NULL but also other values 
	// These other values will be picked up from the database of facts.
	// The pnv, var_vals and var_locs are built up in stages
	// First, they are set by the external conditions.
	// Later they will be joined by those that are vars of the rule and appear in multiple places in 
	// the phrases of the rule
	// Lastly, it is completed by adding all the remaining els of the phrase.
	// The Later and Lastly are not done here, they are implmented.. later.
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
	// Now we want to build up some array we will need for later processing. We well need to translate
	// the loc which is an absolute number incrementing across all the els of the rule into a stage/phrase number (istage or iphrase)
	// and an index of the element into the phrase - noramlly called iel
	// We first build a an array of the loc number at the start of the phrase called l_phrase_starts
	// Next we figure out the length of the longest phrase, so that we can allocate the next structure
	// This next structure is d_var_opts. This is a 2-D array whose dimensions are the number of stages and the number
	// of elements in the structure. Using this we can find the ivar (or iopt) of the element. 
	// We also maintain a list of locations where each var appears in the rule. l_var_all_locs
	// Finally, we also maintin the list of first location for the var, l_var_loc_pairs. This is the source copied to other locations
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
					// The first location (expressed as istage/iel pair is stored now in all_locs but will be added to later.
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
	// Here the bitvec and hd_max defining each element is broken down from the original rule data into arrays - one for each phrase
	// This will be used to make copies of the data to secondary locations belonging to the same var
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
	// We are now ready to add the vars of the rule itself into the l_vars, l_var_vals and l_var_all_locs
	// Remeber, some of the vars internal to the rule were already added because they were also accessed 
	// at the result of the rule whose requirements we passed in "externally"
	{
		int ivar;
		int iopt_now = pvos->num_vars;
		int num_new_vars = 0;
//		int * var_loc_adds;
		for (ivar=0; ivar < pvos->pgg->l_wlist_vars_len; ivar++) {
			int * wlist_var = pvos->pgg->l_wlist_vars[ivar];
			int src_istage = wlist_var[0];
			int src_iel = wlist_var[1];
			// The following checks that the var was not already set externally
			// In the current heavy-malloc implementation, we count the mallocs to avoid having to malloc each one REMOVE THIS COMMENT WHEN MOVING TO STATIC MALLOC!
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
		// The way vars are stored in the rule structure (pgg), is in pairs of src and dest. The original location
		// does not have its own entry; only when a later el makes a ref to an earlier el, is it called a var.
		// Therefore, the earlier entry is either an already known var or a new one.
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
				// Fear not. A later test for whether the hd_max is zero will *replace* the NULL with an exact value string
				str_list_add_val(&(pvos->l_var_vals[iopt_now]), NULL);
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
//			printf("end if iopt == -1\n");
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

	// This block has at least two functions.
	// Firstly, as a result of its other operations, it might decide that the match between the external var and the
	// rule var is mistaken. The words do not match and the leniency given in the two do not allow to match them.
	// The whole rule fails and there is a return 0
	// Barring that, the result of this function is to possibly tighten the hd_max for the var/opt.
	// For example the external set might allow any kind of object but the rule allows only a specific kind. 
	// This is an example of an internal set.
	// On the ohter hand, the external may be more strict. This is an external set. It results in taking the 
	// external value as the src_pat and hd_max instead of the values from the rule itself
	// One last effect, is that if the internal hd_max is exact then the var_val should not contain a NULL.
	// It is replaced by the exact value. This is true even if a var has no connection to an external setting.
	// If an hd IS tightened by the ext value, the src pat of the ext replaces the int
	{
		int iopt;
		for (iopt=0; iopt<pvos->num_vars; iopt++) {
			tSNtVars * var_opt = &(pvos->pnv[iopt]);
			tSIntPairList * var_all_locs = &(pvos->l_var_all_locs[iopt]);
			int src_istage = var_all_locs->pl[0][0];
			int src_iel = var_all_locs->pl[0][1];
			// in code till now, no var has been resolved
			// So presumably this test only applies if the opt is revisited within this code loop
			// or maybe it is defensive code against the possibility of the code above changing. In which case
			// an assert would be more appropriate
			if (!var_opt->b_resolved) {
				printf("Resolving var %d. stage %d, iel %d\n", iopt, src_istage, src_iel);
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
				printf("Resolving by int is %s\n", (b_set_by_int ? "True" : "False"));
				if (b_set_by_int) {
					int nd_el_match_idx = bin_idx_best_match(	papp->el_bin_db, int_els_rep,
																papp->el_bin_db_len, papp->bitvec_size);
					char *el_word = get_word_by_id(papp, nd_el_match_idx);
					bool b_exact = (pvos->ll_hd_max[src_istage][src_iel] == 0);
					printf(	"Resolving exact = %s. hd_max = %d \n", (b_set_by_int ? "True" : "False"), 
							(pvos->ll_hd_max[src_istage][src_iel]));
					var_opt->b_bound=b_exact, var_opt->b_must_bind=b_exact, var_opt->val = el_word;
					var_opt->b_resolved = true;
					var_opt->cd = 1.-((double)((pvos->ll_hd_max[src_istage][src_iel]) / papp->bitvec_size));
					if (b_exact) {
						str_list_reset_with_one_val(&(pvos->l_var_vals[iopt]), el_word);
					}
				}
			}
		}
		// All we're doing here is copying sr_pat/bitvecs and the hd_max from the src to the dest iels
		// We can only do that once we have tigtened some of the bitvecs
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
			// The last comment no longer applies but is kept for reasons of historical interest
			// We will have var entries for every single el whether exact or not. The only reason the 
			// var table is not kept in order of els is because some els are joined by the fac tthat they must have 
			// the same vale
			// once finished, we will not need to add any more to the var table but we will need to add to the l_var_vals
			// of each entry
			int istage;
			for (istage=0;istage<pvos->pgg->l_phrases_len_len;istage++) {
				int phrase_len = pvos->pgg->l_phrases_len[istage];
				int iel;
				for (iel=0; iel<phrase_len;iel++) {
					int ivar = pair_dict_get(pvos->d_var_opts, istage, iel);
					int old_num_vars = pvos->num_vars;
//					if (ivar != -1 || pvos->ll_hd_max[istage][iel] == 0)
//						continue;
					if (ivar != -1)
						continue;
					int hd_max =  pvos->ll_hd_max[istage][iel];
					pvos->num_vars++;
					pair_dict_set(pvos->d_var_opts, istage, iel, old_num_vars);
					// The following function is computationally expensive
					// Its only justification is the readability of the output
					// later version of this code could rely only on the bitvectors 
					// but the change should be made at all the levels calling this function too
					int nd_el_match_idx = bin_idx_best_match(	papp->el_bin_db, pvos->ll_src_pat[istage][iel],
																papp->el_bin_db_len, papp->bitvec_size);
					char *el_word = get_word_by_id(papp, nd_el_match_idx);
					bool b_exact = (hd_max == 0);
					// The following blocks are just a womewhat wordy way of increasing the size of the num_vars 
					// related arrays
					{
						tSNtVars * old_pnv = pvos->pnv;
						tSNtVars nv;
						pvos->pnv = (tSNtVars *)vomalloc(sizeof(tSNtVars) * pvos->num_vars);
						memcpy(pvos->pnv, old_pnv, sizeof(tSNtVars) * old_num_vars);
						vofree(old_pnv);
						nv.loc = pvos->l_phrase_starts[istage]+iel, nv.b_bound = b_exact, nv.b_must_bind = false;
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
						str_list_add_val(&(pvos->l_var_vals[old_num_vars]), (b_exact ? el_word : NULL));
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
		// We now find phrases in the database that match the rule. This will supply us with possible values for
		// the vars. This will be aplied to the phrase itself, obviously. However, later the values will be applied
		// to other phrases, that become fictitious options.
		// A very important role for this block of the code is to begin building l_match_phrase
		// each record of l_match_phrase is a match or possible match for a phrase rule
		// This is ultimately one of the two outputs of this function
		// The null phrase is basically the phrase as it exists in the rule, possibly modified
		// only by the external setting of vars with which the vo function is called.
		int idb = mpdb_get_idb(pvos->pmpdb, pvos->db_name);
		char * nd_default_idb_mrk;
		int istage;
		tSIntPairList * pl_story_rphrases = &(pvos->pmpdb->l_srphrases);
		if (idb < 0) {
			printf("Coding error! no idb for %s\n", pvos->db_name);
		}
		// nd_default_idb_mrk is the array of markers across records, specifiying which records this particular
		// agent/database believes to be true
		nd_default_idb_mrk = pvos->pmpdb->l_idb_mrks[idb]; //  mpdb_mgr.get_nd_idb_mrk(idb)
		// Set up the stage_vars array. One list for each phrase/stage of the vars affecting that stage
		// Currently considering doing this so that this data structure is not needed.
		pvos->stage_vars_len = pvos->pgg->l_phrases_len_len;
		pvos->l_stage_vars = (tSIntList*)vomalloc(sizeof(tSIntList)*pvos->stage_vars_len);
		for (istage=0;istage<pvos->pgg->l_phrases_len_len;istage++) {
			int_list_init(&(pvos->l_stage_vars[istage]));
		}
		// Set up a number of marker arrays across records of the database. These are used to eventually mark
		// in m_match those phrase matched by this phrase of the rule itself
		pvos->mpdb_story_rphrase_size = pl_story_rphrases->len;
		pvos->l_ilen_mrk = (char*)vomalloc(pvos->mpdb_story_rphrase_size*sizeof(char));
		pvos->m_match = (char*)vomalloc(pvos->mpdb_story_rphrase_size*sizeof(char));
		pvos->m_mrks = (char*)vomalloc(pvos->mpdb_story_rphrase_size*sizeof(char));
		for (istage=0;istage<pvos->pgg->l_phrases_len_len;istage++) {
			int phrase_len = pvos->pgg->l_phrases_len[istage];
			int isr, iel;
			char *el_word;
			// Create a marker of database recs that have the same length as rule phrase
			for (isr=0;isr<pl_story_rphrases->len;isr++) {
				pvos->l_ilen_mrk[isr] = ((pvos->pgg->l_phrases_ilen[istage] == pl_story_rphrases->pl[isr][0]) 
										? (char)1 : (char)0);
//				pvos->m_match[isr] = (char)1;
			}
			// Mark records that are the same len and also believed by this agent
			bin_logical_and(pvos->m_mrks, nd_default_idb_mrk, pvos->l_ilen_mrk, pvos->mpdb_story_rphrase_size);
			// copy into m_match
			memcpy(pvos->m_match, pvos->m_mrks, pvos->mpdb_story_rphrase_size*sizeof(char));
			if (pvos->l_phrase_found.pl != NULL) {
				vofree(pvos->l_phrase_found.pl);
				pvos->l_phrase_found.pl = NULL;
				pvos->l_phrase_found.len = 0;
			}
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
				
				if (iopt == -1 || pvos->pnv[iopt].val == NULL) {
					printf("Error! At this point there should be no iopt == -1. or var val not set\n");
					printf("Error at stage %d, iel %d.\n", istage, iel);
					assert(false);
				}
//				if (iopt == -1 || !pvos->pnv[iopt].b_bound) {
//					int nd_el_match_idx = bin_idx_best_match(	papp->el_bin_db, src_pat,
//																papp->el_bin_db_len, papp->bitvec_size);
//					el_word = get_word_by_id(papp, nd_el_match_idx);
//				}
//				else {
//					el_word = pvos->pnv[iopt].val;
//				}
				el_word = pvos->pnv[iopt].val;
				
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
			// as comment before, not sure we really need this data structure
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
				printf("%d l_stage_vars:\n", pvos->stage_vars_len);
				for (iistage=0; iistage<pvos->stage_vars_len; iistage++) {
					int_list_print(&(pvos->l_stage_vars[iistage]));
				}
			}
			{
				// These first phrases, embedded in match_phrase are the null phrase.
				// The null phrase is used to build other phrases when the null values are replaced by 
				// found values
				{
					int * old_null_phrases = pvos->l_i_null_phrases;
					int old_i_null_phrases_len = pvos->i_null_phrases_len;
					printf("pvos->l_i_null_phrases len %d increasing..\n", old_i_null_phrases_len);
					pvos->i_null_phrases_len++;
					pvos->l_i_null_phrases = (int *)vomalloc(sizeof(int)*pvos->i_null_phrases_len);
					if (old_null_phrases != NULL) {
						memcpy(pvos->l_i_null_phrases, old_null_phrases, sizeof(int)*old_i_null_phrases_len);
						vofree(old_null_phrases);
					}
					pvos->l_i_null_phrases[old_i_null_phrases_len] = pvos->match_phrases_len;
				}
				// use the l_phrase_found to create a match phrase and append it to the list.
				// This is one of the null phrases.
				// Note, the l_match_phrase memory is not used. It is copied to its own list owned memory.
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
				
				// Add an array num_vars long to the pvos->ll_match_phrase_var_sels array. Each relevant var
				// will be zero; the first entry in the var_vals. The remainder are -1
				// Note the first entry will be null for rec def like and the actual value for an obj
				// This function also records the stage of the match phrase
				match_phrase_var_sel_append(pvos, istage);
				// We might be able to remove the match_binings structure. REMOVE THIS COMMENT ONCE IMPLEMENTED
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
				// We now go through the m_match markers, finding the phrases in the db for the agent
				// that match the rule.
				
				int imatch;
				for (imatch=0;imatch<pvos->mpdb_story_rphrase_size;imatch++) {
					intpair * story_rphrase;
					tSStrList * p_story_wlist;
					char bmatch = pvos->m_match[imatch];
					if (bmatch==(char)0) {
						continue;
					}
					printf("Testing imatch %d\n", imatch);
					// get the phrase ref
					story_rphrase = &(pvos->pmpdb->l_srphrases.pl[imatch]);
					// use the phrase ref to get the text itself.
					// An alternative would be to access the mpdb bins directly 
					// This would apply in a world where we use only the bitvecs and not the text
					p_story_wlist = &(papp->ll_phrases[(*story_rphrase)[0]].pl[(*story_rphrase)[1]]);
					if (pvos->l_story_phrase_found.pl != NULL) {
						vofree(pvos->l_story_phrase_found.pl);
						pvos->l_story_phrase_found.pl = NULL;
					}
					// Add a rec_def_obj to each el. This works because the database contains only objs and no like
					convert_wlist_to_phrase(&(pvos->l_story_phrase_found), p_story_wlist);
					printf("l_story_phrase_found for %d: ", imatch);
					phrase_print(&(pvos->l_story_phrase_found));
					// test for unexpected double. No two els which are not part of the same var may have the same vale
					pvos->num_test_phrases = 1;
					pvos->l_test_phrases = &(pvos->l_story_phrase_found);
					if (pvos->l_test_stages != NULL) {
						vofree(pvos->l_test_stages);
					}
					pvos->l_test_stages = (int*)vomalloc(sizeof(int));
					pvos->l_test_stages[0] = istage;
					bool b_bad_double = test_for_unexpected_double(pvos);
					if (b_bad_double) {
						printf("bad double found on match %d.\n", imatch);
						pvos->m_match[imatch] = (char)0;
						continue;
					}
					match_phrase_append(pvos, istage, true, &(pvos->l_story_phrase_found));
					// initially create a null var sel. This will now be modified 
					match_phrase_var_sel_append(pvos, istage);
					int * new_var_sels = pvos->ll_match_phrase_var_sels[pvos->match_phrases_len-1];
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
							new_var_sels[ivar] = ivar_val;
							// Again with the stage vars. Perhaps we can remove. REMOVE THIS COMMENT IF stage_vars ARE REMOVED
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
			match_phrase_print(&(pvos->l_match_phrases[i]));
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
		// Here we search for forbidden combinations. Any values of one var that is equal to the value of
		// another var is forbidden becuase in that case there would be a new var 
		for (int ivar1 = 0; ivar1 < pvos->num_vars; ivar1++) {
			for (int ivar2 = ivar1+1; ivar2 < pvos->num_vars; ivar2++) {
//				if (ivar1 == ivar2) continue;
				for (int ival1 = 0; ival1 < pvos->l_var_vals[ivar1].len;ival1++) {
					if (pvos->l_var_vals[ivar1].pl[ival1] == NULL) continue;
					for (int ival2 = 0; ival2 < pvos->l_var_vals[ivar2].len;ival2++) {
						if (pvos->l_var_vals[ivar2].pl[ival2] == NULL) continue;
						if (strcmp(pvos->l_var_vals[ivar1].pl[ival1], pvos->l_var_vals[ivar2].pl[ival2]) == 0) {
							printf("Hit a forbidden combi for ivar1 %d, ival1 %d, ivar2 %d, ival2 %d, val %s.\n",
									ivar1, ival1, ivar2, ival2, pvos->l_var_vals[ivar1].pl[ival1]);
							int old_len = pvos->num_forbidden;
							int** old_p = pvos->ll_forbidden_combs;
							pvos->num_forbidden++;
							pvos->ll_forbidden_combs = (int **)vomalloc(sizeof(int*)*pvos->num_forbidden);
							if (old_len > 0) {
								memcpy(pvos->ll_forbidden_combs, old_p, sizeof(int*)*old_len);
								vofree(old_p);
							}
							int ** pvec = &(pvos->ll_forbidden_combs[old_len]);
							*pvec = (int*)vomalloc(sizeof(int)*pvos->num_vars);
							for (int ivar=0; ivar<pvos->num_vars; ivar++) {
								if (ivar==ivar1) {
									(*pvec)[ivar] = ival1;
								}
								else if (ivar == ivar2) {
									(*pvec)[ivar] = ival2;
								}
								else {
									(*pvec)[ivar] = -1;
								}
							}
						}
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
		// Now we add the fictional match phrases. We build these by taking the var vals for each var
		// and trying different combinations of them
		// First we build an array of limits for each element of the combination. The cartesian_product function,
		// later, will take this array of limits and create all the combinations, each the same length as the input
		// of numbers where each element is less than the limit at that location.
		// This is done by finding the ivar for each el of the phrase. If the var for that position is not 
		// bound, we make the limit simply the number of elements of the l_var_vals for that var. In ohter
		// words, every perm will have an index into the l_var_vals for that val,
		// We also record the var number and iel for later use
		for (int iphrase=0;iphrase<pvos->i_null_phrases_len;iphrase++) {
			int i_null_phrase = pvos->l_i_null_phrases[iphrase];
			tSMatchPhrase * null_match_phrase = &(pvos->l_match_phrases[i_null_phrase]);
			printf("Null match phrase for phrase %d: \n", iphrase);
			match_phrase_print(null_match_phrase);
			int istage = null_match_phrase->istage;
			if (pvos->l_iopts != NULL) {
				vofree(pvos->l_iopts);
				vofree(pvos->l_var_vals_lens);
				vofree(pvos->l_replace_iels);
				pvos->l_iopts = pvos->l_var_vals_lens = pvos->l_replace_iels = NULL;
				pvos->replace_iopts_len = 0;
			}
			if (pvos->l_product_perms != NULL) {
				perm_free(pvos->l_product_perms);
				pvos->l_product_perms = NULL;
			}
			for (int iel=0;iel<pvos->pgg->l_phrases_len[istage];iel++) {
				int iopt = pair_dict_get(pvos->d_var_opts, istage, iel);
				if (iopt == -1 || pvos->pnv[iopt].b_bound) {
					continue;
				}
				printf("Adding elements %d, %d, %d to replace lists.\n", iopt, iel, pvos->l_var_vals[iopt].len);
				pvos->l_iopts = int_arr_add_val(pvos->l_iopts, pvos->replace_iopts_len, iopt);
				pvos->l_replace_iels = int_arr_add_val(pvos->l_replace_iels, pvos->replace_iopts_len, iel);
				pvos->l_var_vals_lens = int_arr_add_val(pvos->l_var_vals_lens, pvos->replace_iopts_len, 
														pvos->l_var_vals[iopt].len);
				pvos->replace_iopts_len++;
//				{
//					int old_len = pvos->iopts_len;
//					int * old_pl = pvos->l_iopts;
//					pvos->iopts_len++;
//					pvos->l_iopts = (int*)vomalloc(sizeof(int)*pvos->iopts_len);
//					if (old_pl != NULL) {
//						memcpy(pvos->l_iopts, old_pl, sizeof(int)*old_len);
//						vofree(old_pl);
//					}
//					pvos->l_iopts[old_len] = iopt;
//				}
				
			}
			// here is the function calls that makes the perms
			int num_products = 0;
			cartesian_product(pvos->replace_iopts_len, pvos->l_var_vals_lens, &(pvos->l_product_perms), &num_products);
			if (pvos->l_comb_vars == NULL) {
				pvos->l_comb_vars = (int*)vomalloc(sizeof(int)*pvos->num_vars);
			}
			// loop through the perms
			for (int iperm=0; iperm<num_products;iperm++) {
				bool b_match_exists = false;
				int * perm = pvos->l_product_perms[iperm];
				// for this perm set up a translation to an array of all vars where the vals of that perm, if relevant,
				// appear in the var location otherwise -1
				for (int ivar=0;ivar<pvos->num_vars;ivar++) {
					pvos->l_comb_vars[ivar] = -1;
				}
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
						printf("perm %d forbidden by comb %d\n", iperm, iforbidden);
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
						int ivar = pair_dict_get(pvos->d_var_opts, istage, iel);
						if (pvos->ll_match_phrase_var_sels[imatch][ivar] != perm[ii]) {
							bmatched = false;
							printf("No match between perm %d and match phrase %d\n", iperm, imatch);
							break;
						}
					}
					if (bmatched) {
						printf("Match between perm %d and match phrase %d\n", iperm, imatch);
						b_match_exists = true;
						break;
					}
				}
				if (b_match_exists) continue;
				// If the comb does not already exist, create a new one
				printf("Creating new match phrase for perm %d\n", iperm);
//				null_match_phrase = &(pvos->l_match_phrases[i_null_phrase]);
				tSPhrase * null_phrase = &(pvos->l_match_phrases[i_null_phrase].phrase);
				if (pvos->perm_phrase.pl != NULL) {
					vofree(pvos->perm_phrase.pl);
					pvos->perm_phrase.len=0;
					pvos->perm_phrase.pl = NULL;
				}
				pvos->perm_phrase.len = null_phrase->len;
				pvos->perm_phrase.pl = (tSPhraseEl*)vomalloc(sizeof(tSPhraseEl)*null_phrase->len);
				printf("%d perm els. null phrase len %d.\n", pvos->replace_iopts_len, null_phrase->len);
				memcpy(pvos->perm_phrase.pl, null_phrase->pl, sizeof(tSPhraseEl)*null_phrase->len);
				printf("%d perm els. null phrase len %d.\n", pvos->replace_iopts_len, null_phrase->len);
				for (int ii=0;ii<pvos->replace_iopts_len;ii++) {
					int iel = pvos->l_replace_iels[ii];
					int ivar = pair_dict_get(pvos->d_var_opts, istage, iel);
					char * val = pvos->l_var_vals[ivar].pl[perm[ii]];
					printf("iel: %d, ivar %d, val %s.\n", iel, ivar, val);
					if (val == NULL) continue;
					pvos->perm_phrase.pl[iel].cd = 1.0;
					pvos->perm_phrase.pl[iel].val = val;
					pvos->perm_phrase.pl[iel].el_type = etRecDefObj;
				}
				match_phrase_append(pvos, istage, false, &(pvos->perm_phrase));
				match_phrase_print(&(pvos->l_match_phrases[pvos->match_phrases_len-1]));
				match_phrase_var_sel_append(pvos, istage);
				int * new_var_sels = pvos->ll_match_phrase_var_sels[pvos->match_phrases_len-1];
				for (int ii=0;ii<pvos->replace_iopts_len;ii++) {
					int iel = pvos->l_replace_iels[ii];
					int ivar = pair_dict_get(pvos->d_var_opts, istage, iel);
					new_var_sels[ivar] = perm[ii];
				}
			}
			
		}
	}
	{
		// Last stage. We build the combos.
		if (pvos->l_var_vals_lens != NULL) {
			vofree(pvos->l_var_vals_lens);
			pvos->l_var_vals_lens = NULL;
		}
		if (pvos->l_product_perms != NULL) {
			perm_free(pvos->l_product_perms);
			pvos->l_product_perms = NULL;
		}
		// Again we will use the cartesian_product function. But this time we will use as input all the
		// lengths of all the vars. So that we will create all combinations of all var vals
		pvos->l_var_vals_lens = (int*)vomalloc(sizeof(int)*pvos->num_vars);
		for (int ivar=0;ivar<pvos->num_vars;ivar++) {
			pvos->l_var_vals_lens[ivar] = pvos->l_var_vals[ivar].len;
		}
		int num_products = 0;
		cartesian_product(pvos->num_vars, pvos->l_var_vals_lens, &(pvos->l_product_perms), &num_products);
		if (pvos->l_comb_cand != NULL) {
			vofree(pvos->l_comb_cand);
			pvos->l_comb_cand = NULL;
		}
		pvos->l_comb_cand = (int*)vomalloc(sizeof(int)*pvos->pgg->l_phrases_len_len);
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
			for (int istage=0;istage<pvos->pgg->l_phrases_len_len;istage++) {
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
				int ** oldp = pvos->ll_match_iphrase_combos;
				pvos->num_combos++;
				pvos->ll_match_iphrase_combos = (int **)vomalloc(sizeof(int*)*pvos->num_combos);
				if (old_len > 0) {
					memcpy(pvos->ll_match_iphrase_combos, oldp, sizeof(int*)*old_len);
					vofree(oldp);
				}
				pvos->ll_match_iphrase_combos[old_len] = (int*)vomalloc(sizeof(int)*pvos->pgg->l_phrases_len_len);
				memcpy(pvos->ll_match_iphrase_combos[old_len], pvos->l_comb_cand, sizeof(int)*pvos->pgg->l_phrases_len_len);
			}
		}
		
	}
	{
		printf("vo summary:\n");
		printf("%d match phrases:\n", pvos->match_phrases_len );
		for (int i=0; i<pvos->match_phrases_len;i++) {
			printf("%d: ", i);
			match_phrase_print(&(pvos->l_match_phrases[i]));
		}
		printf("%d match phrase combos.\n", pvos->num_combos);
		for (int i=0; i<pvos->num_combos; i++) {
			printf("%d: ", i);
			for (int j=0; j<pvos->pgg->l_phrases_len_len;j++) {
				printf("%d, ", pvos->ll_match_iphrase_combos[i][j]);
			}
			printf("\n");
		}

	}
	return 1;
	
}