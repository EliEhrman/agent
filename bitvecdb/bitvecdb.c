/* bitvecdb.c */
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

int My_variable = 3;
double density = 4.1;

#define CLUSTER_BY_EL true


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

int bdb_call_num = -1;

//#define TEST_MALLOC
#ifdef TEST_MALLOC
#define MALLOC_HASH_MAX 100000
#define MAX_ADDR_STR 32
struct hsearch_data d_mallocs;
int imalloc = 0;
bool b_malloc_init = false;
//int malloc_hash_max = 100000;
bool malloc_arr[MALLOC_HASH_MAX];
char addr_str_arr[MALLOC_HASH_MAX][MAX_ADDR_STR];
char * pbad = 0;

void bdb_malloc_init(void) {
	imalloc = 0;
	memset(&(d_mallocs), 0, sizeof (struct hsearch_data));
	hcreate_r(MALLOC_HASH_MAX, &d_mallocs);
	memset(malloc_arr, 0, MALLOC_HASH_MAX * sizeof (bool));
}
#endif // TEST_MALLOC

void bdb_malloc_reset(void) {
#ifdef TEST_MALLOC
	hdestroy_r(&d_mallocs);
	b_malloc_init = false;
#endif // TEST_MALLOC
}

void bdb_malloc_test(void) {
#ifdef TEST_MALLOC
	for (int i = 0; i < imalloc; i++) {
		if (malloc_arr[i]) {
			printf("malloc at # %d not freed, bdb_call_num %d.\n", i, bdb_call_num);
		}
	}
#endif // TEST_MALLOC
}

void* bdbmalloc2(size_t numels, size_t elsize) {
#ifdef TEST_MALLOC
	if (!b_malloc_init) {
		bdb_malloc_init();
		b_malloc_init = true;
	}
#endif // TEST_MALLOC
	num_mallocs++;
	//	if (imalloc == 83 && bdb_call_num == 11) {
	//		printf("imalloc # %d hit for bdb_call_num %d.\n", imalloc, bdb_call_num);
	//		raise(SIGSEGV);
	//	}
	void * p = calloc(numels, elsize);
#ifdef TEST_MALLOC
	malloc_arr[imalloc] = true;
	//	char sbuf[32];
	snprintf(addr_str_arr[imalloc], MAX_ADDR_STR, "%p", p);
	printf("Allocated ptr %s\n", addr_str_arr[imalloc]);
	unsigned hret = 0;
	ENTRY e, *ep;
	e.key = addr_str_arr[imalloc];
	hret = hsearch_r(e, FIND, &ep, &d_mallocs);
	if (hret != 0) {
		ep->data = (void *) &(malloc_arr[imalloc]);
	} else {
		e.data = (void *) &(malloc_arr[imalloc]);
		hsearch_r(e, ENTER, &ep, &d_mallocs);
	}
	imalloc++;
#endif // TEST_MALLOC
	return p;
}

void* bdbmalloc(size_t size) {
	return bdbmalloc2(size, 1);
}

void bdbfree(void* ptr) {
	signal(SIGSEGV, handler); // install our handler
	num_frees++;
	free(ptr);
#ifdef TEST_MALLOC

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
	bool * pb = (bool *) (ep->data);
	if (!*pb) {
		printf("Trying to free pointer %s which has already been freed.\n", sbuf);
	}
	*pb = false;
#endif // TEST_MALLOC
}

void* bdballoc(void * ptr, int * palloc_size, size_t elsize, size_t num_els) {
	void * new_ptr;
	if (ptr == NULL) {
		if (*palloc_size > 0) {
			printf("Error. NULL ptr with non zero allocated size.");
			return NULL;
		}
		*palloc_size = num_els;
		new_ptr = bdbmalloc2(num_els, elsize);
		//		printf("%p allocated from new in size %d\n", new_ptr, (int)num_els);
		return new_ptr;
	}
	if (num_els <= *palloc_size) {
		//		printf("%d <= %d so no need to alloc.\n", (int)num_els, *(int*)palloc_size);
		return ptr;
	}
	void * oldp = ptr;
	//	int old_size = *palloc_size;
	new_ptr = bdbmalloc2(num_els, elsize);
	//	printf("freeing %p grow from %d to %d alloc %p.\n", oldp, *(int*)palloc_size, (int)num_els, new_ptr);
	memcpy(new_ptr, oldp, *palloc_size * elsize);
	bdbfree(oldp);
	*palloc_size = num_els;
	return new_ptr;
}


void * init_capp(void) {
//	return NULL;
	tSBDBApp * papp = (tSBDBApp *) bdbmalloc(sizeof (tSBDBApp));
	papp->name = NULL;
	papp->db = NULL;
	papp->num_db_els = 0;
	papp->num_db_els_alloc = 0;
	papp->rec_ptrs = NULL;
	papp->num_rec_ptrs = 0;
	papp->rec_lens = NULL;
	papp->rec_lens_alloc = 0;
	papp->num_rec_ptrs_alloc = 0;
	papp->hd_buf = NULL;
	papp->hd_buf_alloc = 0;
	papp->hd_el_buf = NULL;
	papp->hd_el_buf_alloc = 0;
	papp->agent_mrks = NULL;
	papp->num_agents = 1;
	papp->num_agents_alloc = 0;
	papp->agent_mrk_allocs = NULL;
	papp->agent_num_allocs_alloc = 0;
	papp->num_left_buf = NULL;
	papp->num_left_buf_alloc = 0;
	papp->hd_thresh = NULL;
	papp->hd_thresh_alloc = 0;
	papp->b_hd_thresh = false;
	papp->rule_data = NULL;
	papp->rule_data_alloc = 0;
	papp->b_rules = false;
	papp->rec_buf = NULL;
	papp->rec_buf_alloc = 0;
	papp->b_names = false;
	return (void*) papp;
}

tSPairDict * create_pair_dict(tSPairDict * ppd, int num_rows, int num_cols) {
	int r,c;

	ppd->num_rows = num_rows;
	ppd->num_cols = num_cols;
	int num_els = ppd->num_rows * ppd->num_cols;
	ppd->ppdata = (int **)bdballoc(ppd->ppdata, &(ppd->num_rows_alloc), sizeof(int*), ppd->num_rows);
	ppd->ppdata[0] = (int *)bdballoc(ppd->ppdata[0], &(ppd->num_els_alloc), sizeof(int), num_els);
	int * p = ppd->ppdata[0];
	for (r=0; r<num_rows; r++, p+=ppd->num_cols) {
		if (r > 0) {
			ppd->ppdata[r] = p;
		}
		for (c=0; c<num_cols; c++) {
			ppd->ppdata[r][c] = -1;
		}
	}
	return ppd;
}

void clear_pair_dict(tSPairDict * ppd) {
	if (ppd->ppdata == NULL) {
		printf("Error! Attempting to clear already NULL pair dict.\n");
		raise(SIGSEGV);
	}
	bdbfree(ppd->ppdata[0]);
	bdbfree(ppd->ppdata);

	bdbfree(ppd);
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


void set_el_bitvec_size(void * happ, int size) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->bitvec_size = size;
	//	printf("bitvec size set at %d\n", papp->bitvec_size);
}

void set_name(void * happ, char * name) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	size_t len = strlen(name);
	papp->name = (char *) bdbmalloc2(len + 1, sizeof (char));
	strncpy(papp->name, name, len);
}

void set_pdbels(void * happ, void * hcdbels) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->pdbels = (tSBDBApp *)hcdbels;
}

void set_b_hd_thresh(void * happ) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->b_hd_thresh = true;
}

void set_b_rules(void * happ) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->b_rules = true;
}

void set_b_rec_names(void * happ) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->b_names = true;
}

void set_hd_buckets(void * happ, int num_buckets, int * hd_buckets) {
//	return;
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->num_hd_buckets = num_buckets;
	papp->hd_buckets = (int*)bdballoc(papp->hd_buckets, &(papp->hd_buckets_alloc), sizeof(int), papp->num_hd_buckets);
	memcpy(papp->hd_buckets, hd_buckets, sizeof(int)*papp->num_hd_buckets);
}

void set_cluster_min(void * happ, int cluster_min) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->cluster_min = cluster_min;
}

void clear_db(void * happ) {
//	return;
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->num_db_els = 0;
	papp->num_rec_ptrs = 0;
	papp->num_agents = 1;
}

