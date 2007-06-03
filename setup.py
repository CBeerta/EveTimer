#!/usr/bin/env python

import os

from distutils.core import setup, Extension

from EveTimer import __version__

def capture(cmd):
        return os.popen(cmd).read().strip()


setup(name='EveTimer',
        version=__version__,
        description='A utility to track Training Times in EVE-Online',
        author='Claus Beerta',
        author_email='claus@beerta.de',
        url='http://claus.beerta.net',
        py_modules=['EveTimer', 'EveXML', 'EveSession'],
        scripts=['EveTimer'],
        data_files=[('share/EveTimer', ['eve-skills2.xml','ChangeLog','README']),
                    ('share/applications', ['EveTimer.desktop'])]
        )
