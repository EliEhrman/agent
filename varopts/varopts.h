/* File: varopts.h */

void * init_vo(void * hgg);
void free_vo(void * hvos);
void set_num_vars(void * hvos, int n);
void set_l_phrases_len(void * hvos, int * l_phrases_len, int len) ;
void cnt_vars(void * hvos, int loc, int b_bound, int b_must_bind, char * val, double cd, int iext_var);
void do_vo(void * hvos);

void * init_capp(void);
void set_el_bitvec_size(void * happ, int size);
void free_capp(void * hcapp);
void * init_cgg(void * hcapp);
void free_gg(void * hgg);
void set_num_els_reps(void * hgg, int num_reps);
void set_els_rep(void * hgg, char * bitvec, int hd, int iel);
void set_l_wlist_vars_len(void * hgg, int size);
void set_l_wlist_var(void * hgg, int * varquad, int ivar);
void set_l_phrases_len(void * hgg, int * l_phrases_len, int len);
