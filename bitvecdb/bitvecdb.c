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

int My_variable = 3;
double density = 4.1;

typedef int intpair[2];
typedef _Bool bool;
#define true (bool)1
#define false (bool)0
#define min(a,b) (((a)<(b))?(a):(b))
#define max(a,b) (((a)>(b))?(a):(b))

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
struct hsearch_data  d_mallocs;
int imalloc = 0;
bool b_malloc_init = false;
//int malloc_hash_max = 100000;
bool malloc_arr[MALLOC_HASH_MAX];
char addr_str_arr[MALLOC_HASH_MAX][MAX_ADDR_STR];
char * pbad = 0;

void bdb_malloc_init(void) {
	imalloc = 0;
	memset(&(d_mallocs), 0, sizeof(struct hsearch_data));
	hcreate_r(MALLOC_HASH_MAX, &d_mallocs);
	memset(malloc_arr, 0, MALLOC_HASH_MAX*sizeof(bool));
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
	for (int i=0; i<imalloc; i++) {
		if (malloc_arr[i]) {
			printf("malloc at # %d not freed, bdb_call_num %d.\n", i, bdb_call_num);
		}
	}
#endif // TEST_MALLOC
}

void* bdbmalloc2 (size_t numels, size_t elsize) {
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
		ep->data = (void *)&(malloc_arr[imalloc]);
	}
	else {
		e.data = (void *)&(malloc_arr[imalloc]);
		hsearch_r(e, ENTER, &ep, &d_mallocs);
	}
	imalloc++;
#endif // TEST_MALLOC
	return p;
}

void* bdbmalloc(size_t size) {
	return bdbmalloc2(size, 1);
}


void bdbfree (void* ptr) {
	signal(SIGSEGV, handler);   // install our handler
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
	bool * pb = (bool *)(ep->data);
	if (!*pb) {
		printf("Trying to free pointer %s which has already been freed.\n", sbuf);
	}
	*pb = false;
#endif // TEST_MALLOC
}

void* bdballoc (void * ptr, int * palloc_size, size_t elsize, size_t num_els) {
	void * new_ptr;
	if (ptr == NULL) {
		if (*palloc_size > 0) {
			printf("Error. NULL ptr with non zero allocated size.");
			return NULL;
		}
		*palloc_size = num_els;
		new_ptr =  bdbmalloc2(num_els, elsize);
//		printf("%p allocated from new in size %d\n", new_ptr, (int)num_els);
		return new_ptr;
	}
	if (num_els<=*palloc_size) {
//		printf("%d <= %d so no need to alloc.\n", (int)num_els, *(int*)palloc_size);
		return ptr;
	}
	void * oldp = ptr;
//	int old_size = *palloc_size;
	new_ptr = bdbmalloc2(num_els, elsize);
//	printf("freeing %p grow from %d to %d alloc %p.\n", oldp, *(int*)palloc_size, (int)num_els, new_ptr);
	memcpy(new_ptr, oldp, *palloc_size*elsize);
	bdbfree(oldp);
	*palloc_size = num_els;
	return new_ptr;
}

typedef struct SDistRec {
	int dist;
	int idx;
} tSDistRec;

typedef struct SBDBApp {
	int bitvec_size;
	char * db;
	int num_db_els;
	int num_db_els_alloc;
	int * rec_ptrs; // array of indices into the db for each rec. A rec may be variable length. The index must be multiplied by bitvec size
	int num_rec_ptrs;
	int num_rec_ptrs_alloc;
	int * rec_lens;
	int rec_lens_alloc;
	tSDistRec * hd_buf;
	int hd_buf_alloc;
	char ** agent_mrks;
	int num_agents;
	int num_agents_alloc;
	int * agent_mrk_allocs;
	int agent_num_allocs_alloc;
	bool * num_left_buf; // length num_rec_ptrs
	int num_left_buf_alloc;
} tSBDBApp;


void * init_capp(void) {
	tSBDBApp * papp = (tSBDBApp *)bdbmalloc(sizeof(tSBDBApp));
	return (void*)papp;
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
	papp->agent_mrks = NULL;
	papp->num_agents = 1;
	papp->num_agents_alloc = 0;
	papp->agent_mrk_allocs = NULL;
	papp->agent_num_allocs_alloc = 0;
	papp->num_left_buf = NULL;
	papp->num_left_buf_alloc = 0;
}