void add_rec(void * happ, int num_els, char * data) {
//	return;
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
//	printf("add_rec called for %d els. Total %d\n", num_els, papp->num_db_els);
	if (num_els > papp->max_rec_len) {
		papp->max_rec_len = num_els;
		printf("max rec len set to %d for db %s.\n", papp->max_rec_len, papp->name);
	}
	int old_num_els = papp->num_db_els;
	papp->num_db_els += num_els;
	papp->db = (char *) bdballoc(papp->db, &(papp->num_db_els_alloc), sizeof (char)*papp->bitvec_size, papp->num_db_els);
	memcpy(&(papp->db[old_num_els * papp->bitvec_size]), data, num_els * sizeof (char)*papp->bitvec_size);
	papp->rec_ptrs = (int *) bdballoc(papp->rec_ptrs, &(papp->num_rec_ptrs_alloc), sizeof (int), papp->num_rec_ptrs + 1);
	papp->rec_lens = (int*) bdballoc(papp->rec_lens, &(papp->rec_lens_alloc), sizeof (int), papp->num_rec_ptrs + 1);
	papp->rec_lens[papp->num_rec_ptrs] = num_els;
	papp->rec_ptrs[papp->num_rec_ptrs] = old_num_els;
	if (papp->b_hd_thresh) {
		papp->hd_thresh = (int*) bdballoc(	papp->hd_thresh, &(papp->hd_thresh_alloc), sizeof (int), 
											papp->max_rec_len * (papp->num_rec_ptrs + 1));
//		papp->hd_thresh[papp->num_rec_ptrs] = -1;
	}
	if (papp->b_rules) {
		papp->rule_data = (tSRuleRec*) bdballoc(papp->rule_data, &(papp->rule_data_alloc), sizeof (tSRuleRec), papp->num_rec_ptrs + 1);
		memset(&(papp->rule_data[papp->num_rec_ptrs]), 0, sizeof (tSRuleRec));
	}
	if (papp->b_names) {
		papp->rec_names = (char **)bdballoc(papp->rec_names, &(papp->rec_names_alloc), sizeof(char*), papp->num_rec_ptrs + 1);
	}
	if (papp->num_rec_ptrs == 0) {
		papp->agent_mrk_allocs = (int *) bdballoc(papp->agent_mrk_allocs, &(papp->agent_num_allocs_alloc),
				sizeof (int), papp->num_agents);
		memset(papp->agent_mrk_allocs, 0, sizeof (int)*papp->num_agents);
		papp->agent_mrks = (char**) bdballoc(papp->agent_mrks, &(papp->num_agents_alloc), sizeof (char*), papp->num_agents);
		memset(papp->agent_mrks, 0, sizeof (char*)*papp->num_agents);
	}
	for (int iagent = 0; iagent < papp->num_agents; iagent++) {
		papp->agent_mrks[iagent] = (char*) bdballoc(papp->agent_mrks[iagent], &(papp->agent_mrk_allocs[iagent]),
				sizeof (char), papp->num_rec_ptrs + 1);
		// The default for a system with only one agent is that every phrase in the db is know to that 1 agent
		// otherwise, the default is 0
		papp->agent_mrks[iagent][papp->num_rec_ptrs] = ((papp->num_agents == 1) ? 1 : 0);
	}
	papp->hd_buf = (tSDistRec*) bdballoc(papp->hd_buf, &(papp->hd_buf_alloc), sizeof (tSDistRec), papp->num_rec_ptrs+1);
	papp->hd_buf[papp->num_rec_ptrs].idx = papp->num_rec_ptrs;
	papp->hd_el_buf = (int *)bdballoc(papp->hd_el_buf, &(papp->hd_el_buf_alloc), sizeof(int), papp->max_rec_len * (papp->num_rec_ptrs+1));
	papp->num_rec_ptrs++;
	
	//	printf("%s bitvecdb add_rec. Added %d els. db now %d long.\n", papp->name, num_els, papp->num_db_els);
	//	for (int irec=0; irec<papp->num_rec_ptrs; irec++) {
	//		for (int ii = 0; ii<papp->rec_lens[irec]; ii++) {
	//			int iel = papp->rec_ptrs[irec] + ii;
	//			printf("irec: %d, ii: %d, iel: %d. ", irec, ii, iel);
	//			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
	//				printf("%hhd ", papp->db[(iel * papp->bitvec_size) + ibit]);
	//			}
	//			printf("\n");
	//		}
	//	}
}

void change_rec(void * happ, int num_els, char * data, int irec) {
//	return;
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	if (papp->rec_lens[irec] != num_els) {
		printf("Error! bitvecdb change_rec called for irec %d of length %d with new length %d. NO change made!\n",
				irec, papp->rec_lens[irec], num_els);
		return;
	}
	memcpy(&(papp->db[papp->rec_ptrs[irec] * papp->bitvec_size]), data, num_els * sizeof (char)*papp->bitvec_size);
	//	printf("bitvecdb change_rec called for irec %d len %d. pos: %d\n", irec, num_els, papp->rec_ptrs[irec]);
	//	for (int iel=0; iel<papp->num_db_els; iel++) {
	//		printf("iel: %d. ", iel);
	//		for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
	//			printf("%hhd ", papp->db[(iel * papp->bitvec_size) + ibit]);
	//		}
	//		printf("\n");
	//	}
}

void set_rec_name(void * happ, char * name, int irec) {
//	return;
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	if (!papp->b_names) {
		printf("Code error! This db has not been set for record names.\n");
		return;
	}
//	printf("Setting rec %d to name %s.\n", irec, name);
	papp->rec_names[irec] = name;
}

int test_rec_name(void * happ, char * name, int irec) {
	tSBDBApp * papp = (tSBDBApp *) happ;
	if (!papp->b_names) {
		printf("Code error! This db has not been set for record names.\n");
		return 0 ;
	}
	if (strcmp(papp->rec_names[irec], name) != 0) {
		printf("Code error! Name check fails for name %s on rec %d.\n", name, irec );
		return 0;
	}
	return 1;
	
}

void print_db_recs(void * happ, void * hcdbels) {
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	tSBDBApp * pdbels = (tSBDBApp *) hcdbels;
	printf("db has %d recs and els db has %d recs.\n", papp->num_rec_ptrs, pdbels->num_rec_ptrs);
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		printf("irec %d: ", irec);
		for (int iel = 0; iel < papp->rec_lens[irec]; iel++) {
			printf("%s ", get_name_exact(pdbels, 1, &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size])));
		}
		printf("\n");
	}
	
}

char * get_name_exact(tSBDBApp * papp, int qlen, char * qbits) {
//	printf("db has %d recs.\n", papp->num_rec_ptrs);
	int irec_found = -1;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
//		printf("rec %d has name %s.\n", irec, papp->rec_names[irec]);
		if (papp->rec_lens[irec] != qlen) continue;
//		for (int iel = 0; iel < qlen)
		if (memcmp(qbits, &(papp->db[papp->rec_ptrs[irec]*papp->bitvec_size]), qlen*papp->bitvec_size) == 0) {
			printf(" (get_name_exact %d  %s) ", irec, papp->rec_names[irec]);
			irec_found = irec;
			break;
		}
	}
	if (irec_found != -1) {
		return papp->rec_names[irec_found];

	}
	printf("(get_name_exact !rec not found!)");
	return NULL;
}

int get_irec_exact(tSBDBApp * papp, int qlen, char * qbits) {
//	printf("db has %d recs.\n", papp->num_rec_ptrs);
	int irec_found = -1;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
//		printf("rec %d has name %s.\n", irec, papp->rec_names[irec]);
		if (papp->rec_lens[irec] != qlen) continue;
//		for (int iel = 0; iel < qlen)
		if (memcmp(qbits, &(papp->db[papp->rec_ptrs[irec]*papp->bitvec_size]), qlen*papp->bitvec_size) == 0) {
			printf("get_name_exact: found rec %d with name %s.\n", irec, papp->rec_names[irec]);
			irec_found = irec;
		}
	}
	return irec_found;
}


