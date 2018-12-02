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
import time
import serial
from threading import Thread
import Wildcards_Logger # * as WildLogger

from Wildcards_Logger import *


class SerialPortChecker:
    """
    This class exists to check SerialPorts to see if they will open up
    successfully at the required communication frequency. If the attempt fails,
    then we know the port won't work, so we indicate that is it not available.
    
    When Auto_Enumerate() is invoked, the port availability status will be checked 
    once per second (typically).
    
    Requirements to operate:
    Need a SerialPort object passed in during initialization. Serial Port object
    must have 
    """
    def __init__(self, port=None):
        self._port = port
        self._checked = False
        self._running_check_now = False
        self._IsPortAvailable = False
        
        self._timetocheck = 0  #how long did it take to check the port?
        self._start = time.time()
        self._end = time.time()
        
        self._localworker = None
        self._localworker_loop = None

    @property
    def IsPortAvailable(self):
        return self._IsPortAvailable

    @property            
    def Checked(self):
        return self._checked
        

  
    def Auto_Enumerate(self):
        """
        This function kicks off port autoenumeration in a separate thread.
        It will poll once per second to see if the connected com ports
        are are devices running FirmataPlus

        :returns: Never returns, loops forever until program is exited
        """
        if self._localworker is None:
            worker_loop = asyncio.new_event_loop()
            worker = Thread(target=self._start_loop, args=(worker_loop,))
            worker.daemon = True  #ensure the threads are killed when the process ends
            # Start the thread
            worker.start()
            self._localworker = worker
            self._localworker_loop = worker_loop
            self._localworker_loop.call_soon_threadsafe(self._Keep_Checking_Port)

        # while True:
            # self._localworker_loop.call_soon_threadsafe(self._Check_Port)
            # await asyncio.sleep(1) #wait 1 second between checks at a minimum
            # while self._running_check_now == True:
                # await asyncio.sleep(1)    #if a serial port is taking a long time to check,
                                          # #keep sleeping until the previous check is complete
        
        

    def _start_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()             

    def _Keep_Checking_Port(self):
        while True:
            self._Check_Port()
            time.sleep(1)
            while self._running_check_now == True:
                time.sleep(1)   #if a serial port is taking a long time to check,
                                          #keep sleeping until the previous check is complete
    
    
    def _Check_Port(self): #checking to see if the port is available
        #print("Running CheckPort  {}   {}   {}".format(self._timetocheck, self._start, self._end))
        #print("checking port on {}".format(self.com_port))
        self._running_check_now = True
        if self._port.com_port is not None:
            #logstring("Running CheckPort on {}".format(self._port.com_port))
            if self._port.IsPortOpen == False:
            #only very infrequency check ports that take too long to check
                #they are likely throwing an OS error
                if (self._timetocheck < 0.3) or ((self._end + self._timetocheck * 100) < time.time()):
                    self._start = time.time()
                    try:
                        serialport = serial.Serial(self._port.com_port, self._port.speed, timeout=10)
                        serialport.close()
                        #logstring("Found ports {}...{}".format(self._port.com_port, self._timetocheck))
                        self._IsPortAvailable = True
                    except serial.SerialException as e:
                        #print("error number {}".format(e))
                        self._IsPortAvailable = False
                        pass
                    self._end = time.time()
                    if self._IsPortAvailable:
                        self._timetocheck = 0  #set to zero because checking a good port can take a few seconds, no need to penalize
                    else:
                        self._timetocheck = self._end - self._start
                    #print("time to check {} was {}".format(self.com_port, self._timetocheck))
            else:
                self._IsPortAvailable = True
        else:
            self._IsPortAvailable = False
        self._checked = True
        self._running_check_now = False

