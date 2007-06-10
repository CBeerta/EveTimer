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


__author__      = "Claus Beerta"
__copyright__   = "Copyright (C) 2007 Claus Beerta"
__version__     = "0.8.2"

import sys
import os
import time
import threading
import Queue
from datetime import datetime
import ConfigParser
import locale

import EveSession
from EveXML import EveXML

try:
	import gtk
    import gobject
    import pango
except ImportError, (strerror):
	print >>sys.stderr, "%s.  Please make sure you have this library installed into a directory in Python's path or in the same directory as Sonata.\n" % strerror
	sys.exit(1)

try:
	import dbus
	import dbus.service
	if getattr(dbus, "version", (0,0,0)) >= (0,41,0):
		import dbus.glib
	if getattr(dbus, "version", (0,0,0)) >= (0,80,0):
		import _dbus_bindings as dbus_bindings
		NEW_DBUS = True
	else:
		import dbus.dbus_bindings as dbus_bindings
		NEW_DBUS = False
	HAVE_DBUS = True
except:
	HAVE_DBUS = False


class AddChar(gtk.Dialog):
    """ Dialogs to add a character, design 'inspired' by EveMon (ie shamelessly copied) """

    def __init__(self, parent = None):
        gtk.Dialog.__init__(self, 'Add Character', parent, 0, ( gtk.STOCK_APPLY, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
        self.set_has_separator(False)

        self.action_area.get_children()[1].set_sensitive(False) # err, this is (x_O) no idea if there is a better way

        frame = gtk.Frame('EVE Online Login')
        self.vbox.pack_start(frame, True, True, 0)
        vbox = gtk.VBox(False, 8)
        vbox.set_border_width(8)
        frame.add(vbox)

        table = gtk.Table(3, 4)
        table.set_row_spacings(4)
        table.set_col_spacings(4)
        vbox.pack_start(table, False, False, 0)

        # Username
        label = gtk.Label("User _name:")
        label.set_use_underline(True)
        table.attach(label, 0,1,0,1)

        self.username = gtk.Entry()
        table.attach(self.username,1,2,0,1)
        label.set_mnemonic_widget(self.username)

        # Password
        label = gtk.Label("_Password:")
        label.set_use_underline(True)
        table.attach(label, 0,1,1,2)

        self.password = gtk.Entry()
        self.password.set_visibility(False)
        table.attach(self.password,1,2,1,2)
        label.set_mnemonic_widget(self.password)

        # Character
        label = gtk.Label("Character:")
        table.attach(label, 0,1,2,3)
        
        self.character = gtk.Entry()
        self.character.set_editable(False)
        self.character.set_text('(None)')
        table.attach(self.character,1,2,2,3)

        button = gtk.Button("...")
        button.connect('clicked', self.on_character_select_clicked)
        table.attach(button, 2,3,2,3)

        self.show_all()
        response = self.run()

        if response == gtk.RESPONSE_OK:
            self.eveusername  = self.username.get_text()
            self.evepassword  = self.password.get_text()
            self.evecharacter = self.character.get_text()
        else:
            self.eveusername = None

        self.destroy()
    
    def get_added(self):
        if self.eveusername != None:
            return ((self.eveusername, self.evepassword, self.evecharacter))
        else:
            return None

    def on_character_select_clicked(self, button):
        dialog = gtk.Dialog("Select a Character", self, 0, (gtk.STOCK_OK, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

        eveusername = self.username.get_text()
        evepassword = self.password.get_text()
        chars = {}

        try:
            tmpsession = EveSession.EveAccount(eveusername, evepassword)
            chars = tmpsession.getCharacters()
        except:
            error = gtk.MessageDialog(self, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, "Unable to get EVE Characters!")
            error.run()
            error.destroy()
            return False
        else:
            del(tmpsession)

        hbox = gtk.HBox(False, 8)
        hbox.set_border_width(8)
        dialog.vbox.pack_start(hbox, False, False, 0)

        combo = gtk.combo_box_new_text()

        for char in chars.keys():
            combo.append_text(char)

        hbox.pack_start(combo, True, True, 0)

        dialog.show_all()
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            selected = combo.get_active_text()
            if selected != None:
                self.character.set_text(selected)
                self.action_area.get_children()[1].set_sensitive(True) # err, this is (x_O) no idea if there is a better way
        dialog.destroy()
        return True

class RemoveChar(gtk.Dialog):
    def __init__(self,parent = None):
        dialog = gtk.Dialog("Select a Character", parent, 0, (gtk.STOCK_REMOVE, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
        hbox = gtk.HBox(False, 8)
        hbox.set_border_width(8)
        dialog.vbox.pack_start(hbox, False, False, 0)

        combo = gtk.combo_box_new_text()

        for char in chars.get():
            combo.append_text(char.character)

        hbox.pack_start(combo, True, True, 0)

        dialog.show_all()
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            selected = combo.get_active_text()
            if selected != None:
                taskq.put(['remove', selected])
 
        dialog.destroy()
        return None

    def get_removed(self):
        return 'fgasdfgsdFG'


class CharInfo(gtk.Dialog):
    """ Also shamelessly copied from EveMON, a window that shows some character information """
    def __init__(self, parent = None, characters = {}):


        if len(characters) == 0:
            # no use popping up an empty window really
            return False


        gtk.Dialog.__init__(self, 'Character Info', parent, 0, (gtk.STOCK_CLOSE, gtk.RESPONSE_OK))

        locale.setlocale(locale.LC_NUMERIC, '')

        notebook = gtk.Notebook()

        for char in characters:
            if char.balance == None or char.corporationName == None:
                continue
            else:
                label = gtk.Label(char.character)
                notebook.append_page(self._charPage(char), label)

        self.vbox.pack_start(notebook, False, False, 0)

        self.show_all()

        res = self.run()
        self.destroy()


    def _charPage(self, char):
        vbox = gtk.VBox(False, 10)

        table = gtk.Table(1, 1, True)
        table.set_row_spacings(10)
        table.set_col_spacings(10)

        # General Overview
        tview = gtk.TextView()
        tview.set_editable(False)
        tview.set_cursor_visible(False)
        tbuffer = tview.get_buffer()
        iter = tbuffer.get_iter_at_offset(0)

        tbuffer.create_tag("x-large", scale=pango.SCALE_X_LARGE)
        tbuffer.create_tag("bold", weight=pango.WEIGHT_BOLD)

        table.attach(tview, 1, 2, 0, 1)

        tbuffer.insert_with_tags_by_name(iter, "%s\n" % char.character, 'x-large', 'bold')
        tbuffer.insert(iter, "%s %s %s\n" % (char.gender, char.race, char.bloodLine))
        tbuffer.insert(iter, "Corporation: %s\n" % char.corporationName)
        tbuffer.insert(iter, "Balance: " + locale.format("%.2f", float(char.balance), True) + " ISK\n\n")

        for name in ('intelligence', 'charisma', 'perception', 'memory', 'willpower'):
            tbuffer.insert(iter, name.capitalize() + ": %.2f\n" % float(getattr(char, name)))


        img = gtk.Image()

        try:
            imgfile = char.DATADIR + '/' + char.charlist[char.character] + '-256.jpg'
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(imgfile, 160, 160)
            img.set_from_pixbuf(pixbuf)
        except:
            #imgfile = char.DATADIR + '/' + char.charlist[char.character] + '-256.jpg'
            imgfile = sys.prefix + '/share/EveTimer/portrait.jpg'
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(imgfile, 160, 160)
            img.set_from_pixbuf(pixbuf)

        imgevbox = gtk.EventBox()
        imgevbox.add(img)
        table.attach(imgevbox, 0, 1, 0, 1)
        imgevbox.connect('button-press-event', self.reload_image_popup)

        vbox.pack_start(table)

        # Skill Trivia
        tview1 = gtk.TextView()
        tview1.set_editable(False)
        tview1.set_cursor_visible(False)
        tbuffer1 = tview1.get_buffer()
        tbuffer1.create_tag("bold", weight=pango.WEIGHT_BOLD)
        iter = tbuffer1.get_iter_at_offset(0)

        tbuffer1.insert_with_tags_by_name(iter, "%s Known Skills\n" % char.skillcount, 'bold')
        tbuffer1.insert_with_tags_by_name(iter, "%s Total SP\n" % locale.format("%.d", int(char.skillpoints), True), 'bold')
        tbuffer1.insert_with_tags_by_name(iter, "%s Skills at Level V\n" % char.skillsmaxed, 'bold')

        vbox.pack_start(tview1)

        # Currently Training, if any
        if char.currently_training != None:
            tview2 = gtk.TextView()
            tview2.set_editable(False)
            tview2.set_cursor_visible(False)
            tbuffer2 = tview2.get_buffer()
            tbuffer2.create_tag("bold", weight=pango.WEIGHT_BOLD)

            iter = tbuffer2.get_iter_at_offset(0)
            tbuffer2.insert_with_tags_by_name(iter, "Currently Training:\n", 'bold')
            tbuffer2.insert(iter, "%s %s\n" % (char.currently_training, char.currently_training_to_level))
            tbuffer2.insert(iter, "%s\n" % char.training_ends.strftime("%a, %d %b %Y %H:%M:%S +0000"))

            vbox.pack_start(tview2)

        return vbox

    def reload_image_popup(self, img, event): 
        return # FIXME: how do i reload the damn image?
        if event.button == 3:
            menu = gtk.Menu()
            reload = gtk.ImageMenuItem(gtk.STOCK_REFRESH)
            reload.connect('activate', self.reload_image)
            menu.append(reload)
            reload.show()
            menu.popup(None, None, None, event.button, event.time)
        else:
            return

    def reload_image(self, button):
        print char.character


class EveStatusIcon:
    """ The GUI thread """

    do_update = True

    def __init__(self, parent=None):
        self.icon = gtk.status_icon_new_from_stock(gtk.STOCK_DIALOG_INFO)
        self.icon.connect('popup-menu', self.on_right_click)
        self.icon.connect('activate', self.on_activate)


        EveDataThread().start()

    def make_menu(self, event_button, event_time, icon):
        menu = gtk.Menu()

        newchar = gtk.MenuItem('Add a _Character')
        remove  = gtk.MenuItem('R_emove a Character')
        quit    = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        refresh = gtk.ImageMenuItem(gtk.STOCK_REFRESH)
        about   = gtk.ImageMenuItem(gtk.STOCK_ABOUT)
        update  = gtk.CheckMenuItem('Enable Updates')

        if self.do_update == True:
            update.set_active(True)


        menu.append(about)
        menu.append(refresh)
        menu.append(update)
        menu.append(newchar)
        menu.append(remove)
        menu.append(quit)

        refresh.connect('activate', self.refresh)
        newchar.connect('activate', self.add_char)
        remove.connect('activate', self.remove_char)
        quit.connect('activate', self.destroy)
        about.connect('activate', self.activate_about)
        update.connect('toggled', self.toggle_update)

        refresh.show()
        newchar.show()
        remove.show()
        quit.show()
        about.show()
        update.show()

        menu.popup(None, None, gtk.status_icon_position_menu, event_button, event_time, icon)

    def on_right_click(self, icon, event_button, event_time):
        self.make_menu(event_button, event_time, icon)

    def destroy(self, button):
        taskq.put(['terminate'])
        gtk.main_quit()

    def remove_char(self, button):
        _char = RemoveChar().get_removed()

    def toggle_update(self, button):
        if self.do_update == True:
            self.do_update = False
        else:
            self.do_update = True
        taskq.put(['do_update',self.do_update])


    def add_char(self, selected):
        _char = AddChar().get_added()
        if _char != None:
            taskq.put(['add_char', _char[0], _char[1], _char[2]])

    def on_activate(self, icon):
        CharInfo(None, chars.get())

    def activate_about(self, button):
        dialog = gtk.AboutDialog()
        dialog.set_name("EveTimer")
        dialog.set_copyright("\302\251 %s" % __copyright__)
        dialog.set_version(__version__)
        dialog.set_website("http://claus.beerta.net/")
        dialog.set_comments("A tool to monitor your Skill Training in EVE-Online.\n\nIf you enjoy this tool, feel free to send ISK donations to 'Kyara'.")

        dialog.connect ("response", lambda d, r: d.destroy())
        dialog.show()


    def refresh(self, button):
        taskq.put(['refresh'])

    def wakeup(self):
        try:
            _cmd = guiq.get(False)
        except Queue.Empty:
            pass
        else:
            if _cmd[0] in ('completing'):
                self.icon.set_from_icon_name('gnome-run')
                self.icon.set_tooltip(_cmd[1])
                self.icon.set_blinking(False)
            elif _cmd[0] in ('completed'):
                self.icon.set_from_stock(gtk.STOCK_DIALOG_WARNING)
                self.icon.set_tooltip(_cmd[1])
                self.icon.set_blinking(False)
            elif _cmd[0] in ('tooltip'):
                self.icon.set_tooltip(_cmd[1])
                self.icon.set_from_stock(gtk.STOCK_DIALOG_INFO)
                self.icon.set_blinking(False)
            elif _cmd[0] in ('updating'):
                self.icon.set_from_stock(gtk.STOCK_REFRESH)
                self.icon.set_blinking(True)
            #guiq.task_done() # not available in python2.4
        return True



class EveChars:
    """Contains all the characters we monitor, and supplies load() and save() options, only the datathread is allowed to manipulate the data herein"""

    chars = []

    DATADIR = ''

    def __init__(self):
        self.DATADIR = os.path.join(os.environ["HOME"], ".config/EveTimer/")


    def add(self, username, password, char):
        # TODO: check for dublicates
        try:
            _char = EveSession.EveChar(username, password, char)
            _char.DATADIR = self.DATADIR
        except:
            raise

        self.chars.append(_char)
        try:
            _char.fetchImages()
            _char.getFullXML()
        except:
            pass

        return True

    def remove(self, character):
        for i, char in enumerate(self.get()):
            if char.character == character:
                self.chars.pop(i)
        return True


    def get(self):
        return self.chars

    def save(self):
        cfg = ConfigParser.ConfigParser()

        for char in self.get():
            cfg.add_section(char.character)
            cfg.set(char.character, 'username', char.eveusername)
            cfg.set(char.character, 'password', char.evepassword)

        try:
            cfg.write(open(self.DATADIR + 'characters.cfg', 'w'))
            os.chmod(self.DATADIR + 'characters.cfg', 0600) # this holds username+passwords
        except:
            raise
        
        return True

    def load(self):
        cfg = ConfigParser.ConfigParser()
        
        try:
            cfg.read(self.DATADIR + 'characters.cfg')
            for char in cfg.sections():
                self.add(cfg.get(char, "username"), cfg.get(char, "password"), char)
        except:
            raise



class EveDataThread(threading.Thread):
    """ The Data Thread *doh* """

    # this is where the backgrounded updates and action is happening

    def run(self):
        evexml = EveXML()

        terminate = False
        do_update = True # set to false in case of screensaver 

        while terminate == False:

            try:
                _cmd = taskq.get(False)
            except Queue.Empty:
                pass
            else:
                if _cmd[0] in ('refresh'):
                    for char in chars.get():
                        char.next_update = time.time() - 1
                elif _cmd[0] in ('add_char'):
                    try: 
                       chars.add(_cmd[1], _cmd[2], _cmd[3])
                       chars.save()
                    except:
                        guiq.put(['error', 'Unable to add Character "%s"' % _cmd[3]])
                elif _cmd[0] in ('terminate'):
                    terminate = True
                elif _cmd[0] in ('remove'):
                    try:
                        chars.remove(_cmd[1])
                        chars.save()
                    except:
                        guiq.put(['error', 'Unable to remove Character "%s"' % _cmd[1]])
                elif _cmd[0] in ('do_update'):
                    if _cmd[1]:
                        do_update = True
                    else:
                        do_update = False



                #taskq.task_done() #not available in python2.4

            _tooltip = ''
            _cmd = 'tooltip'

            for char in chars.get():
                if char.next_update < time.time() and do_update:
                    #FIXME:  Updating and Downloading should really be in the EveAccount or EveChar class, not here
                    guiq.put(['updating'])
                    if len(char.charlist) == 0:
                        try:
                            char.getCharacters()
                        except IOError, (_, msg):
                            print "ERROR :" + msg
                        else:
                            print char.charlist

                    try:
                        char.currently_training = evexml.skillIdToName(char.getCurrentlyTrainingID())
                        char.currently_training_to_level = char.getCurrentlyTrainingToLevel()
                        char.training_ends = char.getTrainingEnd()
                        char.getFullXML() 
                        char.fetchImages()
                    except IOError, (_, msg):
                        print "ERROR :" + msg
                    except:
                        pass

                    char.next_update = time.time() + char.update_interval

                if char.training_ends != None:
                    tdelta = char.training_ends - datetime.utcnow()
                    tend = tdelta.days*24*60*60 + tdelta.seconds

                    _endtime = " - %s" % char.deltaToString(char.training_ends - datetime.utcnow())
                    if  tend < 1800 and tend > 0:
                        _cmd = 'completing'
                    elif tend <= 0:
                        _cmd = 'completed'
                        _endtime = 'Completed!'
                else:
                    _cmd = 'completed'
                    _endtime = ''

                _tooltip = "%s %s - %s %s %s\n" % (_tooltip, char.character, char.currently_training, char.currently_training_to_level, _endtime)


            guiq.put([_cmd, _tooltip.rstrip()])
            time.sleep(1) # dont burn cpu cycles



def detect_screensaver(enabled):
    if enabled == 1:
        taskq.put(['do_update', False])
    else:
        taskq.put(['do_update',True])


chars = EveChars()
taskq = Queue.Queue(0) # gui -> datathread commands
guiq = Queue.Queue(0) # datathread -> gui errors/notifications

class Base:
    def __init__(self):
        chars.load()

        icon = EveStatusIcon()
        gobject.timeout_add(500, icon.wakeup)
        gtk.gdk.threads_init()

    def main(self):

        #FIXME: this clashes with the manual update toggle
        """
        if HAVE_DBUS:
            bus = dbus.SessionBus()
            screensaver = bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver')
            screensaver.connect_to_signal('ActiveChanged', detect_screensaver)

        """


        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()