void del_rec(void * happ, int num_els, int irec) {
//	return;
	tSBDBApp * papp = (tSBDBApp *) happ;

	int remove_pos = papp->rec_ptrs[irec];
	char * ptr1 = &(papp->db[remove_pos * papp->bitvec_size]);
	char * ptr2 = &(papp->db[(remove_pos + num_els) * papp->bitvec_size]);
	int els_left = papp->num_db_els - (remove_pos + num_els);
	if (els_left > 0) {
		memcpy(ptr1, ptr2, els_left * papp->bitvec_size * sizeof (char));
		int recs_left = papp->num_rec_ptrs - irec - 1;
		memcpy(&(papp->rec_ptrs[irec]), &(papp->rec_ptrs[irec + 1]), recs_left * sizeof (int));
		memcpy(&(papp->rec_lens[irec]), &(papp->rec_lens[irec + 1]), recs_left * sizeof (int));
		memcpy(&(papp->hd_buf[irec]), &(papp->hd_buf[irec + 1]), recs_left * sizeof (tSDistRec));
		for (int iagent = 0; iagent < papp->num_agents; iagent++) {
			memcpy(&(papp->agent_mrks[iagent][irec]), &(papp->agent_mrks[iagent][irec + 1]), recs_left * sizeof (char));
		}
		for (int ii = 0; ii < recs_left; ii++) {
			int iirec = ii + irec;
			papp->rec_ptrs[iirec] -= num_els;
		}
	}
	papp->num_db_els -= num_els;
	papp->num_rec_ptrs--;
	printf("bitvecdb del_rec. Removed %d els at rec %d pos %d. db now %d long.\n",
			num_els, irec, remove_pos, papp->num_db_els);
	//	for (int iel=0; iel<papp->num_db_els; iel++) {
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		for (int ii = 0; ii < papp->rec_lens[irec]; ii++) {
			int iel = papp->rec_ptrs[irec] + ii;
			printf("irec: %d, ii: %d, iel: %d. ", irec, ii, iel);
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
				printf("%hhd ", papp->db[(iel * papp->bitvec_size) + ibit]);
			}
			printf("\n");
		}
	}

}

int add_agent(void * happ) {
	tSBDBApp * papp = (tSBDBApp *) happ;
	if (papp->num_rec_ptrs == 0) {
		papp->num_agents++;
		return papp->num_agents;
	}

	papp->agent_mrk_allocs = (int *) bdballoc(papp->agent_mrk_allocs, &(papp->agent_num_allocs_alloc),
			sizeof (int), papp->num_agents + 1);
	papp->agent_mrk_allocs[papp->num_agents] = 0;
	papp->agent_mrks = (char**) bdballoc(papp->agent_mrks, &(papp->num_agents_alloc), sizeof (char*), papp->num_agents + 1);
	papp->agent_mrks[papp->num_agents] = NULL;
	papp->agent_mrks[papp->num_agents] = (char*) bdballoc(papp->agent_mrks[papp->num_agents],
			&(papp->agent_mrk_allocs[papp->num_agents]),
			sizeof (char*), papp->num_rec_ptrs);
	memset(papp->agent_mrks[papp->num_agents], 0, sizeof (char)*papp->num_rec_ptrs);
	papp->num_agents++;
	return papp->num_agents;
}

void agent_change_rec(void * happ, int iagent, int irec, int badd) {
//	return;
	if (happ == NULL) return;
	tSBDBApp * papp = (tSBDBApp *) happ;
	papp->agent_mrks[iagent][irec] = (badd == 1);
	//	printf("%s bitvecdb agent_change_rec. Changed rec %d for iagent %d to %s.\n",
	//			papp->name, irec, iagent, (papp->agent_mrks[iagent][irec] ? "true" : "false"));
}

int dist_cmp(const void * r1, const void * r2) {
	const tSDistRec * d1 = r1;
	const tSDistRec * d2 = r2;
	if ((d1->dist < 0) && (d2->dist < 0)) return 0;
	if (d1->dist < 0) return 1;
	if (d2->dist < 0) return -1;
	if (d1->dist < d2->dist) return -1;
	if (d1->dist > d2->dist) return 1;
	if (d1->dist == d2->dist) return 0;
	return 0;
}

int get_closest_recs(void * happ, int k, int * idxs_ret, int * hds_ret, char * obits,
		int num_els, char * qdata, int iskip, int delta) {
	tSBDBApp * papp = (tSBDBApp *) happ;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] == (num_els - delta))
			papp->hd_buf[irec].dist = 0;
		else
			papp->hd_buf[irec].dist = -1;
	}

	for (int qpos = 0; qpos < num_els; qpos++) { // qpos == pos in query phrase
		if (qpos >= iskip && qpos <= (iskip + delta)) continue;
		int iel = ((qpos < iskip) ? qpos : qpos - delta);
		for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
			if (papp->rec_lens[irec] != (num_els - delta)) continue;
			char * prec = &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size]);
			char * qrec = &(qdata[qpos * papp->bitvec_size]);
			//			printf("qpos: %d iel: %d irec %d: ptr %d. ", qpos, iel, irec, papp->rec_ptrs[irec]);
			int hd = 0;
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
				//				printf("%hhd ", prec[ibit]);
				if (prec[ibit] != qrec[ibit]) {
					hd++;
				}
			}
			//			printf("\n");
			papp->hd_buf[irec].dist += (float) hd;
		}
	}
	//	printf("hds: ");
	//	for (int i=0; i<papp->num_rec_ptrs; i++) {
	//		printf("%d:%d ", papp->hd_buf[i].idx, papp->hd_buf[i].dist);
	//	}
	//	printf("\n");
	qsort(papp->hd_buf, papp->num_rec_ptrs, sizeof (tSDistRec), dist_cmp);

	int num_ret = 0;
	for (int iret = 0; iret < k; iret++) {
		if ((iret >= k) || (iret >= papp->num_rec_ptrs)) break;
		tSDistRec * pdr = &(papp->hd_buf[iret]);
		if (pdr->dist < 0) break;
		idxs_ret[iret] = pdr->idx;
		hds_ret[iret] = pdr->dist;
		memcpy(&(obits[iret * papp->bitvec_size]),
				&(papp->db[(papp->rec_ptrs[pdr->idx] + iskip) * papp->bitvec_size]),
				papp->bitvec_size * sizeof (char));
		num_ret++;
	}

	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		papp->hd_buf[irec].idx = irec;
	}
	return num_ret;
}

int init_num_left_buf(void * hcapp, int plen) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	papp->num_left_buf = (bool*) bdballoc(papp->num_left_buf, &(papp->num_left_buf_alloc), sizeof (bool), papp->num_rec_ptrs);
	int num_left = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] == plen) {
			papp->num_left_buf[irec] = true;
			num_left++;
		} else {
			papp->num_left_buf[irec] = false;
		}
	}
	return num_left;
}

int calc_hd_bucket(tSBDBApp * papp, int hd) {
//	printf("calc_hd_bucket for hd %d ", hd);
	for (int ibucket=0; ibucket<papp->num_hd_buckets; ibucket++) {
		if (hd <= papp->hd_buckets[ibucket]) {
//			printf(".. is %d.\n", ibucket);
			return ibucket;
		}
	}
//	printf(".. Unexpected is %d.\n", papp->num_hd_buckets);
	return papp->num_hd_buckets;
}

void fill_hd_buf(tSBDBApp * papp, int iseed, int plen) {
//	printf("fill_hd_buf called for seed %d. \n", iseed);
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] == plen)
			papp->hd_buf[irec].dist = 0;
		else
			papp->hd_buf[irec].dist = -1;
	}

	for (int qpos = 0; qpos < plen; qpos++) { // qpos == pos in query phrase
		char * qrec = &(papp->db[(papp->rec_ptrs[iseed] + qpos) * papp->bitvec_size]);
//		printf("fill_hd_buf calculating for pos %d. word %s\n", qpos,  get_name_exact(papp->pdbels, 1, qrec));
		for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
			if (papp->rec_lens[irec] != plen) continue;
			char * prec = &(papp->db[(papp->rec_ptrs[irec] + qpos) * papp->bitvec_size]);
//			printf("fill_hd_buf calculating for irec %d. word %s\n", irec, get_name_exact(papp->pdbels, 1, prec));
			//			printf("qpos: %d iel: %d irec %d: ptr %d. ", qpos, iel, irec, papp->rec_ptrs[irec]);
			int hd = 0;
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
				//				printf("%hhd ", prec[ibit]);
				if (prec[ibit] != qrec[ibit]) {
					hd++;
				}
			}
			papp->hd_el_buf[(irec*papp->max_rec_len) + qpos] = calc_hd_bucket(papp, hd);
			//			printf("\n");
			papp->hd_buf[irec].dist += (float) hd;
		}
	}
}

int get_pick_map_recs(tSBDBApp * papp, int plen, int * pick_map, int * pdist_sum) {
	*pdist_sum = 0;
	int num_found = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] != plen) continue;
		bool bfound = true;
