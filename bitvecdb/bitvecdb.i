/* File: bitvecdb.i */
%module bitvecdb

%{
#define SWIG_FILE_WITH_INIT
#include "bitvecdb.h"

%}

%inline %{
struct SVec {
	double x,y,z;
};
extern int My_variable;
extern double density;
%}

%include "carrays.i"
%array_class(int, intArray);
%array_class(char, charArray);
%array_class(char, strArray);
%array_class(float, floatArray);

%include "bitvecdb.h"

