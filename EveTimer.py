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
__version__     = "0.9.2"

import sys
import os
import time
import threading
import Queue
from datetime import datetime
import ConfigParser
import locale

import EveSession
from EveXML import EveXML, find_file

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
	HAVE_DBUS = True
except:
	HAVE_DBUS = False

try:
    from pytz import common_timezones, timezone
    import pytz
except:
    HAVE_PYTZ = False
else:
    HAVE_PYTZ = True




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
        label = gtk.Label("_User ID:")
        label.set_use_underline(True)
        table.attach(label, 0,1,0,1)

        self.username = gtk.Entry()
        table.attach(self.username,1,2,0,1)
        label.set_mnemonic_widget(self.username)

        # Password
        label = gtk.Label("_API Key:")
        label.set_use_underline(True)
        table.attach(label, 0,1,1,2)

        self.password = gtk.Entry()
        #self.password.set_visibility(False)
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



class MainWindow(gtk.Window):
    ui_info = \
            '''
            <ui>
            <menubar name='MenuBar'>
                <menu action='FileMenu'>
                   <menuitem action='AddCharacter' />
                   <menuitem action='RemoveCharacter' />
                   <menuitem action='Refresh' />
                   <separator />
                   <menuitem action='Quit' />
                </menu>
                <menu action='HelpMenu'>
                    <menuitem action='About' />
                </menu>
            </menubar>
            </ui>'''

    ctlabel = {}
    ctflabel = {}
    ctwlabel = {} 

    do_update = True
    prev_command = None # Store the last command we got from the Datathread, so we don't flash around with the status icon

    def __init__(self, parent = None, status_icon=True):
        gobject.timeout_add(1000, self.wakeup)

        self.icon = gtk.status_icon_new_from_stock(gtk.STOCK_DIALOG_INFO)
        self.icon.set_visible(status_icon)
        self.icon.connect('activate', self.status_icon_activate)
        self.icon.connect('popup-menu', self.__icon_menu)

        gtk.Window.__init__(self)
        self.set_title('Eve Timer')
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_default_size(300,200)

        self.connect('destroy', lambda *w: gtk.main_quit())

        merge = gtk.UIManager()
        self.set_data('ui-manager', merge)
        merge.insert_action_group(self.__create_action_group(), 0)
        self.add_accel_group(merge.get_accel_group())
        
        mergeid = merge.add_ui_from_string(self.ui_info)

        table = gtk.Table(1, 3, False)
        self.add(table)

        bar = merge.get_widget("/MenuBar")
        table.attach(bar, 0, 1, 0, 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)

        self.char_notebook = gtk.Notebook()
        table.attach(self.char_notebook, 0, 1, 1, 2, gtk.EXPAND | gtk.FILL, gtk.EXPAND | gtk.FILL, 0, 0)
        for char in chars.get():
            label = gtk.Label(char.character)
            self.char_notebook.append_page(self.__char_tab(char), label)

        self.statusbar = gtk.Statusbar()
        table.attach(self.statusbar, 0, 1, 2, 3, gtk.EXPAND | gtk.FILL, 0, 0, 0)
        self.connect("window_state_event", self.update_resize_grip)
        #self.show_all()

    def __icon_menu(self, icon, event_button, event_time):
        menu = gtk.Menu()

        quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        update  = gtk.CheckMenuItem('Enable Updates')
        if self.do_update == True:
            update.set_active(True)

        menu.append(update)
        menu.append(quit)
        quit.connect('activate', lambda *w: gtk.main_quit())
        update.connect('toggled', self.toggle_update)

        menu.show_all()
        menu.popup(None, None, gtk.status_icon_position_menu, event_button, event_time, icon)

    def __create_action_group(self):
        entries = (
                ( "FileMenu", None, "_File" ),
                ( "HelpMenu", None, "_Help"),
                ( "AddCharacter", gtk.STOCK_ADD, "Add a _Character", "<control>A", "Add a Character", self.add_char),
                ( "RemoveCharacter", gtk.STOCK_DELETE, "R_emove a Character", "<control>E", "Remove a Character", self.remove_char),
                ( "Refresh", gtk.STOCK_REFRESH, "Refresh", "<control>R", "Update from EVE-Online", self.refresh),
                ( "About", gtk.STOCK_ABOUT, "About", None, "About", self.about),
                ( "Quit", gtk.STOCK_QUIT, "Quit", None, "Quit", lambda *w: gtk.main_quit()),
            )
        action_group = gtk.ActionGroup("MainWindowActions")
        action_group.add_actions(entries)

        return action_group

    def __char_tab(self, char):
        vbox = gtk.VBox(False, 10)
        vbox.set_border_width(5)

        tophbox = gtk.HBox(False, 5)
        img = gtk.Image()
        try:
            imgfile = char.DATADIR + '/' + char.charlist[char.character] + '-256.jpg'
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(imgfile, 160, 160)
            img.set_from_pixbuf(pixbuf)
        except:
            imgfile = find_file('portrait.jpg')
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(imgfile, 160, 160)
            img.set_from_pixbuf(pixbuf)

        img.set_padding(5,5)
        tophbox.pack_start(img, False, False)

        charinfo = gtk.VBox(False)

        charlabel = gtk.Label()
        charlabel.set_markup('<b><span size="x-large">' + char.character + "</span></b>")
        charlabel.set_alignment(0,0)
        charinfo.pack_start(charlabel, False, False)

        chardesc = gtk.Label()
        chardesc.set_markup("%s %s %s" % (char.gender, char.race, char.bloodLine))
        chardesc.set_alignment(0,0)
        charinfo.pack_start(chardesc, False, False)

        charcorp = gtk.Label()
        charcorp.set_markup("Corporation: %s" % char.corporationName)
        charcorp.set_alignment(0,0)
        charinfo.pack_start(charcorp, False, False)

        charbalance = gtk.Label()
        charbalance.set_markup("Balance: " + locale.format("%.2f", float(char.balance), True) + " ISK")
        charbalance.set_alignment(0,0)
        charinfo.pack_start(charbalance, False, False)

        charinfo.pack_start(gtk.Label())
        tophbox.pack_start(charinfo, False, False, 2)
        vbox.pack_start(tophbox, False, False)

        attribs = {}
        for name in ('intelligence', 'charisma', 'perception', 'memory', 'willpower'):
            level = float(getattr(char, name)) * (1 + (char.learning * 0.02))
            attribs[name] = gtk.Label()
            attribs[name].set_markup(name.capitalize() + ": %.2f" % level)
            attribs[name].set_alignment(0,0)
            charinfo.pack_start(attribs[name], False, False)

        spvbox = gtk.VBox(False, 0)
        sclabel = gtk.Label()
        sclabel.set_alignment(0,0)
        sclabel.set_markup("<b>%s Known Skills</b>" % char.skillcount)

        splabel = gtk.Label()
        splabel.set_alignment(0,0)
        splabel.set_markup("<b>%s Total SP</b>" % locale.format("%.d", int(char.skillpoints), True))

        s5label = gtk.Label()
        s5label.set_alignment(0,0)
        s5label.set_markup("<b>%s SKills at Level V</b>" % char.skillsmaxed)

        spvbox.pack_start(sclabel, False, False)
        spvbox.pack_start(splabel, False, False)
        spvbox.pack_start(s5label, False, False)
        vbox.pack_start(spvbox, False, False)

        currhbox = gtk.HBox(False, 10)
        currtraining = gtk.Label()
        currtraining.set_markup("<b>Currently Training:</b>")
        currtraining.set_alignment(0,0)
        currhbox.pack_start(currtraining, False, False)

        currvbox = gtk.VBox()

        self.ctlabel[char.character] = gtk.Label()
        self.ctlabel[char.character].set_markup("")
        self.ctlabel[char.character].set_alignment(0,0)
        currvbox.pack_start(self.ctlabel[char.character], False, False)

        self.ctflabel[char.character] = gtk.Label()
        self.ctflabel[char.character].set_markup("")
        self.ctflabel[char.character].set_alignment(0,0)
        currvbox.pack_start(self.ctflabel[char.character], False, False)

        self.ctwlabel[char.character] = gtk.Label()
        self.ctwlabel[char.character].set_markup("")
        self.ctwlabel[char.character].set_alignment(0,0)
        currvbox.pack_start(self.ctwlabel[char.character], False, False)

        currhbox.pack_start(currvbox, False, False)
        vbox.pack_start(currhbox)
        return vbox


    def status_icon_activate(self, icon = None):
        if self.window == None:
            self.show_all()
        elif self.window.get_state() & gtk.gdk.WINDOW_STATE_WITHDRAWN:
            self.window.show()
        elif not self.window.get_state() & gtk.gdk.WINDOW_STATE_WITHDRAWN:
            self.window.hide()

        return

    def toggle_update(self, button):
        if self.do_update == True:
            self.do_update = False
        else:
            self.do_update = True
        taskq.put(['do_update',self.do_update])


    def add_char(self, action):
        char = AddChar(self).get_added()
        if char != None:
            taskq.put(['add_char', char[0], char[1], char[2]])
   

    def remove_char(self, action):
        page_num = self.char_notebook.get_current_page()
        if page_num == -1:
            # not a single char
            return

        page = self.char_notebook.get_nth_page(page_num)
        char =  self.char_notebook.get_tab_label(page).get_text()
        dialog = gtk.MessageDialog(self, 0, gtk.MESSAGE_QUESTION, gtk.BUTTONS_OK_CANCEL, "Are you sure you want to remove '%s' from EveTimer?" % char)

        dialog.show_all()
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            taskq.put(['remove', char])
            self.char_notebook.remove_page(page_num)

        dialog.destroy()

    
    def refresh(self, action):
        taskq.put(['refresh'])
        return

    def about(self, action):
        dialog = gtk.AboutDialog()
        dialog.set_name("EveTimer")
        dialog.set_copyright("\302\251 %s" % __copyright__)
        dialog.set_version(__version__)
        dialog.set_website("http://claus.beerta.net/")
        dialog.set_comments("A tool to monitor your Skill Training in EVE-Online.\n\nIf you enjoy this tool, feel free to send ISK donations to 'Kyara'.")
        dialog.connect ("response", lambda d, r: d.destroy())
        dialog.show()

    def update_resize_grip(self, widget, event):
        mask = gtk.gdk.WINDOW_STATE_MAXIMIZED | gtk.gdk.WINDOW_STATE_FULLSCREEN
        if (event.changed_mask & mask):
            self.statusbar.set_has_resize_grip(not (event.new_window_state & mask))

    def update_statusbar(self, status):
        self.statusbar.pop(0)
        self.statusbar.push(0, 'Status: %s' % status)

    def wakeup(self):
        tooltip = ''
        for char in chars.get():
            try:
                _tooltip = "%s - %s %s - %s\n" % (char.character, char.currently_training, char.currently_training_to_level, char.training_ends_tooltip)
            except:
                pass
            else:
                tooltip = "%s %s" % (tooltip, _tooltip)

            if char.character in self.ctlabel and not self.window == None and not self.window.get_state() & gtk.gdk.WINDOW_STATE_WITHDRAWN:
                if char.training_ends == None:
                    self.ctlabel[char.character].set_markup( "Not Training!")
                else:
                    self.ctlabel[char.character].set_markup("%s %s" % (char.currently_training, char.currently_training_to_level))
                    self.ctflabel[char.character].set_markup("%s" % char.training_ends_tooltip)
                    try:
                        self.ctwlabel[char.character].set_markup("%s" % char.training_ends.astimezone(timezone(time.tzname[0])).strftime("%a, %d %b %Y %H:%M:%S"))
                    except:
                        self.ctwlabel[char.character].set_markup("%s EVE Time" % char.training_ends.strftime("%a, %d %b %Y %H:%M:%S"))

        while True:
            try:
                cmd = guiq.get(False)
            except Queue.Empty:
                break
            else:
                if self.prev_command != cmd[0]:
                    self.prev_command = cmd[0]
                    if cmd[0] in ('completing'):
                        self.icon.set_from_icon_name('gnome-run')
                        self.icon.set_blinking(False)
                    elif cmd[0] in ('completed'):
                        self.icon.set_from_stock(gtk.STOCK_DIALOG_WARNING)
                        self.icon.set_blinking(False)
                    elif cmd[0] in ('tooltip'):
                        self.icon.set_from_stock(gtk.STOCK_DIALOG_INFO)
                        self.icon.set_blinking(False)
                    elif cmd[0] in ('do_update'):
                        if cmd[1]:
                            self.do_update = True
                        else:
                            self.do_update = False
                    elif cmd[0] in ('char_added'):
                        label = gtk.Label(cmd[1])
                        self.char_notebook.append_page(self.__char_tab(chars.get(cmd[1])), label)
                        self.char_notebook.show_all()
                        self.char_notebook.queue_draw_area(0,0,-1,-1)

        self.icon.set_tooltip(tooltip.rstrip())
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
            print "Unable to get Character ID for %s" % char
            return False

        self.chars.append(_char)
        try:
            _char.fetchImages()
            _char.getFullXML()
        except:
            pass

        _char.training_ends_tooltip = None

        return True

    def remove(self, character):
        for i, char in enumerate(self.get()):
            if char.character == character:
                self.chars.pop(i)
        return True

    def get(self, name=None):
        if name == None:
            return self.chars
        else:
            for char in self.chars:
                if char.character == name:
                    return char
            else:
                return False


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

            while True:
                try:
                    cmd = taskq.get(False)
                except Queue.Empty:
                    break
                else:
                    if cmd[0] in ('refresh'):
                        for char in chars.get():
                            char.next_update = time.time() - 1
                    elif cmd[0] in ('add_char'):
                        try: 
                           chars.add(cmd[1], cmd[2], cmd[3])
                           chars.save()
                        except:
                            guiq.put(['error', 'Unable to add Character "%s"' % cmd[3]])
                        else:
                            guiq.put(['char_added', cmd[3]])

                    elif cmd[0] in ('terminate'):
                        terminate = True
                    elif cmd[0] in ('remove'):
                        try:
                            chars.remove(cmd[1])
                            chars.save()
                        except:
                            guiq.put(['error', 'Unable to remove Character "%s"' % cmd[1]])
                    elif cmd[0] in ('do_update'):
                        if cmd[1]:
                            do_update = True
                        else:
                            do_update = False

            _cmd = 'tooltip' 
            for char in chars.get():
                if char.next_update < time.time() and do_update:
                    try:
                        char.currently_training = evexml.skillIdToName(char.getCurrentlyTrainingID())
                        char.currently_training_to_level = char.getCurrentlyTrainingToLevel()
                        char.training_ends = char.getTrainingEnd()
                        char.getFullXML() 
                        char.fetchImages()
                    except IOError, (_, msg):
                        print "ERROR Updating :" + msg
                    except:
                        raise
                    char.next_update = time.time() + char.update_interval

                if char.training_ends != None:
                    if HAVE_PYTZ:
                        tdelta = char.training_ends - datetime.utcnow().replace(tzinfo=pytz.utc)
                    else:
                        tdelta = char.training_ends - datetime.utcnow()
                    
                    tend = tdelta.days*24*60*60 + tdelta.seconds

                    _endtime = "%s" % char.deltaToString(tdelta)
                    if  tend < 1800 and tend > 0 and _cmd != 'completed':
                        _cmd = 'completing'
                    elif tend <= 0:
                        _cmd = 'completed'
                        _endtime = 'Completed!'
                else:
                    _cmd = 'completed'
                    _endtime = ''
                char.training_ends_tooltip = _endtime

            guiq.put([_cmd])
            time.sleep(0.5)



