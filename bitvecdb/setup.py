#!/usr/bin/env python

"""
setup.py file for SWIG bitvecdb
"""

from distutils.core import setup, Extension


bitvecdb_module = Extension('_bitvecdb',
							sources=['bitvecdb_wrap.c', 'bitvecdb.c'],
						   # extra_compile_args=['-O0', '-rdynamic']
                           )

setup (name = 'bitvecdb',
		version = '0.1',
		author      = "eli",
		description = """c db implementation for bitvec db called from agent/bdb.py""",
		ext_modules = [bitvecdb_module],
		py_modules = ["bitvecdb"],
		)