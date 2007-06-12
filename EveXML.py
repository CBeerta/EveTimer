#! /usr/bin/env python
# vim:ts=4 sw=4 softtabstop=4 expandtab
#
# Copyright (C) 2007 - Claus Beerta
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

from xml.dom import minidom, Node
import sys

class EveXML:

    skillnames = {}
    
    def __init__(self):
        try:
            skilldom = minidom.parse(sys.prefix + '/share/EveTimer/eve-skills2.xml')
        except IOError:
            print "Unable to load %s, check for correct installation and permissios. " % (sys.prefix + '/share/EveTimer/eve-skills2.xml')
        else:
            node = skilldom.documentElement
            for skill in node.getElementsByTagName('s'):
                i = skill.getAttribute('i')
                n = skill.getAttribute('n')

                if i.isdigit() and n != None:
                    self.skillnames[int(i)] = n

        skilldom.unlink()
    
    def skillIdToName(self, id):

        if id in self.skillnames.keys():
            return self.skillnames[id]
        elif id == None:
            return 'Not Training!'
        else:
            return 'Unknown Skill'
