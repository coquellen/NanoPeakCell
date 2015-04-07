from setuptools import setup
try:
    from setuptools import Extension, setup
except ImportError:
    from distutils.core import setup
    from distutils.extension import Extension
from setuptools.command.install import install


packages=[
	'NPC'
]
package_dir = {'':'src'}

setup(
	name          =   "NPC",
	version       =   "0.0.1",
	description   =   "NanoPeakCell serial crystallography package",
	author        =   "Nicolas Coquelle",
	author_email  =   "coquelle@ibs.fr",
	packages      =   packages,
	package_dir   =   package_dir,
	package_data={'NPC': ['bitmaps/*']},
	#install_requires = [
        #                'pyFAI',
        #                'fabio',
        #                'PIL',
        #                'h5py >=2.4.0',
        #                'mpi4py',
        #                'matplotlib',
        #                'wxpython',
        #                'scipy >=0.15.0',
        #                'numpy >=1.7.0' ],
	scripts = ['src/NPC/npc','src/NPC/gui/npg'],
	 #cmdclass={
         #'install': CustomInstallCommand,}
   
)
