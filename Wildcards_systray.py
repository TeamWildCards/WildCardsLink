

from systray.traybar import SysTrayIcon

def do_nothing(sysTrayIcon):
    pass

class WildCardsSystray:
    def __init__(self, parent=None, serverport=None, serialport=None):
        self._parent = parent
        self.Exiting = False
        self._hover_text = "WildCards Link"
        self.ServerStatus = ('Server not running', "RedLight.ico", do_nothing)
        self.SerialStatus = ('Serial port not connected', "RedLight.ico", do_nothing)     

        self.menu_options = (('WildCards Link', "wc_site_icon_filled.ico", do_nothing),
            self.ServerStatus,
            self.SerialStatus)
            
        self.WildsysTrayIcon = SysTrayIcon("wc_site_icon_filled.ico", self._hover_text, self.menu_options, on_quit=self.bye, default_menu_index=1)
        
        self.set_server_port(serverport)
        self.set_serial_port(serialport)
        self.WildsysTrayIcon.start()        
        
    def set_server_port(self, serverportnum):
        if serverportnum is None:
            self.ServerStatus = ('Server not running', "RedLight.ico", do_nothing)
        else:
            self.ServerStatus = ('Server port {}'.format(serverportnum), "GreenLight.ico", do_nothing)  
        self.menu_options = (('WildCards Link', "wc_site_icon_filled.ico", do_nothing),
            self.ServerStatus,
            self.SerialStatus)
        self._update_menu(self.menu_options)  
        
    def set_serial_port(self, serialportname):
        if serialportname is None:
             self.SerialStatus = ('Serial port not connected', "RedLight.ico", do_nothing)
        else:
             self.SerialStatus = ('Serial port {}'.format(serialportname), "GreenLight.ico", do_nothing)  
        self.menu_options = (('WildCards Link', "wc_site_icon_filled.ico", do_nothing),
            self.ServerStatus,
            self.SerialStatus)             
        self._update_menu(self.menu_options)        

    def _update_menu(self, menu_options):
        self.WildsysTrayIcon.update(menu_options = menu_options)
        
    def bye(self, sysTrayIcon):
        self.Exiting = True

    def kill_systray(self):
        self.WildsysTrayIcon.shutdown    
        
        
    # menu_options = (('WildCards Link', "wc_site_icon_filled.ico", do_nothing),
                     # ServerStatus,
                     # SerialStatus)


    # WildsysTrayIcon = SysTrayIcon("wc_site_icon_filled.ico", hover_text, menu_options, on_quit=bye, default_menu_index=1)

    # SerialStatus = ('Serial port COM8', "RedLight.ico", do_nothing)

    # menu_options2 = (('WildCards Link', "wc_site_icon_filled.ico", do_nothing),
                     # ServerStatus,
                     # SerialStatus)



    # WildsysTrayIcon.update(menu_options = menu_options)


    # WildsysTrayIcon.start()