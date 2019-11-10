/* bdb.h */
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

typedef int intpair[2];
typedef _Bool bool;
#define true (bool)1
#define false (bool)0
#define min(a,b) (((a)<(b))?(a):(b))
#define max(a,b) (((a)>(b))?(a):(b))

#define VAR_DEF_SIZE 4

void handler(int sig);
void bdb_malloc_reset(void);
void bdb_malloc_test(void);
void* bdbmalloc2(size_t numels, size_t elsize);
void* bdbmalloc(size_t size);
void bdbfree(void* ptr);
void* bdballoc(void * ptr, int * palloc_size, size_t elsize, size_t num_els);

typedef struct SPairDict {
    int num_rows;
    int num_cols;
    int ** ppdata;
    int num_rows_alloc;
    int num_els_alloc; // num_els = num_rows * num_cols
} tSPairDict;

typedef struct SVarData {
    intpair * locs;
    int locs_alloc;
    int num_locs;
    int hd_thresh;
    int src_pat_el;
} tSVarData;

typedef struct SRuleRec {
    int num_phrases; // num cents is the same as num phrases. A rule is made of multiple phrases implemented in learning for now as phrase cluster centroids
    int * phrase_offsets;
    int phrase_offsets_alloc;
    int * phrase_lens; // length of each phrase/centroid
    int phrase_lens_alloc;
    int * thresh_hds; // For rules that have hd only per phrase, the list num_cents long of phrase hds
    int thresh_hds_alloc;
//    int * el_hds; // For rules where b_hd_per_el is true, one hd per el. The size of this list is the length of the Rec in the tSBDBApp->rec_lens
//    int el_hds_alloc;
    int num_var_defs; // All rules have a quartet of values per var (i_src_phrase, i_src_pos, i_dest_phrase, i_dest_pos).
    int * var_defs; // Num of quartets
    int var_defs_alloc;
    int b_result; // rule has a result
    int b_hd_per_el; // currently true for external rules. If true, each el has its own hd
    tSVarData * var_tbl;
    int var_tbl_alloc;
    int num_vars;
    tSPairDict d_var_opts;
    int cid;
    int rid;
} tSRuleRec;

typedef struct SDistRec {
    int dist;
    int idx;
} tSDistRec;

struct SBDBApp;
typedef struct SBDBApp tSBDBApp;

struct SBDBApp {
    int bitvec_size;
    void * hvdb;
    char * name;
    char * db;
    tSBDBApp * pdbels;
    int * vdb_cols; // array holding col returned from each rec added, num_rec_ptrs long
    int num_vdb_cols_alloc;
    int num_db_els;
    int num_db_els_alloc;
    int * rec_ptrs; // array of indices into the db for each rec. A rec may be variable length. The index must be multiplied by bitvec size
    int num_rec_ptrs;
    int num_rec_ptrs_alloc;
    int * rec_lens; // rec lens is the number of els in the phrase. For rules, it is the number of els in all the phrases combined!!!!!!!
    int rec_lens_alloc;
    tSDistRec * hd_buf;
    int hd_buf_alloc;
    int * hd_el_buf; // values of hd for each el in the rec. length max_rec_len * num_rec_ptrs
    int hd_el_buf_alloc;
    int num_hd_buckets;
    int * hd_buckets;
    int hd_buckets_alloc;
    int max_rec_len;
    char ** agent_mrks;
    int num_agents;
    int num_agents_alloc;
    int * agent_mrk_allocs;
    int agent_num_allocs_alloc;
    bool * num_left_buf; // length num_rec_ptrs
    int num_left_buf_alloc;
    int * hd_thresh; // array of hd thresh, plen ints for each record, for matches where the query must come within hd of the rec to match
    int hd_thresh_alloc;
    bool b_hd_thresh;
    int cluster_min; // minimum number of recs for a cluster
    tSRuleRec * rule_data;
    int rule_data_alloc;
    bool b_rules;
    char * rec_buf; // buffer for holding a bitvec record for queries etc
    int rec_buf_alloc;
    bool b_names; // if true, allocated mem for a name for each record
    char ** rec_names; // num_rec_ptrs long
    int rec_names_alloc;
} ;


int get_rec_len(tSBDBApp * pdb, int irec);
char * get_rec(tSBDBApp * pdb, int irec);
void clear_pair_dict(tSPairDict * ppd);
int pair_dict_get(tSPairDict * ppd, int r, int c);
void pair_dict_set(tSPairDict * ppd, int r, int c, int val);
void pair_dict_print(tSPairDict * ppd);
char * get_name_exact(tSBDBApp * papp, int qlen, char * qbits) ;
int get_next_irec(tSBDBApp * papp, int istart, int iagent, int qlen, char ** match_pat, int * match_hd);
char * get_el_in_rec(tSBDBApp * papp, int irec, int iel);
int get_irec_exact(tSBDBApp * papp, int qlen, char * qbits);
