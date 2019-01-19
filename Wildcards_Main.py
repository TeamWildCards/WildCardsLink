#!/usr/bin/env python#!/usr/bin/env python

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

import asyncio
import datetime
import json
import sys
import signal
import argparse
import websockets
import time
import logging

from easygui import *
#from pymata_aio.constants import Constants
#from pymata_aio.pymata_core import PymataCore
from serial import SerialException
import serial
from Wildcards_UserInterface import WildCardsUserInterface
from Wildcards_Serial import WildCardsSerial
from Wildcards_Firmata import WildcardsFirmata
from Wildcards_Server import WildServer
#import Wildcards_Logger
from Wildcards_Logger import *

class WildCardsMain:
    def __init__(self):

        self.Exiting = False
        self.has_active_server = False
        self.start_server = None
        #initialize the System Tray icon for WildCards Link
        self.WildUI = WildCardsUserInterface(parent=self)

        #set up the serial link to Firmata        
        self.WildSerial = None
        self.WildSerial = WildCardsSerial(parent=self) 
        self.WildFirmata = WildcardsFirmata(parent=self)

        loop.create_task(self.CheckForNewUserInputs())
        
        self.server = WildServer(parent=self, my_firmata=self.WildFirmata)

        self._new_serial_port = None
        
        loop.create_task(self.KeepServerAlive())
        loop.create_task(self.WildFirmata.write_continuously())

 
    def StartSerial(self):
        self.WildSerial.StartService()
        
    async def KeepServerAlive(self):
        self.server.portnumber = serverport
        if self.start_server is None:
            self.start_server = websockets.serve(self.server.get_message, '127.0.0.1', serverport)
        try:
            await asyncio.gather(self.start_server, loop=loop)
            logstring("Server listining on port {}".format(serverport))
            self.ServerListening(serverport)
        except:
            logstring("Error setting up server")
            pass
            
    def ServerListening(self, portnumber):
        self.WildUI.UpdateServerPort(portnumber)
        self.WildUI.UpdateServerStatusGood(True)
        
    async def CheckForNewUserInputs(self):
        while True:
            if self.WildUI.Exiting:
                if self.Exiting is False:
                    self.Exiting = True
                    _signal_handler(1,1)

            if (self._new_serial_port is not None):
                await self.WildSerial.OpenNamedSerialPort(self._new_serial_port)
                self._new_serial_port = None
            await asyncio.sleep(0.1, loop=loop)
            
    async def SerialOpened(self):
        """ called by Wildcards_serial """
        self.WildUI.UpdateCurrentPort(self.WildSerial.CurrentPort.com_port)
        self.WildUI.UpdateCurrentPortStatusGood(True)
        await self.WildFirmata.assign_serial_port(self.WildSerial)  #this WildSerial will have a CurrentPort object

    def SerialClosed(self):
        self.WildUI.UpdateCurrentPort(None)
        self.WildUI.UpdateCurrentPortStatusGood(False)
        self.WildFirmata.remove_serial_port()
                
    def UpdatePortList(self, portlist):
        self.WildUI.UpdatePortList(portlist)
        
    def UpdateCurrentSerialPort(self, port):
        self.WildUI.UpdateCurrentPort(port)
        
    def UpdateCurrentPortStatusGood(self, status):
        self.WildUI.UpdateCurrentPortStatusGood(status)
        
    def SelectUserSpecifiedPort(self, portname):
        """
        This is a called by the user interface.
        This method instructs the serial port to use the specified port name.
        Once the serial part has established a good connection, it *should* 
        eventually result in a call to self.WildUI.UpdateCurrentPort

        :param portname:  the name of the port that has been selected by the user
        :returns: No return value.
        """
        logstring("selecting main port now: {}".format(portname))
        self._new_serial_port = portname
        logstring("selected main port now: {}".format(portname))
        #loop.call_soon_threadsafe(self.SelectUserSpecifiedPort_Threadsafe(portname))
        

    def ShutdownUI(self):
        #print("ShutdownUI")
        if self.WildUI.Exiting is False:
            self.WildUI.Exiting = True
            self.WildUI.kill_systray()

    # async def statusprinter(self):
        # while True:
            # #print("Are we exiting ?  {}".format(self.WildUI.Exiting))
            # await asyncio.sleep(0.1)
            
    async def SystrayExitChecker(self):
        #print("SystrayExitChecker")
        while True:
            if self.WildUI.Exiting:
                if self.Exiting is False:
                    self.Exiting = True
                    _signal_handler(1,1)
            await asyncio.sleep(0.1)
"""

 usage: Wildcards_link.py [-h] [--host HOSTNAME] [--port PORT] [--wait WAIT]
                 [--comport COM] [--sleep SLEEP] [--verbose VERBOSE] [--log LOG]

    optional arguments:
      -h, --help           show this help message and exit
      --host HOSTNAME      Server name or IP address
      --port PORT          Server port number
      --wait WAIT          Arduino wait time
      --comport COM        Arduino COM port
      --sleep SLEEP        sleep tune in ms.
      -v --verbose VERBOSE send output to file      
      -l --logging LOG     send output to console
"""

parser = argparse.ArgumentParser()
parser.add_argument("--host", dest="hostname", default="localhost", help="Server name or IP address")
parser.add_argument("--port", dest="port", default="9000", help="Server port number")
parser.add_argument("--wait", dest="wait", default="2", help="Reset wait time in seconds")
parser.add_argument("--comport", dest="com", default="None", help="COM port")
parser.add_argument("--sleep", dest="sleep", default=".001", help="sleep tune in ms.")
parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="increase output verbosity")
parser.add_argument("-l", "--logging", dest="logging", action="store_true", help="log outputs to ./Wildcards.log")

args = parser.parse_args()

if args.com == 'None':
    comport = None
else:
    comport = args.com
    
serverport = args.port

    
    

#global_log_output = args.logging
#global_verbose = args.verbose    
#global_verbose = True            
#global_log_output = True

#last_logstring = ""

#Wildcards_Logger.setup_global_log_output(args.logging, args.verbose)
#Wildcards_Logger.setup_global_log_output(True, True)
setup_global_log_output(True, True)

#remove this later? only makes sense when run from console because this runs in the background

#catch WM_CLOSE for windows?
def _signal_handler(sig, frame):
    #schedule the closing of all asynchronous generator objects via calls to aclose()
    loop.create_task(loop.shutdown_asyncgens())

    try:
        loop.stop()
    except:
        pass
    try:
        loop.close()
    except:
        pass
    try:
        sys.exit()       
    except SystemExit:
        pass
    logstring('\nFinished Cleaning Up, Bye!')
    

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

loop = asyncio.get_event_loop()

'''
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.basicConfig(level=logging.DEBUG) 


fh = logging.FileHandler('spam.log')
fh.setLevel(logging.DEBUG)
loop.set_debug(True)
'''


try:



    MainObject = WildCardsMain()
    #loop.create_task(MainObject.statusprinter())
    loop.create_task(MainObject.SystrayExitChecker())
    logstring("I'm the one calling startserial")
    #MainObject.StartSerial()
    #loop.create_task(MainObject.statusprinter())
    #loop.create_task(MainObject.SystrayExitChecker())
    loop.run_forever()
    
    MainObject.ShutdownUI()
    sys.exit()
    logstring("neverseethis")
except serial.serialutil.SerialException:
    logstring('problem closing the loop')
    MainObject.ShutdownUI()  
    sys.exit()
except RuntimeError:
    logstring('got here1')
    MainObject.ShutdownUI()  
    sys.exit()
	