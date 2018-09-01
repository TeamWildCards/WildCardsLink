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
from Wildcards_serial import WildCardsSerial
from Wildcards_Firmata import WildcardsFirmata
from Wildcards_Server import WildServer

class WildCardsMain:
    def __init__(self):
        
        self.Exiting = False
        #initialize the System Tray icon for WildCards Link
        #self.WildUI = None
        self.WildUI = WildCardsUserInterface(parent=self)

        #set up the server on default port
        #self.WildServer = WildCardsServer()

        #set up the serial link to Firmata        
        self.WildSerial = None
        self.WildSerial = WildCardsSerial(parent=self) 
        self.WildFirmata = WildcardsFirmata(parent=self)

        loop.create_task(self.CheckForNewUserInputs())
        
        self.server = WildServer(self.WildFirmata)
        start_server = websockets.serve(self.server.get_message, '127.0.0.1', 9000)
        
        self._new_serial_port = None

        print("server set up...")
        loop.run_until_complete(start_server)
        print("got past the run until complete...")
 
    def StartSerial(self):
        self.WildSerial.StartService()
        
    async def CheckForNewUserInputs(self):
        #last_serial_port = self._new_serial_port
        #print("1last {}   new  {}".format(last_serial_port, self._new_serial_port))
        #await asyncio.sleep(0.01, loop=loop)
        while True:
            if self.WildUI.Exiting:
                if self.Exiting is False:
                    self.Exiting = True
                    _signal_handler(1,1)
            print("2last {}   new  {}".format(self.WildSerial.com_port, self._new_serial_port))
            if (self._new_serial_port is not None):
                print("last {}   new  {}".format(self.WildSerial.com_port, self._new_serial_port))
                #last_serial_port = self._new_serial_port
                print("starting an await")
                await self.WildSerial.OpenNamedSerialPort(self._new_serial_port)
                print("ending an await")
                self._new_serial_port = None
            await asyncio.sleep(0.1, loop=loop)
            #print("4last {}   new  {}".format(last_serial_port, self._new_serial_port))
            
    async def SerialOpened(self):
        """ called by Wildcards_serial """
        print("got to SerialOpened1")
        self.WildUI.UpdateCurrentPort(self.WildSerial.CurrentPort.com_port)
        print("got to SerialOpened2")
        self.WildUI.UpdateCurrentPortStatusGood(True)
        print("got to SerialOpened3")
        await self.WildFirmata.assign_serial_port(self.WildSerial.CurrentPort)
        print("got to SerialOpened3")
        
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
        print("selecting main port now: {}".format(portname))
        self._new_serial_port = portname
        print("selected main port now: {}".format(portname))
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

 usage: pymata_iot.py [-h] [-host HOSTNAME] [-port PORT] [-wait WAIT]
                 [-comport COM] [-sleep SLEEP] [-log LOG]

    optional arguments:
      -h, --help      show this help message and exit
      -host HOSTNAME  Server name or IP address
      -port PORT      Server port number
      -wait WAIT      Arduino wait time
      -comport COM    Arduino COM port
      -sleep SLEEP    sleep tune in ms.
      -log LOG        True = send output to file, False = send output to console
      -ardIPAddr ADDR Wireless module ip address (WiFly)
      -ardPort PORT   Wireless module ip port (Wifly)
      -handshake STR  Wireless device handshake string (WiFly)
"""

parser = argparse.ArgumentParser()
parser.add_argument("-host", dest="hostname", default="localhost", help="Server name or IP address")
parser.add_argument("-port", dest="port", default="9000", help="Server port number")
parser.add_argument("-wait", dest="wait", default="2", help="Arduino wait time")
parser.add_argument("-comport", dest="com", default="None", help="Arduino COM port")
parser.add_argument("-sleep", dest="sleep", default=".001", help="sleep tune in ms.")

args = parser.parse_args()

if args.com == 'None':
    comport = None
else:
    comport = args.com


###remove this later
def _signal_handler(sig, frame):

    loop.create_task(loop.shutdown_asyncgens())
    #MainObject.ShutdownUI()
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
    #print('\nFinished Cleaning Up, Bye!')
    

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

loop = asyncio.get_event_loop()

logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.basicConfig(level=logging.DEBUG) 


fh = logging.FileHandler('spam.log')
fh.setLevel(logging.DEBUG)
loop.set_debug(True)

try:



    MainObject = WildCardsMain()
    #loop.create_task(MainObject.statusprinter())
    loop.create_task(MainObject.SystrayExitChecker())
    MainObject.StartSerial()
    #loop.create_task(MainObject.statusprinter())
    #loop.create_task(MainObject.SystrayExitChecker())
    loop.run_forever()
    
    MainObject.ShutdownUI()
    sys.exit()
    print("neverseethis")
except serial.serialutil.SerialException:
    print('problem closing the loop')
    MainObject.ShutdownUI()  
    sys.exit()
except RuntimeError:
    print('got here1')
    MainObject.ShutdownUI()  
    sys.exit()
	