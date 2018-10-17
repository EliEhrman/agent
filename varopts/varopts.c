/* File: varopts.c */

#include "varopts.h"

struct SNtVars {
	int loc;
	int b_bound;
	int b_must_bind;
	char * val;
	int cd;
	int iext_var;
};

int My_variable = 3;
double density = 4.1;

int fact(int n) {
    if (n < 0){ /* This should probably return an error, but this is simpler */
        return 0;
    }
    if (n == 0) {
        return 1;
    }
    else {
        /* testing for overflow would be a good idea here */
        return n * fact(n-1);
    }
}

struct SNtVars cnt_vars(int loc, int b_bound, int b_must_bind, char * val, int cd, int iext_var) {
	struct SNtVars nv;
	nv.loc = loc, nv.b_bound = b_bound, nv.b_must_bind = b_must_bind, nv.val = val, nv.cd = cd, nv.iext_var = iext_var;
	/*, b_bound, val, cd, iext_var);*/
	return nv;
}

