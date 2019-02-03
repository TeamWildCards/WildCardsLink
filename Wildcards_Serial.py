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
import sys
#import logging
import glob
import time
import concurrent.futures
from threading import Thread
from itertools import cycle
import serial.tools.list_ports
from Wildcards_SerialPort import SerialPort

from Wildcards_Logger import *

class WildCardsSerial:

    def __init__(self, parent=None, com_port=None, speed=57600, sleep_tune=.5):
        """
        This is the constructor for the aio serial handler

        :param com_port: Com port designator
        :param speed: baud rate
        :return: None
        """
        self._parent = parent
        self._portlist = []
        self.com_port = com_port  #stores the com port recommended by the user
        self.sleep_tune = sleep_tune
        self.speed = speed
        self.CurrentPort = None
        self.Ports = []
        sys.stdout.flush()
        self.ReadBuffer = []

        # if MAC get list of ports
        if sys.platform.startswith('darwin'):
            self.locations = glob.glob('/dev/tty.[usb*]*')
            self.locations = glob.glob('/dev/tty.[wchusb*]*') + self.locations
            self.locations.append('end')
        # for everyone else, here is a list of possible ports
        else:
            self.locations = ['dev/ttyACM0', '/dev/ttyACM0', '/dev/ttyACM1',
                         '/dev/ttyACM2', '/dev/ttyACM3', '/dev/ttyACM4',
                         '/dev/ttyACM5', '/dev/ttyUSB0', '/dev/ttyUSB1',
                         '/dev/ttyUSB2', '/dev/ttyUSB3', '/dev/ttyUSB4',
                         '/dev/ttyUSB5', '/dev/ttyUSB6', '/dev/ttyUSB7',
                         '/dev/ttyUSB8', '/dev/ttyUSB9',
                         '/dev/ttyUSB10',
                         '/dev/ttyS0', '/dev/ttyS1', '/dev/ttyS2',
                         '/dev/tty.usbserial', '/dev/tty.usbmodem', 'com2',
                         'com3', 'com4', 'com5', 'com6', 'com7', 'com8',
                         'com9', 'com10', 'com11', 'com12', 'com13',
                         'com14', 'com15', 'com16', 'com17', 'com18',
                         'com19', 'com20', 'com21', 'com1', 'end'
                         ]
        if (com_port not in self.locations) and com_port is not None:
            #logstring("Adding comport: {}".format(self.locations))
            self.locations.insert(0,com_port)
        myports = [comport.device for comport in serial.tools.list_ports.comports()]
        for myport in myports:
            if myport.lower() not in self.locations:
                #logstring("Adding found comport: {}".format(myport.lower()))
                self.locations.insert(0,myport.lower())        
        
        #logstring("all locations: {}".format(self.locations))
        
        #We will want to go back and add something to check for new com ports on request (remember the com22 issue, wasn't in list)
          
        detected = None

        for device in self.locations:
            self.Ports.append(SerialPort(self, device))
        #logstring("Starting service")
        self.StartService() #does this go here?
            
    def IsCurrentPortOpen(self):
        if self.CurrentPort is not None:
            return self.CurrentPort._IsPortOpen

    def IsCurrentPortAvailable(self):
        if self.CurrentPort is not None:
            return self.CurrentPort.IsPortAvailable
    
    def DidCurrentPortHaveError(self):
        if self.CurrentPort is not None:
            return self.CurrentPort.had_error
            
    def AppendToPortList(self, portname):
        self._portlist.append(portname)
        #logstring("appending to port list {}".format(portname))
        self._parent.UpdatePortList(self._portlist)
            
    def RemoveFromPortList(self, portname):
        self._portlist.remove(portname)
        logstring("Updating port list {}".format(self._portlist))
        self._parent.UpdatePortList(self._portlist)

    async def PortOpened(self):
        await self._parent.SerialOpened()
        
    def PortClosed(self, com_port):
        self._parent.SerialClosed()
        
    async def OpenNamedSerialPort(self, portname, clear_port_error_status = True):
        logstring("Opening port {}".format(portname))
        if portname not in self.locations: #add to locations if it isn't already in there
            self.locations.insert(0, portname)
            self.Ports.append(Port(self, portname))
        
        for x in self.Ports:  #find the requested port in the list of ports
            if x.com_port == portname:
                PortToOpen = x
                
        #now that it is in the port list, we wait for it to become available
        if not PortToOpen.HasBeenCheckedForAvailability: #wait for avaialability checks to complete if needed
            await asyncio.sleep(self.sleep_tune)
            
        if clear_port_error_status == True:
            PortToOpen.had_error = False
            
        if (PortToOpen.IsPortAvailable) and (PortToOpen.had_error == False): #port is available and operational 
            logstring("Port is available without error")
            if self.CurrentPort is None:
                self.CurrentPort = PortToOpen #assign the requested port as the current port
                logstring("No current port, so opening the port now...")
                await self.CurrentPort.open()  #and open the requested serial port     
            else:
                logstring("There is a CurrentPort already")
                if (self.CurrentPort.IsPortOpen == False):
                    logstring("but it is not open so opening the new port now...")
                    self.CurrentPort = PortToOpen #switch to the requested port
                    await self.CurrentPort.open()  #and open the requested serial port   
                else:
                    if self.CurrentPort.com_port != portname: #CurrentPort is a different port than we want
                        logstring("but it is a different port than desired so close it and open the correct port")
                        self.CurrentPort.close()    #so close it
                        self.CurrentPort = PortToOpen #switch to the requested port
                        await self.CurrentPort.open()  #and open the requested serial port
                    #otherwise, we already have the requested port open, so ignore
        # If the port isn't available, or has failed due to an error, there is nothing we can do to open it        
    
    async def NextAvailablePort(self): #returns the name of the next available port
        HasLogstringChanged = True
        while True:
            if self.CurrentPort is None:
                if self.Ports is not None:
                    for x in self.Ports:
                        if x.IsPortAvailable and x.had_error == False:
                            HasLogstringChanged = True
                            return x
            else:
                
                FoundCurrentPort = False
                #loop through all valid ports after the currently-selected one
                for x in self.Ports:
                    if x.com_port == self.CurrentPort.com_port:
                        FoundCurrentPort = True
                    else:
                        if FoundCurrentPort:
                            if x.IsPortAvailable and x.had_error == False:
                                HasLogstringChanged = True
                                return x
                #loop through all ports, skipping only the one we are currently on. 
                for x in self.Ports:
                    if x.IsPortAvailable and x.had_error == False:
                            return x    
            if HasLogstringChanged:
                logstring("No available ports; waiting")
            HasLogstringChanged = False
            
            await asyncio.sleep(0.5)  #keep waiting for an available, non-erroneous port to show up        
        
    # async def KeepTryingToOpenSerialPorts(self):
        # #loop through available ports, trying them out
        # #only try the ones that don't have a history of errors
        # while True:
            # logstring("KeepingTryingToOpenSerialPorts {}".format(self.CurrentPort))
            # if (self.CurrentPort is not None):
                # if self.CurrentPort.IsPortOpen == True: #we already have an open port, nothing to do
                    # await asyncio.sleep(1)
                    # logstring("Finished sleeping in KTTOSP1")
                # else:
                    # myport = await self.NextAvailablePort()
                    # logstring("Got the next available port as {}".format(myport.com_port))
                    # await self.OpenNamedSerialPort(myport.com_port, clear_port_error_status = False)      
                    # logstring("Finished sleeping in KTTOSP2")
            # else: #the current port was None
                # myport = await self.NextAvailablePort()
                # logstring("Got the next available port from None as {}".format(myport.com_port))
                # await self.OpenNamedSerialPort(myport.com_port, clear_port_error_status = False)    
                # logstring("Finished opening Names Serial Port")
            # logstring("waiting2")
            # await asyncio.sleep(1)
            # logstring("Finished sleeping in KTTOSP3")
            
    async def KeepTryingToOpenSerialPorts(self):
        #loop through available ports, trying them out
        #only try the ones that don't have a error history
        HasLogstringChanged = True
        while True:
            if (self.CurrentPort is not None):
                if self.CurrentPort.IsPortOpen == True: #we already have an open port, nothing to do
                    if HasLogstringChanged:
                        logstring("Port {} is Open".format(self.CurrentPort.com_port), self)
                    HasLogstringChanged = False
                    await asyncio.sleep(1)
                else:
                    HasLogstringChanged = True
                    logstring("Port {} is NOT Open".format(self.CurrentPort.com_port, self.CurrentPort.IsPortOpen))
                    myport = await self.NextAvailablePort()
                    logstring("Next Available Port is {}".format(myport.com_port))
                    await self.OpenNamedSerialPort(myport.com_port, clear_port_error_status = False)  
            else: #the current port was None
                HasLogstringChanged = True
                myport = await self.NextAvailablePort()
                logstring("Next Available Port is {}".format(myport.com_port))
                await self.OpenNamedSerialPort(myport.com_port, clear_port_error_status = False)
            await asyncio.sleep(1)
 
    def StartService(self):
        loop = asyncio.get_event_loop()
        logstring("Creating task to find and open serial ports")
        loop.create_task(self.KeepTryingToOpenSerialPorts())
        loop.create_task(self.Auto_Reader())
        
    async def Auto_Reader(self):
        """
        
        This polls the com port continuously for updates and store the result in ReadBuffer

        :returns: Never returns, loops forever until program is exited
        """
        while True:
            if (self.CurrentPort is not None):
                myresult = await self.CurrentPort.read()
                #logstring("reading from port again: {}".format(myresult))
                if myresult is not None:
                    #logstring("found a char: {}".format(myresult))
                    self.ReadBuffer.append(myresult)
            else:
                logstring("No active port connected; nothing to do")
                await asyncio.sleep(0.2)