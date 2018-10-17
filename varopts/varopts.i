/* File: varopts.i */
%module varopts

%{
#define SWIG_FILE_WITH_INIT
#include "varopts.h"

%}

%inline %{
struct SVec {
	double x,y,z;
};
struct SNtVars {
	int loc;
	int b_bound;
	int b_must_bind;
	char * val;
	int cd;
	int iext_var;
};
extern int My_variable;
extern double density;
%}

int fact(int n);
struct SNtVars cnt_vars(int loc, int b_bound, int b_must_bind, char * val, int cd, int iext_var);