//		printf("irec %d: ", irec);
		int dist = 0;
		for (int ip2=0; ip2<plen; ip2++) {
//			printf("%d: el buf %d vs. pick map %d. ", ip2, papp->hd_el_buf[(irec*papp->max_rec_len) + ip2], pick_map[ip2]);
			int el_dist = papp->hd_el_buf[(irec*papp->max_rec_len) + ip2];
			if (el_dist > pick_map[ip2]) {
				bfound = false;
				break;
			}
			if (!bfound) break;
			dist += el_dist;
		}
		if (bfound) {
			if (!papp->num_left_buf[irec]) {
//				printf("\nget_pick_map_recs: Error! collision with num_lef_buf. \n");
				break;
			}
			else {
				papp->num_left_buf[irec] = false;
				num_found++;
				*pdist_sum += dist;
//						printf("... valid record. \n");
			}
		}
	}
	return num_found;
}

int pick_thresh_map(tSBDBApp * papp, int plen, int max_picks, int * pick_map, int * num_picks_ret) {
	bool pick_map_avoid[plen];
	for (int ip=0; ip<plen; ip++) {
		pick_map[ip] = 0;
	}
//	{
//		*num_picks_ret = max_picks;
//		return 11;
//	}
//	for (int ibucket=0; ibucket<papp->num_hd_buckets; ibucket++) {
//		printf("pick_thresh_map: bucket %d is %d.\n", ibucket, papp->hd_buckets[ibucket]);
//	}
	int max_num_found = 0;
	for (int ipick = 0; ipick < max_picks; ipick++) {
//		printf("pick_thresh_map: pick num %d of %d. \n", ipick, max_picks);
		int ip_max = -1;
		int num_to_avoid = 0;
		for (int ip=0; ip<plen; ip++) {
//			printf("pick_thresh_map: Incrementing pick map %d. \n", ip);
			pick_map_avoid[ip] = false;
			pick_map[ip]++;
			int num_found = 0;
			for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
				if (papp->rec_lens[irec] != plen) continue;
				bool bfound = true;
//				printf("irec %d: ", irec);
				for (int ip2=0; ip2<plen; ip2++) {
//					printf("%d: el buf %d vs. pick map %d. ", ip2, papp->hd_el_buf[(irec*papp->max_rec_len) + ip2], pick_map[ip2]);
					if (papp->hd_el_buf[(irec*papp->max_rec_len) + ip2] > pick_map[ip2]) {
						bfound = false;
						break;
					}
					if (!bfound) break;
				}
				if (bfound) {
					if (!papp->num_left_buf[irec]) {
//						printf("collision with num_lef_buf. \n");
						pick_map_avoid[ip] = true;
						num_to_avoid++;
						break;
					}
					else {
						num_found++;
//						printf("... valid record. \n");
					}
				}
				else {
//					printf("... record invalid!\n");
				}
			}
			pick_map[ip]--;
			if (num_found > max_num_found) {
				ip_max = ip;
				max_num_found = num_found;
			}
		} // loop over els (plen)
		if (ip_max == -1) {
			if (num_to_avoid == plen) {
				printf("pick_thresh_map: No further pick progress possible without hitting non available.\n");
				*num_picks_ret = ipick;
				return max_num_found;
			}
			while (true) {
				ip_max = rand() % plen;
				if (!pick_map_avoid[ip_max]) {
					break;
				}
				printf("selected pick %d through random process.\n", ip_max);
			}
		}
		pick_map[ip_max]++;
//		printf(	"pick_thresh_map: pick num %d, ip_max %d raising pick to %d to include %d recs.\n", 
//				ipick, ip_max, pick_map[ip_max], max_num_found);
	} // loop over picks till max_pick
	*num_picks_ret = max_picks;
	return max_num_found;
}

int get_cluster_seed(	void * hcapp, char * cent_ret, float * hd_avg_ret, 
						int * hd_thresh_ret, int plen, int hd_thresh) { // if CLUSTER_BY_EL hd_thresh_ret must be allocated plen ints
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	printf("papp->cluster_min = %d\n", papp->cluster_min);
	float best_score = 0;
	int ibest_score = -1;
	int best_thresh = -1;
	int best_pick_map[plen];
	for (int iseed = 0; iseed < papp->num_rec_ptrs; iseed++) {
//		printf("get_cluster_seed: testing iseed %d len %d, left %s.\n", iseed, papp->rec_lens[iseed], (papp->num_left_buf[iseed]? "True" : "False"));
		if (papp->rec_lens[iseed] != plen || !papp->num_left_buf[iseed]) continue;
		fill_hd_buf(papp, iseed, plen);
		if (CLUSTER_BY_EL) {
			for (int thresh = 0; thresh <= hd_thresh; thresh++) {
//				printf("get_cluster_seed: thresh at %d.\n", thresh);
				int pick_map[plen];
				memset(pick_map, 0, sizeof(int)*plen);
				int num_picks;
				int num_found = pick_thresh_map(papp, plen, thresh, pick_map, &num_picks);
				if (num_found < papp->cluster_min || num_picks < 1) continue;
				float score = (float)num_found / num_picks;
				if (score > best_score) {
					best_score = score;
					ibest_score = iseed;
					best_thresh = num_picks;
					memcpy(best_pick_map, pick_map, sizeof(int)*plen);
					printf("get_cluster_seed. best so far at score %f.\n", score);
				}			
			} // loop over different values of thresh
		}
		/*
		else {
			bool b_seed_scored = false;
			for (int thresh = hd_thresh * plen; thresh >= 0; thresh -= plen) {
				bool b_overlap = false;
				int dist_sum = 0;
				int num_hit = 0;
				for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
					int dist = papp->hd_buf[irec].dist;
					if (dist >= 0 && dist <= thresh) {
						if (!papp->num_left_buf[irec]) {
							//						printf("for thresh %d, iseed %d overlapped rec at %d\n", thresh, iseed, irec);
							b_overlap = true;
							break;
						}
						dist_sum += dist;
						num_hit++;
					}
				}
				if (b_overlap) continue;
				if (num_hit > 0) {
					float avg_dist = (float) dist_sum / (plen * num_hit);
					float seed_score = ((papp->bitvec_size - avg_dist) / papp->bitvec_size) * num_hit;
					//				printf(	"for thresh %d, iseed %d achieved num_hit %d with dist_sum %d, seed_score %f\n", 
					//						thresh, iseed, num_hit, dist_sum, seed_score);
					if (seed_score > best_score) {
						best_score = seed_score;
						ibest_score = iseed;
						best_thresh = thresh;
						//					printf("iseed %d best so far.\n", iseed);
					}
					b_seed_scored = true;
				}
				if (b_seed_scored) break;
			} // loop over different threshes
		} // end else CLUSTER_BY_EL
		 */
	} // end loop over recs (iseed)

//	{ // dummy ret
//		for (int iel = 0; iel < plen; iel++) {
//			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
//				cent_ret[(iel * papp->bitvec_size) + ibit] = 0;
//			}
//		}
//		*hd_avg_ret = 0.0;
//		return 0;
//	}

	*hd_avg_ret = 0.0;
	if (ibest_score != -1) {
		int num_hit = 0;
		int dist_sum = 0;
		fill_hd_buf(papp, ibest_score, plen);
		if (CLUSTER_BY_EL) {
			num_hit =  get_pick_map_recs(papp, plen, best_pick_map, &dist_sum);
			*hd_avg_ret = (float) dist_sum / num_hit;
			for (int iel = 0; iel < plen; iel++) {
				hd_thresh_ret[iel] = papp->hd_buckets[best_pick_map[iel]];
			}
		}
		else {
			for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
				int dist = papp->hd_buf[irec].dist;
				if (dist >= 0 && dist <= best_thresh) {
					if (!papp->num_left_buf[irec]) {
						printf("Error! Unexpected overlap with rec %d for seed %d that was declared the winner\n", irec, ibest_score);
					}
					papp->num_left_buf[irec] = false;
					dist_sum += dist;
					num_hit++;
				}
			}
			*hd_avg_ret = (float) dist_sum / (plen * num_hit);
			*hd_thresh_ret = best_thresh;
			for (int iel = 1; iel < plen; iel++) {
				hd_thresh_ret[iel] = 0;
			}
		}

		for (int iel = 0; iel < plen; iel++) {
			char * prec = &(papp->db[(papp->rec_ptrs[ibest_score] + iel) * papp->bitvec_size]);
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
				cent_ret[(iel * papp->bitvec_size) + ibit] = prec[ibit];
			}
		}

	}

	int num_left = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] != plen || !papp->num_left_buf[irec]) continue;
		num_left++;
	}

	return num_left;
}

