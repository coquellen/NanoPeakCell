from setuptools import setup, find_packages, Extension

VERSION = (0, 3, 2)
VERSION_STR = ".".join([str(x) for x in VERSION])

setup(
	name          =   "NanoPeakCell",
	version       =   VERSION_STR,
	description   =   "NanoPeakCell serial crystallography package",
	author        =   "Nicolas Coquelle",
	author_email  =   "coquelleni@ill.fr",
	packages      =   find_packages(),
    package_data={'NPC': ['bitmaps/*','gui/cmaps/*','gui/icons/*']},
	scripts = ['NPC/npc','NPC/gui/npg'],

    ext_modules=[
        Extension('cbf_c', [
            'cbf/cbf.cpp',
            'cbf/python-cbf.c'
        ], extra_compile_args=[
            "-lstdc++",
            "-O3",
            "-Wall",
            "-W",
            "-Wundef",
            "-DVERSION=\"%s\"" % VERSION_STR,
            "-DCBF_VERSION=\"0.0.1\"",
        ])
    ],

)