void set_el_bitvec_size(void * happ, int size) {
	tSBDBApp * papp = (tSBDBApp *)happ;
	papp->bitvec_size = size;
	printf("bitvec size set at %d\n", papp->bitvec_size);
}

void add_rec(void * happ, int num_els, char * data) {
	tSBDBApp * papp = (tSBDBApp *)happ;
	int old_num_els = papp->num_db_els;
	papp->num_db_els += num_els;
	papp->db = (char *)bdballoc(papp->db, &(papp->num_db_els_alloc), sizeof(char)*papp->bitvec_size, papp->num_db_els);
	memcpy(&(papp->db[old_num_els*papp->bitvec_size]), data, num_els*sizeof(char)*papp->bitvec_size);
	papp->rec_ptrs = (int *)bdballoc(papp->rec_ptrs, &(papp->num_rec_ptrs_alloc), sizeof(int), papp->num_rec_ptrs+1);
	papp->rec_ptrs[papp->num_rec_ptrs] = old_num_els;
	papp->hd_buf = (tSDistRec*)bdballoc(papp->hd_buf, &(papp->hd_buf_alloc), sizeof(tSDistRec), papp->num_rec_ptrs+1);
	papp->hd_buf[papp->num_rec_ptrs].idx = papp->num_rec_ptrs;
	papp->rec_lens = (int*)bdballoc(papp->rec_lens, &(papp->rec_lens_alloc), sizeof(int), papp->num_rec_ptrs+1);
	papp->rec_lens[papp->num_rec_ptrs] = num_els;
	if (papp->num_rec_ptrs==0) {
		papp->agent_mrk_allocs = (int *)bdballoc(	papp->agent_mrk_allocs, &(papp->agent_num_allocs_alloc), 
													sizeof(int), papp->num_agents);
		memset(papp->agent_mrk_allocs, 0, sizeof(int)*papp->num_agents);
		papp->agent_mrks = (char**)bdballoc(papp->agent_mrks, &(papp->num_agents_alloc), sizeof(char*), papp->num_agents);
		memset(papp->agent_mrks, 0, sizeof(char*)*papp->num_agents);
	}
	for (int iagent=0; iagent<papp->num_agents; iagent++) {
		papp->agent_mrks[iagent] = (char*)bdballoc(papp->agent_mrks[iagent], &(papp->agent_mrk_allocs[iagent]),
									sizeof(char), papp->num_rec_ptrs+1);
		// The default for a system with only one agent is that every phrase in the db is know to that 1 agent
		// otherwise, the default is 0
		papp->agent_mrks[iagent][papp->num_rec_ptrs] = ((papp->num_agents==1) ? 1 : 0);
	}
	papp->num_rec_ptrs++;
//	printf("bitvecdb add_rec. Added %d els. db now %d long.\n", num_els, papp->num_db_els);
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
	tSBDBApp * papp = (tSBDBApp *)happ;
	if (papp->rec_lens[irec] != num_els) {
		printf(	"Error! bitvecdb change_rec called for irec %d of length %d with new length %d. NO change made!\n", 
				irec, papp->rec_lens[irec], num_els);
		return;
	}
	memcpy(&(papp->db[papp->rec_ptrs[irec]*papp->bitvec_size]), data, num_els*sizeof(char)*papp->bitvec_size);
//	printf("bitvecdb change_rec called for irec %d len %d. pos: %d\n", irec, num_els, papp->rec_ptrs[irec]);
//	for (int iel=0; iel<papp->num_db_els; iel++) {
//		printf("iel: %d. ", iel);
//		for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
//			printf("%hhd ", papp->db[(iel * papp->bitvec_size) + ibit]);
//		}
//		printf("\n");
//	}
}