int get_num_plen(void * hcapp, int plen) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	int n = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] == plen)
			n++;
	}
	return n;
}

int get_plen_irecs(void * hcapp, int* ret_arr, int plen, int iagent) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	int num_found = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (!papp->agent_mrks[iagent][irec]) continue;
		if (papp->rec_lens[irec] == plen) {
			ret_arr[num_found] = irec;
			num_found++;
		}
	}
	return num_found;
}

int get_cluster(void * hcapp, int * members_ret, int num_ret, char * cent,
		int plen, int * hd_thresh) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;

	printf("get_cluster: num_ret: %d, plen: %d, hd_thresh0 %d. num recs: %d. db size %d\n", 
			num_ret, plen, hd_thresh[0], papp->num_rec_ptrs, papp->num_db_els);
	int num_found = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] != plen) continue;
		int hd_tot = 0;
		bool bfound = true;
		for (int iel = 0; iel < plen; iel++) { // qpos == pos ind query phrase
			int hd = 0;
			char * prec = &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size]);
			//			char * qrec = &(papp->db[(papp->rec_ptrs[iseed] + qpos)*papp->bitvec_size]);
			//			printf("iel: %d irec %d: ptr %d. \n", iel, irec, papp->rec_ptrs[irec]);
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
				//				printf("%hhd ", prec[ibit]);
				if (prec[ibit] != cent[(iel * papp->bitvec_size) + ibit]) {
					hd++;
				}
			}
			hd_tot += hd;
			if (CLUSTER_BY_EL) {
				printf("irec: %d iel %d el hd: %d vs el thresh %d.\n", irec, iel, hd, hd_thresh[iel]);
				if (hd > hd_thresh[iel]) {
					bfound = false;
					break;
				}
			}
			//			printf("\n");
			//			papp->hd_buf[irec].dist += (float)hd;
		}
		if ((CLUSTER_BY_EL && bfound) || hd_tot <= hd_thresh[0]) {
			//			printf("Found cluster member %d at %d.\n", num_found, irec);
			members_ret[num_found] = irec;
			num_found++;
		}
	}
	printf("%d recs found.\n", num_found);
	return num_found;
}

bool test_rec_for_eid(tSBDBApp * papp, int iagent, int irec, int iel_at, char * qbits) {
	if (!papp->agent_mrks[iagent][irec]) return false;
	bool bfound = false;
	for (int iel = 0; iel < papp->rec_lens[irec]; iel++) { // qpos == pos ind query phrase
		if (iel_at != -1 && iel_at != iel) continue;
		char * prec = &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size]);
		if (memcmp(prec, qbits, papp->bitvec_size) == 0) {
			bfound = true;
			break;
		}
	}
	return bfound;
}

int get_irecs_with_eid(void* hcapp, int * ret_arr, int iagent, int iel_at, char * qbits) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	int num_found = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (test_rec_for_eid(papp, iagent, irec, iel_at, qbits)) {
			ret_arr[num_found] = irec;
			num_found++;
		}
	}

	return num_found;
}

int get_next_irec(tSBDBApp * papp, int istart, int iagent, int qlen, char ** match_pat, int * match_hd) {
	for (int irec = istart+1; irec < papp->num_rec_ptrs; irec++) {
		if (!papp->agent_mrks[iagent][irec]) continue;
		if (papp->rec_lens[irec] != qlen) continue;
		bool bfound = true;
		for (int iel = 0; iel < qlen; iel++) {
			char * qbits = match_pat[iel];
			char * pbits = &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size]);
			int hd = 0; 
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
				if (qbits[ibit] != pbits[ibit]) hd++;
			}
			if (hd > match_hd[iel]) {
				bfound = false;
				break;
			}
		}
		if (bfound) {
			return irec;
		}
	}
	return -1;
}

char * get_el_in_rec(tSBDBApp * papp, int irec, int iel) {
	return &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size]);
}

int get_irecs_with_eid_by_list(void* hcapp, int * ret_arr, int iagent, int iel_at, int * cand_arr,
		int num_cands, char * qbits) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	int num_found = 0;
	for (int icand = 0; icand < num_cands; icand++) {
		int irec = cand_arr[icand];
		if (test_rec_for_eid(papp, iagent, irec, iel_at, qbits)) {
			ret_arr[num_found] = irec;
			num_found++;
		}
	}
	return num_found;
}

// The assumption is that papp->max_rec_len has already been set at the highest it will reach
void set_hd_thresh(void * hcapp, int irec, int * hd_thresh, int plen) { // set plen to 1 for bperel regardless of real plen
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	memcpy(&(papp->hd_thresh[irec*papp->max_rec_len]), hd_thresh, sizeof(int)*plen);
}

bool test_for_thresh(tSBDBApp * papp, int plen, int * ext_thresh, int irec, char * qrec, bool bext, bool bperel) {
	int hd_tot = 0;
	if (papp->rec_lens[irec] != plen) return false;
	bool bfound = true;
	for (int iel = 0; iel < papp->rec_lens[irec]; iel++) { // qpos == pos ind query phrase
		char * prec = &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size]);
		char * qel = &(qrec[iel * papp->bitvec_size]);
		//			printf("iel %d db vs. q:", iel);
		int hd = 0;
		for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
			//				printf(" %hhdvs.%hhd", prec[ibit], qel[ibit]);
			if (prec[ibit] != qel[ibit]) hd++;
		}
		if (bperel) {
			int hd_thresh;
			if (bext) hd_thresh = ext_thresh[iel];
			else hd_thresh = papp->hd_thresh[(irec*papp->max_rec_len)+iel];
			if (hd > hd_thresh) {
				bfound = false;
				break;
			}
		}
		hd_tot += hd;
		//			printf("\n");
	}
	if (!bfound) {
		return false;
	}
	//		printf("get_thresh_recs: irec %d hd %d vs. thresh %d.\n", irec, hd, papp->hd_thresh[irec]);
	if (!bperel) {
		if (bext) {
			if (hd_tot > ext_thresh[0]) return false;
		}
		else {
			if (hd_tot > papp->hd_thresh[irec*papp->max_rec_len]) return false;
		}
	}
	return true;
}

//if ext_thresh is -1, it means the thresh, is the hd_thresh of the rec itself
//otherwise it is the thresh of closeness to use.

int get_thresh_recs(void * hcapp, int * ret_arr, int plen, int * ext_thresh, char * qrec, int bext, int bperel) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	int num_found = 0;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (test_for_thresh(papp, plen, ext_thresh, irec, qrec, bext == 1, bperel == 1)) {
			if (ret_arr != NULL)
				ret_arr[num_found] = irec;
			num_found++;
		}
	}
	return num_found;
}

// not ext_thresh is not an ext_rule. It is the outside requiring a thresh as oposed to the hd requirement of the db rec itself
int get_thresh_recs_by_list(void * hcapp, int * ret_arr, int plen, int * ext_thresh, int bext, int bperel,
		int * cand_arr, int num_cands, char * qrec) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	int num_found = 0;
	for (int icand = 0; icand < num_cands; icand++) {
		int irec = cand_arr[icand];
		if (test_for_thresh(papp, plen, ext_thresh, irec, qrec, bext == 1, bperel == 1)) {
			if (ret_arr != NULL)
				ret_arr[num_found] = irec;
			num_found++;
		}
	}
	return num_found;
}

bool test_for_el_hd(tSBDBApp * papp, int iel, int hd_req, int irec, char * qrec) {
	char * prec = &(papp->db[(papp->rec_ptrs[irec] + iel) * papp->bitvec_size]);
	printf("iel %d db vs. q:", iel);
	int hd = 0;
	for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
		printf(" %hhdvs.%hhd", prec[ibit], qrec[ibit]);
		if (prec[ibit] != qrec[ibit]) hd++;
	}
	printf("\n");
	printf("get_thresh_recs: irec %d hd %d vs. thresh %d.\n", irec, hd, hd_req);
	if (hd <= hd_req) return true;
	return false;
}


int get_el_hd_recs_by_list(	void * hcapp, int * irec_arr, int * cand_arr, int num_cands, int iel, int hd, char * qrec) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	int num_found = 0;
	for (int icand = 0; icand < num_cands; icand++) {
		int irec = cand_arr[icand];
		if (test_for_el_hd(papp, iel, hd, irec, qrec)) {
			if (irec_arr != NULL)
				irec_arr[num_found] = irec;
			num_found++;
		}
	}
	return num_found;
	
}

