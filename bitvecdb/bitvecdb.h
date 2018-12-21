/* bitvecdb.h */

void * init_capp(void);
void free_capp(void * hcapp);
void set_el_bitvec_size(void * happ, int size);
void set_name(void * happ, char * name);
void clear_db(void * happ);
void add_rec(void * happ, int num_els, char * data);
void change_rec(void * happ, int num_els, char * data, int irec);
void del_rec(void * happ, int num_els, int irec);
int add_agent(void * happ);
void agent_change_rec(void * happ, int iagent, int irec, int badd);
int get_closest_recs(	void * happ, int k, int * idxs_ret, int * hds_ret, char * obits,
						int num_els, char * qdata, int iskip, int delta);
int init_num_left_buf(void * hcapp, int plen);
int get_cluster_seed(void * hcapp, char * cent_ret, float * hd_avg_ret, int * hd_thresh_ret, int plen, int hd_thresh);
int get_num_plen(void * hcapp, int plen);
int get_cluster(void * hcapp, int * members_ret, int num_ret, char * cent,
				int plen, int hd_thresh);
int get_irecs_with_eid(void* hcapp, int * ret_arr, int iagent, char * qbits);
void set_hd_thresh(void * hcapp, int irec, int hd_thresh);
int get_thresh_recs(void * hcapp, int * ret_arr, int plen, char * qrec);
