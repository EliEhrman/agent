#!/usr/bin/env python

"""
setup.py file for SWIG bitvecdb
"""

from distutils.core import setup, Extension


bitvecdb_module = Extension('_bitvecdb',
							sources=['bitvecdb_wrap.c', 'bitvecdb.c', 'vo.c'],
							extra_compile_args=['-fPIC','-O0', '-rdynamic'],
							extra_link_args=['-L/home/eehrman/apu/build/debug/sw_sim/app/lib', '-ltest_custom']
                           )

setup (name = 'bitvecdb',
		version = '0.1',
		author      = "eli",
		description = """c db implementation for bitvec db called from agent/bdb.py""",
		ext_modules = [bitvecdb_module],
		py_modules = ["bitvecdb"],
		)