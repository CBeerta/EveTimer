#! /usr/bin/env python
# vim:ts=4 sw=4 softtabstop=4 expandtab


import os, sys, re, getopt, time
import urllib2
import cookielib

from xml.dom import minidom, Node
from datetime import datetime


class EveChar:
    
    eveusername = ''
    evepassword = ''
    evesessionid = ''

    charlist = {}

    COOKIEFILE = ''
    DATADIR = ''

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
        login = self.opener.open('https://myeve.eve-online.com/login.asp?username=%s&password=%s&login=Login&Check=OK&r=&t=/ingameboard.asp&remember=1' % (self.eveusername, self.evepassword))
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
        if not (os.path.isfile(destfile) and forcedownload == False):
            skill = self.opener.open('http://myeve.eve-online.com/xml/skilltraining.asp?characterID=%s' % self.charlist[char])
            open(destfile, "w").write(skill.read())

        skillxml = minidom.parse(destfile)
        node = skillxml.documentElement

        if node.getElementsByTagName('error'):
            os.unlink(destfile)
            raise IOError, ('skilltraining xml', 'Unable to get initial skilltraining xml')
        else:
            next =  node.getElementsByTagName('tryAgainIn')[0].childNodes[0].data
            last = time.strptime(node.getElementsByTagName('currentTime')[0].childNodes[0].data, "%Y-%m-%d %H:%M:%S")
            if float(next) + time.mktime(last) - time.mktime(time.gmtime()) < 0 and forcedownload == False:
                #we can get an update
                os.rename(destfile, destfile + '.bak')
                try:
                    self.loadSkillTrainingXML(char, True)
                    os.unlink(destfile + '.bak')
                except:
                    os.rename(destfile + '.bak', destfile)

            skillxml = minidom.parse(destfile)

        return skillxml



    def getTimeTillEnd(self, char):
        if char not in self.charlist:
            raise IOError, ('char not found', 'Unable to find %s for this account' % char)
        else:
            skillxml = self.loadSkillTrainingXML(char)
            node = skillxml.documentElement

            datenode = node.getElementsByTagName('trainingEndTime')

            if len(datenode) == 1:
                # python2.4 hackery, no datetime.datetime.strptime available there
                _ts = time.mktime(time.strptime(datenode[0].childNodes[0].data, "%Y-%m-%d %H:%M:%S"))
                to_date = datetime.fromtimestamp(_ts) - datetime.utcnow()
               #to_date = time.strptime(datenode[0].childNodes[0].data, "%Y-%m-%d %H:%M:%S") - datetime.utcnow()
            else:
                return None

            #FIXME is there a better way to reformat a timedelta?
            _deltastr = re.search('^(\d+ days,)?\s?(\d+):(\d+):(\d+)', "%s" % to_date)
            return "%s %sh, %sm, %ss" % (_deltastr.group(1),_deltastr.group(2),_deltastr.group(3),_deltastr.group(4))


    def getCurrentlyTrainingID(self, char):
        if char not in self.charlist:
            raise IOError, ('char not found', 'Unable to find %s for this account' % char)
        else:
            skillxml = self.loadSkillTrainingXML(char)
            node = skillxml.documentElement
            
            idnode = node.getElementsByTagName('trainingTypeID')
            if len(idnode) == 1:
                id = idnode[0].childNodes[0].data
            else:
                return None

            if id.isdigit():
                return int(id)
            else:
                return False




if __name__ == "__main__":

    try:
        eve = EveChar('cb5amg', 'RivCodes9')
        print eve.getCharacters()
    except IOError, (_, msg):
        print "ERROR: " + msg
    else:
        print eve.getTimeTillEnd('Eurybe')