void set_rule_data(	void * hcapp, int irec, int num_cents, int * cent_offsets, int * cent_hds, int num_var_defs, 
					int * var_defs, int bresult, int cid, int rid, int b_hd_per_el) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	tSRuleRec * prule = (tSRuleRec *)&(papp->rule_data[irec]);
	int tot_num_els = papp->rec_lens[irec];
	prule->b_hd_per_el = (bool)(b_hd_per_el != 0);
	int num_hds = (prule->b_hd_per_el ? tot_num_els : prule->num_phrases);
	prule->num_phrases = num_cents;
	prule->phrase_offsets = (int*) bdballoc(prule->phrase_offsets, &(prule->phrase_offsets_alloc), sizeof (int), prule->num_phrases);
	prule->phrase_lens = (int*) bdballoc(prule->phrase_lens, &(prule->phrase_lens_alloc), sizeof (int), prule->num_phrases);
	prule->phrase_hds = (int*) bdballoc(prule->phrase_hds, &(prule->phrase_hds_alloc), sizeof (int), num_hds);
	memcpy(prule->phrase_offsets, cent_offsets, sizeof (int)*prule->num_phrases);
	prule->b_result = bresult;
	printf("set_rule_data called for irec %d.\n", irec);
	for (int icent = 0; icent < prule->num_phrases - 1; icent++) {
		prule->phrase_lens[icent] = prule->phrase_offsets[icent + 1] - prule->phrase_offsets[icent];
		printf("set_rule_data: cent %d, len = %d\n", icent, prule->phrase_lens[icent]);
	}
	prule->phrase_lens[prule->num_phrases - 1] = papp->rec_lens[irec] - prule->phrase_offsets[prule->num_phrases - 1];
	printf("set_rule_data: Last cent, len = %d\n", prule->phrase_lens[prule->num_phrases - 1]);
	memcpy(prule->phrase_hds, cent_hds, sizeof (int)*num_hds);
	int max_phrase_len = -1; 
	for (int iphrase = 0; iphrase < prule->num_phrases; iphrase++) {
		if (prule->phrase_lens[iphrase] > max_phrase_len) {
			max_phrase_len = prule->phrase_lens[iphrase];
		}
	}
	create_pair_dict(&(prule->d_var_opts), prule->num_phrases, max_phrase_len);
	prule->num_var_defs = num_var_defs;
	prule->var_defs = (int*) bdballoc(prule->var_defs, &(prule->var_defs_alloc), sizeof (int)*VAR_DEF_SIZE, prule->num_var_defs);
	memcpy(prule->var_defs, var_defs, sizeof (int)*VAR_DEF_SIZE * prule->num_var_defs);
//	for (int ivar = 0; ivar < prule->num_var_defs; ivar++) {
//		prule->var_tbl[ivar].quad = (int *)bdballoc(prule->var_tbl[ivar].quad, &(prule->var_tbl[ivar].quad_alloc), 
//													sizeof(int), VAR_DEF_SIZE);
////		memcpy(prule->var_tbl[ivar].quad, var_defs)
//	}
//	prule->var_tbl = (tSVarData *)bdballoc(prule->var_tbl, &(prule->var_tbl_alloc), sizeof(tSVarData), prule->num_var_defs);
	int ivar = 0;
	for (int iphrase = 0; iphrase < prule->num_phrases; iphrase++) {
		for (int iel = 0; iel < prule->phrase_lens[iphrase]; iel++) {
			bool bfound = false;
			for (int ivardef = 0; ivardef < prule->num_var_defs; ivardef++) {
				int * var = &(var_defs[ivardef*VAR_DEF_SIZE]);
				if (var[2] == iphrase && var[3] == iel) {
					bfound = true;
					int isrc = pair_dict_get(&(prule->d_var_opts), var[0], var[1]);
					if (isrc == -1) {
						printf("Rule Error! (Probably in the definition) Rule refers to source later than intself.\n");
						exit(1);
					}
					prule->var_tbl[isrc].locs = (intpair *)bdballoc(prule->var_tbl[isrc].locs, &(prule->var_tbl[isrc].locs_alloc), 
																	sizeof(intpair), prule->var_tbl[isrc].num_locs+1);
					prule->var_tbl[isrc].locs[prule->var_tbl[isrc].num_locs][0] = iphrase;
					prule->var_tbl[isrc].locs[prule->var_tbl[isrc].num_locs][1] = iel;
					prule->var_tbl[isrc].num_locs++;
					pair_dict_set(&(prule->d_var_opts), iphrase, iel, isrc);
					break;
				}
			}
			if (!bfound) {
				prule->var_tbl = (tSVarData *)bdballoc(prule->var_tbl, &(prule->var_tbl_alloc), sizeof(tSVarData), ivar+1);
				prule->var_tbl[ivar].locs = (intpair *)bdballoc(prule->var_tbl[ivar].locs, &(prule->var_tbl[ivar].locs_alloc), 
																sizeof(intpair), 1);
				prule->var_tbl[ivar].num_locs = 1;
				prule->var_tbl[ivar].locs[0][0] = iphrase;
				prule->var_tbl[ivar].locs[0][1] = iel;
				pair_dict_set(&(prule->d_var_opts), iphrase, iel, ivar);
				int i_orig_pos = cent_offsets[iphrase]+iel;
				prule->var_tbl[ivar].hd_thresh = cent_hds[i_orig_pos];
//				if (cent_hds[i_orig_pos] == 0) {
					prule->var_tbl[ivar].src_pat_el = papp->rec_ptrs[irec] + i_orig_pos; // &(papp->db[(papp->rec_ptrs[irec] + i_orig_pos) * papp->bitvec_size]);
//				}
				ivar++;
			}
		}
	}
	prule->num_vars = ivar;
	printf("printing rule var tbl for rule %d. %d vars\n", irec, prule->num_vars);
	for (int ivar = 0; ivar < prule->num_vars; ivar++) {
		tSVarData * pvar = &(prule->var_tbl[ivar]);
		char * src_val = get_name_exact(papp->pdbels, 1, &(papp->db[pvar->src_pat_el*papp->bitvec_size]));
		printf(	"var %d with %d locs. val pos: %d, val: \'%s\', hd: %d\n", ivar, pvar->num_locs, 
				pvar->src_pat_el, src_val, pvar->hd_thresh);
		for (int iloc = 0; iloc < pvar->num_locs; iloc++) {
			printf("%d: %d %d.\n", iloc, pvar->locs[iloc][0], pvar->locs[iloc][1]);
		}
	}
	prule->cid = cid;
	prule->rid = rid;
	return;
}

/*
void set_rule_el_data(	void * hcapp, int irec, int num_cents, int * cent_offsets, int * el_hds, int num_var_defs, 
						int * var_defs, int bresult, int cid, int rid) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	tSRuleRec * prule = (tSRuleRec *)&(papp->rule_data[irec]);
	prule->num_phrases = num_cents;
	prule->phrase_offsets = (int*) bdballoc(prule->phrase_offsets, &(prule->phrase_offsets_alloc), sizeof (int), prule->num_phrases);
	prule->phrase_lens = (int*) bdballoc(prule->phrase_lens, &(prule->phrase_lens_alloc), sizeof (int), prule->num_phrases);
	prule->el_hds = (int*) bdballoc(prule->el_hds, &(prule->el_hds_alloc), sizeof (int), papp->rec_lens[irec]);
	memcpy(prule->phrase_offsets, cent_offsets, sizeof (int)*prule->num_phrases);
	prule->b_hd_per_el = true;
	prule->b_result = bresult;
	printf("set_rule_el_data called for irec %d.\n", irec);
	for (int icent = 0; icent < prule->num_phrases - 1; icent++) {
		prule->phrase_lens[icent] = prule->phrase_offsets[icent + 1] - prule->phrase_offsets[icent];
		printf("set_rule_data: cent %d, len = %d\n", icent, prule->phrase_lens[icent]);
	}
	prule->phrase_lens[prule->num_phrases - 1] = papp->rec_lens[irec] - prule->phrase_offsets[prule->num_phrases - 1];
	printf("set_rule_data: Last cent, len = %d\n", prule->phrase_lens[prule->num_phrases - 1]);
	memcpy(prule->el_hds, el_hds, sizeof(int)*papp->rec_lens[irec]);
	prule->num_var_defs = num_var_defs;
	prule->var_defs = (int*) bdballoc(prule->var_defs, &(prule->var_defs_alloc), sizeof (int)*VAR_DEF_SIZE, prule->num_var_defs);
	memcpy(prule->var_defs, var_defs, sizeof (int)*VAR_DEF_SIZE * prule->num_var_defs);
	prule->cid = cid;
	prule->rid = rid;
	return;
}
*/
// meant for use by one db (c code) getting records from another db. Usually from the bdb_all where each record is another rperm

