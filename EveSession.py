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


import os, sys, re, getopt, time
import urllib2
import cookielib

from xml.dom import minidom, Node
from datetime import datetime



class EveAccount:
    
    eveusername = None
    evepassword = None
    evesessionid = None

    charlist = {}

    COOKIEFILE = None
    DATADIR = None

    _skillxml = None

    def __init__(self, username, password):
        self.eveusername = username
        self.evepassword = password

        self.DATADIR = os.path.join(os.environ["HOME"], ".config/EveTimer/")

        if not os.path.isdir(self.DATADIR):
            os.mkdir(self.DATADIR)

        self.COOKIEFILE = self.DATADIR +  "evemon-cookies.txt"

        # We need a session ID to download the xml files, so we need cookies
        self.cj = cookielib.LWPCookieJar(self.COOKIEFILE)
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
        
        #FIXME: multiple accounts!
        #if os.path.isfile(self.COOKIEFILE):
        #    self.cj.load()

        self.getSessionId()


    def getSessionId(self):
        login = self.opener.open('https://myeve.eve-online.com/login.asp', 'username=%s&password=%s&login=Login&Check=OK&r=&t=/ingameboard.asp&remember=1' % (self.eveusername, self.evepassword))
        
        sid = re.search('^https:\/\/.*&sid=(\d+)$', login.geturl())
        if sid:
            #login succeeded
            self.evesessionid = sid.group(1)
            #self.cj.save() #FIXME: what to do on multiple accounts?
            return True
        else:
            self.evesessionid = False
            raise IOError, ('login error', 'Unable to get Session ID')


    def getCharacters(self):
        _charlist = {}
        charxml = self.opener.open('http://myeve.eve-online.com/character/xml.asp?sid=' + self.evesessionid)
        chardom = minidom.parseString(charxml.read())

        node = chardom.documentElement
        for char in node.getElementsByTagName('character'):
            _charlist[char.getAttribute('name')] = char.getAttribute('characterID')

        chardom.unlink()

        if len(_charlist) > 0:
            self.charlist = _charlist
            return _charlist
        else:
            raise IOError, ('no chars found', 'Unable to get any Character IDs')


    def loadSkillTrainingXML(self, char, forcedownload=False):
        destfile = self.DATADIR + '/' + self.charlist[char] + '.xml'
        if not os.path.isfile(destfile) or forcedownload == True:
            skill = self.opener.open('http://myeve.eve-online.com/xml/skilltraining.asp?characterID=%s' % self.charlist[char])
            open(destfile, "w").write(skill.read())

        if self._skillxml == None or forcedownload == True:
            # store the dom so we don't have to reload it on every request
            skillxml = minidom.parse(destfile)
        else:
            skillxml = self._skillxml

        node = skillxml.documentElement
        next =  node.getElementsByTagName('tryAgainIn')[0].childNodes[0].data
        if node.getElementsByTagName('error'):
            os.unlink(destfile)
            self._skillxml = None
            raise IOError, ('skilltraining xml', 'Unable to get initial skilltraining xml, try again in %s' % next)
        else:
            last = time.strptime(node.getElementsByTagName('currentTime')[0].childNodes[0].data + " GMT", "%Y-%m-%d %H:%M:%S %Z")

            if (float(next)+time.mktime(last)) < time.mktime(time.gmtime()) and forcedownload == False:
                #we can get an update
                os.rename(destfile, destfile + '.bak')
                try:
                    self.loadSkillTrainingXML(char, True)
                except:
                    os.rename(destfile + '.bak', destfile)
                else:
                    os.unlink(destfile + '.bak')

            skillxml = minidom.parse(destfile)

        self._skillxml = skillxml
        return self._skillxml


    def deltaToString(self, tdelta):
            #FIXME is there a better way to reformat a timedelta?
            _deltastr = re.search('^(\d+ [a-z,]{4,5})?\s?(\d+):(\d+):(\d+)', "%s" % tdelta)

            if _deltastr == None:
                return tdelta

            _datestr = ''
            # FIXME: use your brain!
            if _deltastr.group(1) != None:
                _datestr = "%s " % _deltastr.group(1)

            if _deltastr.group(2) != None:
                _datestr = "%s %sh" % (_datestr, _deltastr.group(2))

            if _deltastr.group(3) != None:
                _datestr = "%s %sm" % (_datestr, _deltastr.group(3))

            if _deltastr.group(4) != None:
                _datestr = "%s %ss" % (_datestr, _deltastr.group(4))

            return _datestr