void del_rec(void * happ, int num_els, int irec) {
	tSBDBApp * papp = (tSBDBApp *)happ;

	int remove_pos = papp->rec_ptrs[irec];
	char * ptr1 = &(papp->db[remove_pos*papp->bitvec_size]);
	char * ptr2 = &(papp->db[(remove_pos+num_els)*papp->bitvec_size]);
	int els_left = papp->num_db_els - (remove_pos+num_els);
	if (els_left > 0) {
		memcpy(ptr1, ptr2, els_left * papp->bitvec_size * sizeof(char));
		int recs_left = papp->num_rec_ptrs - irec - 1;
		memcpy(&(papp->rec_ptrs[irec]), &(papp->rec_ptrs[irec+1]), recs_left*sizeof(int));
		memcpy(&(papp->rec_lens[irec]), &(papp->rec_lens[irec+1]), recs_left*sizeof(int));
		memcpy(&(papp->hd_buf[irec]), &(papp->hd_buf[irec+1]), recs_left*sizeof(tSDistRec));
		for (int iagent=0; iagent<papp->num_agents; iagent++) {
			memcpy(&(papp->agent_mrks[iagent][irec]), &(papp->agent_mrks[iagent][irec+1]), recs_left*sizeof(char));
		}
		for (int ii=0; ii<recs_left; ii++) {
			int iirec = ii + irec;
			papp->rec_ptrs[iirec] -= num_els;			
		}
	}
	papp->num_db_els -= num_els;
	papp->num_rec_ptrs--;
	printf(	"bitvecdb del_rec. Removed %d els at rec %d pos %d. db now %d long.\n", 
			num_els, irec, remove_pos, papp->num_db_els);
//	for (int iel=0; iel<papp->num_db_els; iel++) {
	for (int irec=0; irec<papp->num_rec_ptrs; irec++) {
		for (int ii = 0; ii<papp->rec_lens[irec]; ii++) {
			int iel = papp->rec_ptrs[irec] + ii;
			printf("irec: %d, ii: %d, iel: %d. ", irec, ii, iel);
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
				printf("%hhd ", papp->db[(iel * papp->bitvec_size) + ibit]);
			}
			printf("\n");
		}
	}
	
}

void add_agent(void * happ) {
	tSBDBApp * papp = (tSBDBApp *)happ;
	if (papp->num_rec_ptrs==0) {
		papp->num_agents++;
		return;
	}
	
	papp->agent_mrk_allocs = (int *)bdballoc(	papp->agent_mrk_allocs, &(papp->agent_num_allocs_alloc), 
												sizeof(int), papp->num_agents+1);
	papp->agent_mrk_allocs[papp->num_agents] = 0;
	papp->agent_mrks = (char**)bdballoc(papp->agent_mrks, &(papp->num_agents_alloc), sizeof(char*), papp->num_agents+1);
	papp->agent_mrks[papp->num_agents] = NULL;
	papp->agent_mrks[papp->num_agents] =(char*)bdballoc(papp->agent_mrks[papp->num_agents], 
														&(papp->agent_mrk_allocs[papp->num_agents]),
														sizeof(char*), papp->num_rec_ptrs);
	memset(papp->agent_mrks[papp->num_agents], 0, sizeof(char)*papp->num_rec_ptrs);
	papp->num_agents++;
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

int get_closest_recs(	void * happ, int k, int * idxs_ret, int * hds_ret, char * obits, 
						int num_els, char * qdata, int iskip, int delta) {
	tSBDBApp * papp = (tSBDBApp *)happ;
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] == (num_els-delta))
			papp->hd_buf[irec].dist = 0;
		else
			papp->hd_buf[irec].dist = -1;
	}

	for (int qpos = 0; qpos < num_els; qpos++) { // qpos == pos in query phrase
		if (qpos >= iskip && qpos <= (iskip+delta) ) continue;
		int iel = ((qpos < iskip) ? qpos  : qpos - delta);
		for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
			if (papp->rec_lens[irec] != (num_els-delta)) continue;
			char * prec = &(papp->db[(papp->rec_ptrs[irec] + iel)*papp->bitvec_size]);
			char * qrec = &(qdata[qpos*papp->bitvec_size]);
//			printf("qpos: %d iel: %d irec %d: ptr %d. ", qpos, iel, irec, papp->rec_ptrs[irec]);
			int hd = 0;
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
//				printf("%hhd ", prec[ibit]);
				if (prec[ibit] != qrec[ibit]) {
					hd++;
				}
			}
//			printf("\n");
			papp->hd_buf[irec].dist += (float)hd;
		}
	}
//	printf("hds: ");
//	for (int i=0; i<papp->num_rec_ptrs; i++) {
//		printf("%d:%d ", papp->hd_buf[i].idx, papp->hd_buf[i].dist);
//	}
//	printf("\n");
	qsort(papp->hd_buf, papp->num_rec_ptrs, sizeof(tSDistRec), dist_cmp);
	
	int num_ret = 0;
	for (int iret=0; iret < k; iret++) {
		if ((iret >= k) || (iret >= papp->num_rec_ptrs)) break;
		tSDistRec * pdr = &(papp->hd_buf[iret]);
		if (pdr->dist < 0) break;
		idxs_ret[iret] = pdr->idx;
		hds_ret[iret] = pdr->dist;
		memcpy(	&(obits[iret*papp->bitvec_size]), 
				&(papp->db[(papp->rec_ptrs[pdr->idx] + iskip) * papp->bitvec_size]), 
				papp->bitvec_size*sizeof(char));
		num_ret++;
	}
	
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		papp->hd_buf[irec].idx = irec;
	}
	return num_ret;
}

