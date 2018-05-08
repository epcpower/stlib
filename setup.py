from setuptools import setup, find_packages

setup(
    name="epyqlib",
    version="0.1",
    author="EPC Power Corp.",
    classifiers=[
        ("License :: OSI Approved :: "
         "GNU General Public License v2 or later (GPLv2+)")
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'collectdevices = epyqlib.collectdevices:main',
            'contiguouscommits = epyqlib.utils.contiguouscommits:_entry_point [dulwich]',
            'epyqflash = epyqlib.flash:_entry_point',
            'patchvenv = epyqlib.patchvenv:main',
            'cangenmanual = epyqlib.cangenmanual:_entry_point',
            'updateepc = epyqlib.updateepc:main',
            'genbuildinfo = epyqlib.genbuildinfo:write_build_file',
            'versionfile = epyqlib.cli.versionfile:cli',
            'generateversion = epyqlib.cli.generateversion:cli',
        ]
    },
    install_requires=[
        'arrow',
        'bitstruct',
        'natsort',
        'pint',
        'pyelftools',
        'qt5reactor',
        'gitpython',
        'graham',
        'PyQt5',
        'click',
        'python-docx',
        'python-can',
    ],
    extras_requires={
        'deploy': [
            'gitpython',
            'requests',
        ],
        'dulwich': [
            'dulwich',
        ],
    },
)