int get_rec_len(tSBDBApp * pdb, int irec) {
	printf("get_rec_len get rec of len %d.\n", pdb->rec_lens[irec]);
	return pdb->rec_lens[irec];
}

char * get_rec(tSBDBApp * pdb, int irec) {
	return &(pdb->db[pdb->rec_ptrs[irec] * pdb->bitvec_size]);
}

int find_matching_rules(void * hcapp, int * ret_arr, int * ret_rperms,
						void * hcdb, int num_srcs, int * src_rperms) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	tSBDBApp * pdb = (tSBDBApp *) hcdb;
	int num_found = 0;
	for (int isrc = 0; isrc < num_srcs; isrc++) {
		int qlen = get_rec_len(pdb, src_rperms[isrc]);
		//		papp->rec_buf = (char*)bdballoc(papp->rec_buf, &(papp->rec_buf_alloc), sizeof(char)*papp->bitvec_size, qlen);
		//		memcpy(papp->rec_buf, get_rec(pdb, src_rperms[isrc]), qlen*sizeof(char)*papp->bitvec_size);
		char * pdbrec[1];
		int icent = 0;
		pdbrec[icent] = get_rec(pdb, src_rperms[isrc]);
		printf("find_matching_rules: finding for rperm %d, found so far %d.\n", src_rperms[isrc], num_found);
		for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
			tSRuleRec * prule = &(papp->rule_data[irec]);
			bool b_rule_matched = true;
			int num_var_defs = prule->num_var_defs;
			int * pvar_defs[num_var_defs];
			for (int ivar = 0; ivar < num_var_defs; ivar++) {
				pvar_defs[ivar] = &(prule->var_defs[ivar * 4]);
			}
			int hd = 0;
			if (qlen != papp->rule_data[irec].phrase_lens[icent]) continue;
			printf("find_matching_rules: searching cand %d.\n", irec);
			int off = papp->rec_ptrs[irec] + papp->rule_data[irec].phrase_offsets[icent];
			for (int iel = 0; iel < qlen; iel++) { // qpos == pos ind query phrase
				char * qel = &(pdbrec[icent][iel * papp->bitvec_size]);
				int hd_el = 0; bool b_el_var = false;
				for (int ivar = 0; ivar < num_var_defs; ivar++) {
					if ((icent == pvar_defs[ivar][2]) && (iel == pvar_defs[ivar][3])) {
						b_el_var = true;
						printf("Checking for var def %d that iel %d,%d == iel %d,%d.\n",
								ivar, icent, iel, pvar_defs[ivar][0], pvar_defs[ivar][1]);
						char * qvar = &(pdbrec[pvar_defs[ivar][0]][pvar_defs[ivar][1] * papp->bitvec_size]);
						if (memcmp(qel, qvar, sizeof (char)*papp->bitvec_size) != 0) {
							printf("find_matching_rules fails var match!\n");
							b_rule_matched = false;
							break;
						}
					}
				}
				if (!b_rule_matched) break;
				char * pel = &(papp->db[(off + iel) * papp->bitvec_size]);
//				printf("iel %d db vs. qel %d:", iel, iel);
				for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
//					printf(" %hhdvs.%hhd", pel[ibit], qel[ibit]);
					if (pel[ibit] != qel[ibit]) hd_el++;
				}
				if (prule->b_hd_per_el && !b_el_var)  {
					printf("Checking per el hd for iphrase %d iel %d.\n",icent, iel);
					if (hd_el > prule->el_hds[prule->phrase_offsets[icent]+iel]) {
						printf("hd_el test failed because %d > %d.\n", hd_el, prule->el_hds[prule->phrase_offsets[icent]+iel]);
						b_rule_matched = false;
						break;
					}
				}
				hd += hd_el;
//				printf("\n");
			}
			if (!b_rule_matched) continue;
			if (prule->b_hd_per_el) 
				printf("find_matching_rules: irec %d el_per_hd rule passed all tests.\n", irec);
			else
				printf("find_matching_rules: irec %d hd %d vs. thresh %d.\n", irec, hd, papp->rule_data[irec].phrase_hds[icent]);
			if (prule->b_hd_per_el || hd <= papp->rule_data[irec].phrase_hds[icent]) {
				if (ret_arr != NULL) {
					ret_arr[num_found] = irec;
					ret_rperms[num_found] = src_rperms[isrc];
				}
				num_found++;
			}

		}
	}

	return num_found;
}

