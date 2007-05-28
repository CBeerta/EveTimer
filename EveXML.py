#! /usr/bin/env python
# vim:ts=4 sw=4 softtabstop=4 expandtab

from xml.dom import minidom, Node


class EveXML:

    skillnames = {}
    
    def __init__(self):
        self.skilldom = minidom.parse('eve-skills2.xml')

        node = self.skilldom.documentElement
        for skill in node.getElementsByTagName('s'):
            i = skill.getAttribute('i')
            n = skill.getAttribute('n')

            if i.isdigit() and n != None:
                self.skillnames[int(i)] = n

        
    def skillIdToName(self, id):
        if id in self.skillnames.keys():
            return self.skillnames[id]
        elif id == None:
            return 'Not Training!'
        else:
            return 'Unknown Skill'




if __name__ == '__main__':

    xml = EveSkillXML()

    print xml.trainingTypeID_to_string(12099)