class EveChar(EveAccount):
    """Abstracts the EveSession.EveAccount class and Stores Information about a single Character."""

    next_update     = 0 # When the next update should happen. time_t
    update_interval = 900 # in seconds, this is eve's current default

    character = None

    currently_training = None
    training_ends = None

    balance = None
    bloodLine = None
    gender = None
    corporationName = None
    race = None

    # Attrributes  
    intelligence = None
    charisma = None
    perception = None
    memory = None
    willpower = None
    
    skillpoints = None
    skillcount = None
    skillsmaxed = None

    def __init__(self, username, password, character):
        self.next_update = time.time() # update immediatly after start
        EveAccount.__init__(self, username, password)
        if character in self.getCharacters():
            self.character = character
        else:
            raise IOError, ('character nor found', 'The Character "%s" was not found' % character)

    def getFullXML(self, forcedownload=False):
        destfile = self.DATADIR + '/' + self.charlist[self.character] + '-full.xml'

        if not (os.path.isfile(destfile)) and forcedownload == False:
            try:
                url = 'http://myeve.eve-online.com/character/xml.asp?characterID=' + self.charlist[self.character]
                xml = self.opener.open(url)
                open(destfile, 'w').write(xml.read())
            except:
                raise

        dom = minidom.parse(destfile)

        for char in  dom.getElementsByTagName('character'):
            if char.getAttribute('name') == self.character:
                nextUpdate = int(char.getAttribute('timeLeftInCache'))/1000 +  os.stat(destfile).st_mtime
                if  datetime.fromtimestamp(nextUpdate) <= datetime.utcnow():
                    os.unlink(destfile)
                    return self.getFullXML(True)


        # Set the Attributes for this character
        for node in dom.getElementsByTagName('attributes')[0].childNodes:
            if node.nodeType == node.ELEMENT_NODE:
                for attribs in node.childNodes:
                    if attribs.nodeType == attribs.TEXT_NODE:
                        setattr(self, node.tagName, attribs.data)
        
        for type in ('balance', 'bloodLine', 'race', 'gender', 'corporationName'):
            setattr(self, type, dom.getElementsByTagName(type)[0].childNodes[0].data)

        sp = sc = sa5 = 0
        for node in dom.getElementsByTagName('skill'):
            if node.nodeType == node.ELEMENT_NODE:
                sp += int(node.getElementsByTagName('skillpoints')[0].childNodes[0].data)
                sc += 1
                if int(node.getElementsByTagName('level')[0].childNodes[0].data) == 5:
                    sa5 += 1

        self.skillpoints = sp
        self.skillcount = sc
        self.skillsmaxed = sa5
    

    def getTrainingEnd(self):
        skillxml = self.loadSkillTrainingXML(self.character)
        node = skillxml.documentElement
        datenode = node.getElementsByTagName('trainingEndTime')
        if len(datenode) == 1:
            # python2.4 hackery, no datetime.datetime.strptime available there
            _ts = time.mktime(time.strptime(datenode[0].childNodes[0].data, "%Y-%m-%d %H:%M:%S"))
            to_date = datetime.fromtimestamp(_ts)
            return to_date
        return None


    def getCurrentlyTrainingID(self):
        skillxml = self.loadSkillTrainingXML(self.character)
        node = skillxml.documentElement
        
        idnode = node.getElementsByTagName('trainingTypeID')
        if len(idnode) == 1:
            id = idnode[0].childNodes[0].data
            if id.isdigit():
                return int(id)
        return None

    def getCurrentlyTrainingToLevel(self):
        levels = [None, 'I', 'II', 'III', 'IV', 'V']
        skillxml = self.loadSkillTrainingXML(self.character)
        node = skillxml.documentElement

        lnode = node.getElementsByTagName('trainingToLevel')
        if len(lnode) == 1:
            lvl = lnode[0].childNodes[0].data
            if lvl.isdigit():
                return levels[int(lvl)]
            
        return None

    def fetchImages(self):
        for size in [64,256]:
            destfile = self.DATADIR + '/' + self.charlist[self.character] + '-%d' % size + '.jpg'
            if os.path.isfile(destfile):
                continue # don't redownload
            try:
                url = 'http://img.eve.is/serv.asp?s=%d&c=%s' % (size, self.charlist[self.character])
                img = urllib2.urlopen(url)
                open(destfile, 'w').write(img.read())
            except:
                pass

