#! /usr/bin/env python
# vim:ts=4 sw=4 softtabstop=4 expandtab

import sys
import os
import time
import threading
import ConfigParser

import EveSession
from EveXML import EveXML

try:
	import gtk
    import gobject
except ImportError, (strerror):
	print >>sys.stderr, "%s.  Please make sure you have this library installed into a directory in Python's path or in the same directory as Sonata.\n" % strerror
	sys.exit(1)

class AddChar(gtk.Dialog):
    """ Dialogs to add a character, design 'inspired' by EveMon (ie shamelessly copied) """

    def __init__(self, parent = None):
        gtk.Dialog.__init__(self, 'Add Character', parent, 0, ( gtk.STOCK_APPLY, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
        self.set_has_separator(False)

        self.action_area.get_children()[1].set_sensitive(False) # err, this is (x_O) no idea if there is a better way

        frame = gtk.Frame('EVE Online Loin')
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
            tmpsession = EveSession.EveChar(eveusername, evepassword)
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



class EveStatusIcon:
    """ The GUI thread """

    def __init__(self, parent=None):
        self.icon = gtk.status_icon_new_from_stock(gtk.STOCK_DIALOG_INFO)
        self.icon.connect('popup-menu', self.on_right_click)
        self.icon.connect('activate', self.on_activate)

        EveDataThread().start()

    def make_menu(self, event_button, event_time, icon):
        menu = gtk.Menu()

        newchar = gtk.MenuItem('Add New Character')
        quit    = gtk.MenuItem('Quit')

        menu.append(newchar)
        menu.append(quit)

        newchar.connect_object('activate', self.add_char, "newchar")
        quit.connect_object('activate', self.destroy, "file.quit")

        newchar.show()
        quit.show()

        menu.popup(None, None, gtk.status_icon_position_menu, event_button, event_time, icon)

    def on_right_click(self, icon, event_button, event_time):
        self.make_menu(event_button, event_time, icon)

    def destroy(self, hm):
        global_status.terminate = True # tell the data thread to quit
        gtk.main_quit()

    def add_char(self, selected):
        _char = AddChar().get_added()
        if _char != None:
            chars.add(_char[0], _char[1], _char[2]) # FIXME: is it a good idea to do this from the GUI thread?
            chars.save() # FIXME: This is EVIL, could block the UI

    def on_activate(self, icon):
        pass

    def wakeup(self):
        if global_status.current_status == Status.E_IDLE:
            self.icon.set_from_stock(gtk.STOCK_DIALOG_INFO)
            self.icon.set_tooltip(global_status.tooltip)
            self.icon.set_blinking(False)
        elif global_status.current_status == Status.E_UPDATING:
            self.icon.set_from_stock(gtk.STOCK_REFRESH)
            self.icon.set_tooltip(global_status.to_string(global_status.current_status))
            self.icon.set_blinking(True)
        return True


class EveChar(EveSession.EveChar):
    """Abstracts the EveSession.EveChar class and Stores Information about a single Character."""

    next_update     = 0 # When the next update should happen. time_t
    update_interval = 900 # in seconds, this is eve's current default

    character = ''

    tooltip = '' # tooltip with 'Charname - Skill Currently Training - When it finishes'

    def __init__(self, username, password, character):
        self.next_update = time.time() # update immediatly after start
        EveSession.EveChar.__init__(self, username, password)
        if character in self.getCharacters():
            self.character = character
        else:
            raise IOError, ('character nor found', 'The Character "%s" was not found' % character)

    def set_tooltip(self, tooltip):
        self.tooltip = tooltip
        return True


class EveChars:
    """Contains all the characters we monitor, and supplies load() and save() options"""

    #TODO: implement Locking, to allow both threads to manipulate this?

    chars = []

    DATADIR = ''

    def __init__(self):
        self.DATADIR = os.path.join(os.environ["HOME"], ".config/EveTimer/")


    def add(self, username, password, char):
        # TODO: check for dublicates

        try:
            _char = EveChar(username, password, char)
            _char.DATADIR = self.DATADIR
        except:
            return False

        self.chars.append(_char)
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



class Status:
    """Communication between the GUI thread and data thread happens through this
    Only the Data Thread is allowed to write, the GUI thread may only read.
    Manipulation should never happen directly, only through functions"""

    E_IDLE     = 0
    E_UPDATING = 1
    E_ERROR    = 2

    current_status = 0
    tooltip = ''

    terminate = False # Signal from gui thread to update thread to terminate

    def to_string(self, status):
        stati = {
                self.E_IDLE: 'Idle',  # Idle is a pseudo status, the Data thread overrides this tooltip
                self.E_UPDATING: 'Updating',
                self.E_ERROR:  'Error'
                }
        return stati[status]

    def set(self, status):
        self.current_status = status
        return True




class EveDataThread(threading.Thread):
    """ The Data Thread *doh* """

    # this is where the backgrounded updates and action is happening

    def run(self):

        while global_status.terminate == False:

            _tooltip = ''

            for char in chars.get():
                if char.next_update < time.time():
                    global_status.set(Status.E_UPDATING)

                    if len(char.charlist) == 0:
                        #no chars available yet
                        try:
                            char.getCharacters()
                        except IOError, (_, msg):
                            print "ERROR :" + msg
                        else:
                            print char.charlist

                    skillname = evexml.skillIdToName(char.getCurrentlyTrainingID(char.character))
                    char.set_tooltip("%s - %s - %s\n" % (char.character, skillname, char.getTimeTillEnd(char.character)))

                    global_status.set(Status.E_IDLE)
                    char.next_update = time.time() + char.update_interval
                else:
                    _tooltip = _tooltip + char.tooltip

            global_status.tooltip = _tooltip.rstrip()
            time.sleep(0.5) # dont burn cpu cycles



if __name__ == "__main__":

    chars = EveChars()
    chars.load()


    global_status = Status()
    evexml = EveXML()

    icon = EveStatusIcon()
    gobject.timeout_add(1000, icon.wakeup)
    gtk.gdk.threads_init()

    try:
        gtk.main()
    except KeyboardInterrupt:
        pass