void find_result_matching_rules_opt(tSBDBApp * papp, tSBDBApp * pdb, tSBDBApp * pdbels, int irec, int qlen, 
									int * pnum_found, char * pdbrec, int * ret_arr, 
									int * ret_num_vars, int * ret_rperms,
									int src_rperm, int num_cats, int * cat_arr, int num_rids, int * rid_arr,
									int * iel_ret, int * ivar_ret,int * src_iphrase_ret, int * src_iel_ret, int num_rets) {
	tSRuleRec * prule = &(papp->rule_data[irec]);
	if (!prule->b_result)  {
		printf("rejecting rule %d because has no result.\n", irec);
		return;
	}
	int iphrase = prule->num_phrases-1;
//	int result_off = prule->phrase_offsets[iphrase];
	int result_len = prule->phrase_lens[iphrase];
	if (qlen != result_len) {
		printf("rejecting rule %d because result len is %d but rule result len is %d.\n", irec, qlen, result_len);
		return;
	}
	if (num_cats > 0) {
		bool b_in_cat = false;
		for (int icid = 0; icid < num_cats; icid++) {
			if (cat_arr[icid] == prule->cid) {
				b_in_cat = true;
				break;
			}
		}
		if (!b_in_cat) {
			printf("rejecting rule %d because cid %d not in requested list.\n", irec, prule->cid);
			return;
		}
	}
	if (num_rids > 0) {
		bool b_in_rids = false;
		for (int irid = 0; irid < num_rids; irid++) {
			if (rid_arr[irid] == prule->rid) {
				b_in_rids = true;
				break;
			}
		}
		if (!b_in_rids) {
			printf("rejecting rule %d because cid %d not in requested list.\n", irec, prule->rid);
			return;
		}
	}
//			char * result_phrase = &(papp->db[result_off*papp->bitvec_size]);
	bool b_rule_matched = true;
	printf("find_matching_rules: searching cand %d.\n", irec);
	if (!prule->b_hd_per_el) {
		printf("Not implemented result searching for cent rules yet.\n");
		exit(1);
	}
	int num_opt_vars = 0;
	for (int iel = 0; iel < qlen; iel++) { 
		char * qel = &(pdbrec[iel * papp->bitvec_size]);
		int ivar = pair_dict_get(&(prule->d_var_opts), iphrase, iel);
		printf("iel %d\n",iel);
		if (ivar == -1) {
			printf("Surprise result. Probably coding error. No var for %d %d.\n", iphrase, iel);
			return;
		}
		int hd_var = 0;
		tSVarData * pvar = &(prule->var_tbl[ivar]);
		printf("var %d found with val pos %d. %d locs.\n", ivar, pvar->src_pat_el, pvar->num_locs);
		char * rule_var = &(papp->db[pvar->src_pat_el*papp->bitvec_size]);
		char * src_val = get_name_exact(papp->pdbels, 1, rule_var);
		printf("Comparing rule word %s to result word %s.\n", src_val, get_name_exact(pdbels, 1, qel));
		for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
//			printf(" %hhdvs.%hhd", pel[ibit], qel[ibit]);
			if (rule_var[ibit] != qel[ibit]) hd_var++;
		}
		printf("hd to src is %d.\n", hd_var);
		if (hd_var > pvar->hd_thresh) {
			printf(	"find_matching_rules fails ivar %d match on iel %d from phrase %d iel %d!\n", 
					ivar, iel, pvar->locs[0][0], pvar->locs[0][1]);
			if (pvar->hd_thresh == 0) {
				printf("The two words %s and %s failed the match.\n", get_name_exact(pdbels, 1, rule_var), 
						get_name_exact(pdbels, 1, qel));
			}
			b_rule_matched = false;
			break;
		}
		if (pvar->hd_thresh != 0) {
			if (num_rets != -1) {
				printf("Setting vars for opt var %d.\n", num_opt_vars);
				ivar_ret[num_opt_vars] = ivar;
				iel_ret[num_opt_vars] = iel; 
				src_iphrase_ret[num_opt_vars] = pvar->locs[0][0];
				src_iel_ret[num_opt_vars] = pvar->locs[0][1];
			}
			num_opt_vars++;
		}
	}
	if (!b_rule_matched) {
		return;
	}
	if (num_rets == -1) {
		if (ret_arr != NULL) {
			ret_arr[*pnum_found] = irec;
			ret_num_vars[*pnum_found] = num_opt_vars;
			ret_rperms[*pnum_found] = src_rperm;
		 }
		(*pnum_found)++;
	}
	printf("find_matching_rules: irec %d el_per_hd rule passed all tests.\n", irec);
	/*
	int num_var_defs = prule->num_var_defs;
	int * pvar_defs[num_var_defs];
	for (int ivar = 0; ivar < num_var_defs; ivar++) {
		pvar_defs[ivar] = &(prule->var_defs[ivar * 4]);
	}
	int hd_tot = 0;
	int num_opt_vars = 0;
//			int off = papp->rec_ptrs[irec] + papp->rule_data[irec].cent_offsets[iphrase];
	for (int iel = 0; iel < qlen; iel++) { 
		char * qel = &(pdbrec[iel * papp->bitvec_size]);
		bool b_el_var = false;
		for (int ivar = 0; ivar < num_var_defs; ivar++) {
			if ((iphrase == pvar_defs[ivar][2]) && (iel == pvar_defs[ivar][3])) {
				b_el_var = true;
				if (pvar_defs[ivar][0] == iphrase) { // unlikely event that the result has an internal var
					printf("Checking for var def %d that iel %d,%d == iel %d,%d.\n",
							ivar, iphrase, iel, pvar_defs[ivar][0], pvar_defs[ivar][1]);
					char * qvar = &(pdbrec[pvar_defs[ivar][1] * papp->bitvec_size]);
					if (memcmp(qel, qvar, sizeof (char)*papp->bitvec_size) != 0) {
						printf("find_matching_rules fails var match internal to result!\n");
						b_rule_matched = false;
						break;
					}
				}
				else { // standard scenario where a var in the result has a source in one of the earlier phrases
					// iel ivar src_iphrase src_iel
					int var_phrase_off = prule->phrase_offsets[pvar_defs[ivar][0]];
					int var_el_off = pvar_defs[ivar][1];
					char * var_bits = &(papp->db[(var_phrase_off+var_el_off)*papp->bitvec_size]);
					if (prule->b_hd_per_el) {
						int hd_thresh = prule->el_hds[var_phrase_off+var_el_off];
						int hd_var = 0;
						for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
		//					printf(" %hhdvs.%hhd", pel[ibit], qel[ibit]);
							if (var_bits[ibit] != qel[ibit]) hd_var++;
						}
						if (hd_var > hd_thresh) {
							printf(	"find_matching_rules fails var %d match on iel %d from phrase %d iel %d!\n", 
									ivar, iel, pvar_defs[ivar][0], pvar_defs[ivar][1]);
							b_rule_matched = false;
							break;
						}
						if (num_rets != -1) {
							iel_ret[num_opt_vars] = iel; ivar_ret[num_opt_vars] = ivar;
							src_iphrase_ret[num_opt_vars] = pvar_defs[ivar][0];
							src_iel_ret[num_opt_vars] = pvar_defs[ivar][1];
						}
						num_opt_vars++;
					}
				}
			}
		}
		if (!b_rule_matched) break;
		char * rule_el = &(papp->db[( papp->rec_ptrs[irec] + result_off + iel) * papp->bitvec_size]);
//				printf("iel %d db vs. qel %d:", iel, iel);
		int hd_el = 0; 
		for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
//					printf(" %hhdvs.%hhd", pel[ibit], qel[ibit]);
			if (rule_el[ibit] != qel[ibit]) hd_el++;
		}
//				printf("\n");
		if (prule->b_hd_per_el && !b_el_var)  {
			printf("Checking per el hd for iphrase %d iel %d.\n",iphrase, iel);
			if (hd_el > prule->el_hds[prule->phrase_offsets[iphrase]+iel]) {
				printf("hd_el test failed because %d > %d.\n", hd_el, prule->el_hds[prule->phrase_offsets[iphrase]+iel]);
				b_rule_matched = false;
				break;
			}
		}
		hd_tot += hd_el;
	}
	if (!b_rule_matched) return;
	if (prule->b_hd_per_el) 
		printf("find_matching_rules: irec %d el_per_hd rule passed all tests.\n", irec);
	else
		printf("find_matching_rules: irec %d hd %d vs. thresh %d.\n", irec, hd_tot, papp->rule_data[irec].phrase_hds[iphrase]);
	if (prule->b_hd_per_el || hd_tot <= papp->rule_data[irec].phrase_hds[iphrase]) {
		if (num_rets == -1) {
			if (ret_arr != NULL) {
				ret_arr[*pnum_found] = irec;
				ret_num_vars[*pnum_found] = num_opt_vars;
				ret_rperms[*pnum_found] = src_rperm;
			}
			(*pnum_found)++;
		}
		if (!prule->b_hd_per_el) {
			printf("find_matching_rules: cent test passed too.\n");
		}
	}
	 */
}

void result_matching_rule_get_opt(	void * hcapp, void * hcdb, void * hcdbels, int irec, int src_rperm, int * iel_ret, int * ivar_ret,
									int * src_iphrase_ret, int * src_iel_ret, int num_rets) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	tSBDBApp * pdb = (tSBDBApp *) hcdb;
	tSBDBApp * pdbels = (tSBDBApp *) hcdbels;
	int qlen = get_rec_len(pdb, src_rperm);
	char * pdbrec = get_rec(pdb, src_rperm);
	int num_cats = -1; int * cat_arr = NULL; int num_rids = -1; int * rid_arr = NULL;
	int * ret_arr = NULL; int * ret_num_vars = NULL; int * ret_rperms = NULL; int * pnum_found = NULL;
	find_result_matching_rules_opt(	papp, pdb, pdbels, irec, qlen, pnum_found, pdbrec, ret_arr, 
									ret_num_vars, ret_rperms,
									src_rperm, num_cats, cat_arr, num_rids, rid_arr,
									iel_ret, ivar_ret, src_iphrase_ret, src_iel_ret, num_rets);
} 

int find_result_matching_rules(	void * hcapp, void * hcdb, void * hcdbels, int * ret_arr, int * ret_num_vars, int * ret_rperms,
								int num_srcs, int * src_rperms, int num_cats, int * cat_arr, int num_rids, int * rid_arr) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	tSBDBApp * pdb = (tSBDBApp *) hcdb;
	tSBDBApp * pdbels = (tSBDBApp *) hcdbels;
	int num_found = 0;
	for (int isrc = 0; isrc < num_srcs; isrc++) {
		int qlen = get_rec_len(pdb, src_rperms[isrc]);
		//		papp->rec_buf = (char*)bdballoc(papp->rec_buf, &(papp->rec_buf_alloc), sizeof(char)*papp->bitvec_size, qlen);
		//		memcpy(papp->rec_buf, get_rec(pdb, src_rperms[isrc]), qlen*sizeof(char)*papp->bitvec_size);
		char * pdbrec;
		pdbrec = get_rec(pdb, src_rperms[isrc]);
		printf("find_matching_rules: finding for rperm %d, found so far %d.\n", src_rperms[isrc], num_found);
		for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
			int * iel_ret= NULL; int * ivar_ret = NULL; int * src_iphrase_ret = NULL;
			int * src_iel_ret = NULL; int num_rets = -1;
			find_result_matching_rules_opt(	papp, pdb, pdbels, irec, qlen, &num_found, pdbrec, ret_arr, 
								ret_num_vars, ret_rperms,
								src_rperms[isrc], num_cats, cat_arr, num_rids, rid_arr,
								iel_ret, ivar_ret, src_iphrase_ret, src_iel_ret, num_rets);

		}
	}

	return num_found;
}


void free_capp(void * hcapp) {
	tSBDBApp * papp = (tSBDBApp *) hcapp;
	bdbfree(papp);
}
