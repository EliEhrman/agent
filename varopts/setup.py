#!/usr/bin/env python

"""
setup.py file for SWIG varopts
"""

from distutils.core import setup, Extension


varopts_module = Extension('_varopts',
							sources=['varopts_wrap.c', 'varopts.c'],
						   extra_compile_args=['-O0', '-rdynamic']
                           )

setup (name = 'varopts',
		version = '0.1',
		author      = "SWIG Docs",
		description = """Simple swig example from docs""",
		ext_modules = [varopts_module],
		py_modules = ["varopts"],
		)