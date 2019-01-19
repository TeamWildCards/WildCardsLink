"""
 Copyright (c) 2018 Dynamic Phase, LLC All rights reserved.
 
 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE
 Version 3 as published by the Free Software Foundation; either
 or (at your option) any later version.
 This library is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.

 You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
 along with this library; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import sys
from systray.traybar import SysTrayIcon

def do_nothing(sysTrayIcon, index_number, menu_text):
    pass


#todo:
#Support other operating systems other than windows
#Refresh the context menu automatically when data changes
#add "bubble" notification messages
#http://blog.differentpla.net/blog/2007/10/01/shell_notifyicon-displaying-a-balloon-from-a-hidden-notification-icon

class WildCardsUserInterface:
    def __init__(self, parent=None, serverport=None, serialport=None):
        self._parent = parent
        self.Exiting = False
        self._hover_text = "WildCards Link"
        self.CurrentServerPort = serverport
        self.CurrentServerStatus = "RedLight.ico"
        self.CurrentSerialPort = serialport
        self.CurrentSerialPortStatus = "RedLight.ico"

        self.ServerStatus = None
        self.SerialStatus = None
        self.SerialPorts = None
                      
        self._generate_updated_menu()
        
        if sys.platform.startswith('darwin'):
            self.WildsysTrayIcon = None
        else:
            self.WildsysTrayIcon = SysTrayIcon("wc_site_icon_filled.ico", self._hover_text, self.menu_options, on_quit=self.bye, default_menu_index=1)
            
        

        self.update_menu_options()
        
        if sys.platform.startswith('darwin'):
            pass
        else:        
            self.WildsysTrayIcon.start()        
      
    def UpdateServerPort(self, serverportnum):
        #called by higher level objects
        self.CurrentServerPort = serverportnum
        self.update_menu_options()

    def UpdateServerStatusGood(self, status):
        #called by higher level objects
        if status:
            self.CurrentServerStatus = "GreenLight.ico"
        else:
            self.CurrentServerStatus = "RedLight.ico"
        self.update_menu_options()       

    def UpdateCurrentPort(self, port):
        """
        Updates the current port. Typically called by a parent object

        :param port: string name of the port
        :returns: No return value.
        """
        self.CurrentSerialPort = port
        self.update_menu_options()
        
    def UpdateCurrentPortStatusGood(self, status):
        """
        Updates the current port status. Typically called by a parent object.
        Triggers refresh of the menu

        :param status: boolean, true = port is good
        :returns: No return value.
        """
        if status:
            self.CurrentSerialPortStatus = "GreenLight.ico"
        else:
            self.CurrentSerialPortStatus = "RedLight.ico"
        self.update_menu_options()
                        
    def UpdatePortList(self, portlist):
        self.SerialPorts = None
        for port in portlist:
            if self.SerialPorts is None:
                self.SerialPorts = []
            self.SerialPorts.append((port, None, self.SelectNewPort))
            self.update_menu_options()

    def SelectNewPort(self, systray, index_number, menu_text):
        #called by the systray menu
        print("select port {}".format(menu_text))
        print(menu_text)
        self._parent.SelectUserSpecifiedPort(menu_text)
        #select port option_text

    def update_menu_options(self):
        self._generate_updated_menu()
        self._update_menu(self.menu_options)
    
    def _generate_updated_menu(self):
        if self.CurrentServerPort is not None:
            #may change do nothing to something that pops up an input box for a new server number on localhost??
            self.ServerStatus = ('Server listening on port {}'.format(self.CurrentServerPort), self.CurrentServerStatus, do_nothing)
        else:
            self.ServerStatus = ('Server not running', self.CurrentServerStatus, do_nothing)
        #print("{}".format(self.SerialPorts))
        
        if self.SerialPorts is None:
            submenu = do_nothing
        else:
            submenu = tuple(self.SerialPorts)
            
        if self.CurrentSerialPort is not None:
            self.SerialStatus = ('Connected to {}'.format(self.CurrentSerialPort),
                                 self.CurrentSerialPortStatus,
                                 submenu)
        else:
            self.SerialStatus = ('Serial port not connected',
                                 self.CurrentSerialPortStatus,
                                 submenu)

        self.menu_options = (('WildCards Link', "wc_site_icon_filled.ico", do_nothing),
                             self.ServerStatus,
                             self.SerialStatus)                
                             
    def _update_menu(self, menu_options):
        print("updating menu options")
        if sys.platform.startswith('darwin'):
            pass
        else:   
            self.WildsysTrayIcon.update(menu_options = menu_options)
        
    def bye(self, sysTrayIcon):
        #called by "on_quit"
        self.Exiting = True

    def kill_systray(self):
        if sys.platform.startswith('darwin'):
            pass
        else:   
            self.WildsysTrayIcon.shutdown()   
        