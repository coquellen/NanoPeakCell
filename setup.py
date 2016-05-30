from setuptools import setup, find_packages

setup(
	name          =   "NPC",
	version       =   "0.0.1",
	description   =   "NanoPeakCell serial crystallography package",
	author        =   "Nicolas Coquelle",
	author_email  =   "coquelleni@ill.fr",
	packages      =   find_packages(),
        package_data={'NPC': ['bitmaps/*','gui/cmaps/*']},
	scripts = ['NPC/npc','NPC/gui/npg'],

)
