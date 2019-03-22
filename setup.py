import setuptools

import versioneer


setuptools.setup(
    name="epyqlib",
    author="EPC Power Corp.",
    classifiers=[
        ("License :: OSI Approved :: "
         "GNU General Public License v2 or later (GPLv2+)")
    ],
    packages=setuptools.find_packages(),
    include_package_data=True,
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    entry_points={
        'console_scripts': [
            'outparsecheck = epyqlib.outparsecheck:main [dss]',
            'collectdevices = epyqlib.collectdevices:main',
            'contiguouscommits = epyqlib.utils.contiguouscommits:_entry_point [dulwich]',
            'epyqflash = epyqlib.flash:_entry_point',
            'patchvenv = epyqlib.patchvenv:main',
            'cangenmanual = epyqlib.cangenmanual:_entry_point',
            'updateepc = epyqlib.updateepc:main',
            'genbuildinfo = epyqlib.genbuildinfo:write_build_file',
            'versionfile = epyqlib.cli.versionfile:cli',
            'generateversion = epyqlib.cli.generateversion:cli',
            'autodevice = epyqlib.autodevice.cli:cli',
        ],
        'pytest11': [
            'epyqlib = epyqlib.tests.pytest_plugin',
        ]
    },
    install_requires=[
        'arrow',
        'bitstruct',
        'canmatrix',
        'click>=7',
        'python-dotenv',
        'natsort',
        'pint',
        'pyelftools',
        'qt5reactor',
        'gitpython',
        'graham',
        'PyQt5',
        'python-docx',
        'python-can',
        'twisted>=18.9.0rc1',
    ],
    extras_require={
        'deploy': [
            'gitpython',
            'requests',
        ],
        'dss': [
            'ccstudiodss>=0.2.7',
        ],
        'dulwich': [
            'dulwich',
        ],
        'test': [
            'pytest',
            'pytest-qt',
            'pytest-rerunfailures',
        ],
    },
)
