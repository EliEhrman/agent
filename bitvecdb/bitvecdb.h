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
int get_plen_irecs(void * hcapp, int* ret_arr, int plen, int iagent);
int get_cluster(void * hcapp, int * members_ret, int num_ret, char * cent,
				int plen, int hd_thresh);
int get_irecs_with_eid(void* hcapp, int * ret_arr, int iagent, int iel_at, char * qbits);
int get_irecs_with_eid_by_list(	void* hcapp, int * ret_arr, int iagent, int iel_at, int * cand_arr,
								int num_cands, char * qbits);
void set_hd_thresh(void * hcapp, int irec, int hd_thresh);
int get_thresh_recs(void * hcapp, int * ret_arr, int plen, int ext_thresh, char * qrec);
int get_thresh_recs_by_list(void * hcapp, int * ret_arr, int plen, int ext_thresh,
							int * cand_arr, int num_cands, char * qrec);
int get_el_hd_recs_by_list(	void * hcapp, int * irec_arr, int * cand_arr, int num_cands, int iel, int hd, char * qrec);
void set_b_hd_thresh(void * hcapp);
void set_b_rules(void * hcapp);
void set_b_rec_names(void * happ);
void set_rec_name(void * happ, char * name, int irec);
void set_rule_data( void * hcapp, int irec, int num_cents, int * cent_offsets, int * cent_hds, int num_var_defs, 
                    int * var_defs, int bresult, int cid, int rid, int b_hd_per_el);
//void set_rule_el_data(  void * hcapp, int irec, int num_cents, int * cent_offsets, int * el_hds, int num_var_defs, 
//                        int * var_defs, int bresult, int cid, int rid);
int find_matching_rules(void * hcapp, int * ret_arr, int * ret_rperms, void * hcdb, int num_srcs, int * src_rperms);
int find_result_matching_rules(	void * hcapp, void * hcdb, void * hcdbels, int * ret_arr, int * ret_num_vars, 
                                int * ret_rperms, int num_srcs, int * src_rperms, int num_cats, int * cat_arr, 
                                int num_rids, int * rid_arr);
void result_matching_rule_get_opt(  void * hcapp, void * hcdb, void * hcdbels, int irec, int src_rperm, int * iel_ret, 
                                    int * ivar_ret, int * src_iphrase_ret, int * src_iel_ret, int num_rets);
void * create_vo(void * hcdb_rules, void * hcdb_all, void * hcdb_story, void * hcdb_els);
void init_vo(void * hvos, int irule_rec, int idb, int call_num, int rperm);
//void set_ext_rperm(void * hvos, int rperm);
void add_ext_var(void * hvos, int ivar, int b_bound, int b_must_bind, int iel, int hd, int iext_var );
void do_vo(void * hcapp);
int get_num_match_phrases(void * hvos);
int get_match_phrase_istage(void * hvos, int imatch);
int get_match_phrase_b_matched(void * hvos, int imatch);
int get_num_phrase_els(void * hvos, int imatch);
int get_phrase_el_def_type(void * hvos, int imatch, int iel);
int get_phrase_el_hd(void * hvos, int imatch, int iel);
int get_phrase_el_val(void * hvos, int imatch, int iel) ;
int get_num_combos(void * hvos);
int get_combo_len(void * hvos);
int get_combo_val(void * hvos, int icombo, int ival);
void print_db_recs(void * happ, void * hcdbels);
void set_pdbels(void * happ, void * hcdbels);
