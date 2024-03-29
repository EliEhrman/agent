/* File: varopts.h */

void * str_list_create(int len);
void str_list_set(void * hl, int ipos, char * val);
void str_list_delete(void * hl);

void * create_vo(void);
void * init_vo(void * hvos, void * hgg, void * hmpdb, char * dbname, int call_num);
void free_vo(void * hvos);
void set_num_vars(void * hvos, int n);
void set_l_phrases_len(void * hvos, int * l_phrases_len, int * l_phrases_ilen, int len) ;
void cnt_vars(void * hvos, int loc, int b_bound, int b_must_bind, char * val, double cd, int iext_var);
int do_vo(void * hvos);

void * init_capp(void);
void set_el_bitvec_size(void * happ, int size);
void ll_phrases_add_ilen(void * happ);
void ll_phrases_add_val(void * happ, int ilen, void * hsl);
void ll_phrases_print(void * happ);
void free_capp(void * hcapp);
void * init_cgg(void * hcapp);
void free_gg(void * hgg);
void set_num_els_reps(void * hgg, int num_reps);
void set_els_rep(void * hgg, char * bitvec, int hd, int iel);
void set_l_wlist_vars_len(void * hgg, int size);
void set_l_wlist_var(void * hgg, int * varquad, int ivar);
//void set_l_phrases_len(void * hgg, int * l_phrases_len, int len);

//char * get_word_by_id(void * happ, int iel);
//char* get_el_bin(void * happ, char * word);
int add_el_bin(void * happ, char * word, char *bitvec);
void set_el_bin(void * happ, int iel, char * word, char *bitvec);
void change_el_bin(void * happ, int iel, char *bin);
void init_el_bin_db(void * happ, int size, int dict_space);
char* check_el_bin(void * happ, char * word);

void * mpdb_init(void * happ, int num_idbs);
void mpdb_add_db(void * hmpdb, char * dbname, int idb);
int mpdb_get_idb(void * hmpdb, char * dbname);
void mpdb_add_srphrase(void * hmpdb, int ilen, int iphrase);
void mpdb_set_idb_mrk(void * hmpdb, int idb, int isrphrase, char val);
void mpdb_del_srphrase(void * hmpdb, int isrphrase);
void mpdb_clear(void * hmpdb);

void app_mpdb_bin_init(void * happ, int num_recs, int rec_len);
void app_mpdb_bin_free(void * happ);
void app_mpdb_bin_rec_set(void * happ, int irec, char* rec);
void app_mpdb_bin_rec_add(void * happ, char* rec);
void app_mpdb_bin_rec_del(void * happ, int irec);
void app_mpdb_bin_print(void * happ);

int get_num_match_phrases(void * hvos);
int get_match_phrase_istage(void * hvos, int imatch);
int get_match_phrase_b_matched(void * hvos, int imatch);
int get_num_phrase_els(void * hvos, int imatch);
int get_phrase_el_def_type(void * hvos, int imatch, int iel);
double get_phrase_el_cd(void * hvos, int imatch, int iel) ;
char * get_phrase_el_val(void * hvos, int imatch, int iel) ;
int get_num_combos(void * hvos);
int get_combo_len(void * hvos) ;
int get_combo_val(void * hvos, int icombo, int ival);