chars = EveChars()
taskq = Queue.Queue(0) # gui -> datathread commands
guiq = Queue.Queue(0) # datathread -> gui errors/notifications

if HAVE_DBUS:
    class EveTimerDBus(dbus.service.Object):

        @dbus.service.method("org.EveTimer")
        def getCurrentlyTraining(self, character):
            char = chars.get(character)
            if char != False:
                return "%s - %s %s - %s" % (char.character, char.currently_training, char.currently_training_to_level, char.training_ends_tooltip)
            else:
                return "Char not Found!"

        @dbus.service.method("org.EveTimer")
        def quit(self):
            gtk.main_quit()

        @dbus.service.method("org.EveTimer")
        def refresh(self):
            taskq.put(['refresh'])

        @dbus.service.method("org.EveTimer")
        def version(self):
            return  __version__




class Base:
    status_icon = True

    def __init__(self):
        chars.load()
        gobject.threads_init()

    def main(self):
        if HAVE_DBUS:
            session_bus = dbus.SessionBus()
            name = dbus.service.BusName("org.EveTimer", bus=session_bus)
            object = EveTimerDBus(name, "/org/EveTimer")

        EveDataThread().start()
        MainWindow(None, self.status_icon)
        gtk.quit_add(0, taskq.put, ['terminate'])
        gtk.main()