void init_num_left_buf(void * hcapp, int plen) {
	tSBDBApp * papp = (tSBDBApp *)hcapp;
	papp->num_left_buf = (bool*)bdballoc(papp->num_left_buf, &(papp->num_left_buf_alloc), sizeof(bool), papp->num_rec_ptrs);
	for (int irec = 0; irec<papp->num_rec_ptrs; irec++) {
		papp->num_left_buf[irec] = (papp->rec_lens[irec]==plen);
	}
}

void fill_hd_buf(tSBDBApp * papp, int iseed, int plen) {
	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] == plen)
			papp->hd_buf[irec].dist = 0;
		else
			papp->hd_buf[irec].dist = -1;
	}

	for (int qpos = 0; qpos < plen; qpos++) { // qpos == pos in query phrase
		for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
			if (papp->rec_lens[irec] != plen) continue;
			char * prec = &(papp->db[(papp->rec_ptrs[irec] + qpos)*papp->bitvec_size]);
			char * qrec = &(papp->db[(papp->rec_ptrs[iseed] + qpos)*papp->bitvec_size]);
//			printf("qpos: %d iel: %d irec %d: ptr %d. ", qpos, iel, irec, papp->rec_ptrs[irec]);
			int hd = 0;
			for (int ibit = 0; ibit < papp->bitvec_size; ibit++) {
//				printf("%hhd ", prec[ibit]);
				if (prec[ibit] != qrec[ibit]) {
					hd++;
				}
			}
//			printf("\n");
			papp->hd_buf[irec].dist += (float)hd;
		}
	}
}

int get_cluster_seed(void * hcapp, char * cent_ret, float * hd_avg_ret, int plen, int hd_thresh) {
	tSBDBApp * papp = (tSBDBApp *)hcapp;

	int num_left = 0;
	float best_score = 0;
	int ibest_score = -1;
	int best_thresh = -1;
	for (int iseed = 0; iseed < papp->num_rec_ptrs; iseed++) {
		if (papp->rec_lens[iseed] != plen || !papp->num_left_buf[iseed]) continue;
		fill_hd_buf(papp, iseed, plen);
		bool b_seed_scored = false;
		for (int thresh=hd_thresh*plen; thresh>=0; thresh-=plen) {
			bool b_overlap = false;
			int dist_sum = 0;
			int num_hit = 0;
			for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
				int dist = papp->hd_buf[irec].dist;
				if (dist > 0 && dist <= thresh) {
					if (!papp->num_left_buf[irec]) {
						b_overlap = true;
						break;
					}
				}
				dist_sum += dist;
				num_hit++;				
			}
			if (b_overlap) continue;
			if (num_hit > 0) {
				float avg_dist = (float)dist_sum/plen;
				float seed_score = ((papp->bitvec_size - avg_dist)/papp->bitvec_size)*num_hit;
				if (seed_score>best_score) {
					best_score = seed_score;
					ibest_score = iseed;
					best_thresh = thresh;
				}
				b_seed_scored = true;
			}
			if (b_seed_scored) break;
		}
	}

	*hd_avg_ret = 0.0;
	if (ibest_score != -1) {
		int num_hit = 0;
		int dist_sum = 0;
		fill_hd_buf(papp, ibest_score, plen);
		
		for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
			int dist = papp->hd_buf[irec].dist;
			if (dist > 0 && dist <= best_thresh) {
				if (!papp->num_left_buf[irec]) {
					papp->num_left_buf[irec] = true;
					break;
				}
			}
			dist_sum += dist;
			num_hit++;				
		}
		
		*hd_avg_ret = (float)dist_sum / (plen * num_hit);
	}

	for (int irec = 0; irec < papp->num_rec_ptrs; irec++) {
		if (papp->rec_lens[irec] != plen || !papp->num_left_buf[irec]) continue;
		num_left++;
	}

	return num_left;
}

void free_capp(void * hcapp) {
	tSBDBApp * papp = (tSBDBApp *)hcapp;
	bdbfree(papp);
}
