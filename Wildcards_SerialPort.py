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

from Wildcards_Logger import *
from Wildcards_SerialPortChecker import SerialPortChecker
import serial
import asyncio

class SerialPort:
    def __init__(self, parent, com_port, speed=57600, sleep_tune=.01):
        self._parent = parent
        self.com_port = com_port
        
        self.sleep_tune = sleep_tune
        self.speed = speed
        
        self._IsPortOpen = False

        
        #had_error indicates whether there was a write error or "this isn't Firmata" error
        #since the port was last available
        self.had_error = False
        self.my_serial = None
        
        self._SerialPortChecker = SerialPortChecker(self)
        self._SerialPortChecker.Auto_Enumerate()
        loop = asyncio.get_event_loop()
        loop.create_task(self._KeepAvailabilityUpToDate())
   
    @property
    def IsPortAvailable(self):
        return self._SerialPortChecker.IsPortAvailable

    @property
    def HasBeenCheckedForAvailability(self):
        return self._SerialPortChecker.Checked
        
    @property
    def IsPortOpen(self):
        return self._IsPortOpen
        
    # def _MarkPortAvailable(self):
        # if self.IsPortAvailable == False:
            # self.IsPortAvailable = True
            # self.had_error = False #no known errors so far
            # self._parent.AppendToPortList(self.com_port)
            
    # def _MarkPortUnavailable(self):
        # if self.IsPortAvailable:
            # self.IsPortAvailable = False
            # self._parent.RemoveFromPortList(self.com_port) 
        # if self._IsPortOpen:
            # self.my_serial.close()
            # self._MarkPortClosed()

    async def _MarkPortOpen(self):
        if self._IsPortOpen == False:
            logstring("Marking _IsPortOpen for port {}".format(self.com_port))
            self._IsPortOpen = True
            await self._parent.PortOpened()

    def _MarkPortClosed(self):
        if self._IsPortOpen == True:
            logstring("Marking _IsPortOpen as FALSE for port {}".format(self.com_port))    
            self._IsPortOpen = False
            self._parent.PortClosed(self.com_port)
            
    def get_serial(self):
        return self.my_serial

    async def _KeepAvailabilityUpToDate(self):
        lastknownstatus = self.IsPortAvailable
        while True:
            if lastknownstatus != self.IsPortAvailable:
                logstring("port availability chagned!!!!!!!!!")
                if self.IsPortAvailable:
                    logstring("reverting had_error back to false")
                    self.had_error = False #no known errors so far
                    self._parent.AppendToPortList(self.com_port)
                else:
                    self._parent.RemoveFromPortList(self.com_port) 
                    self.my_serial.close()
                    self._MarkPortClosed()
                lastknownstatus = self.IsPortAvailable
            await asyncio.sleep(0.1)    
            
    def write(self, data):
        """
        This is s call to pyserial write. It provides a
        write and returns the number of bytes written upon
        completion

        :param data: Data to be written
        :return: Number of bytes written
        """
        if self._SerialPortChecker.IsPortAvailable and self._IsPortOpen:
            result = None
            try:
                for d in data:
                    result = self.my_serial.write(bytes([ord(d)]))
                #result = self.my_serial.write(data.encode('utf-8'))
                #print('Wrote {} on {}!'.format(ord(data),self.com_port))
                    logstring('Wrote {} on {}!'.format(bytes([ord(d)]),self.com_port))
                #logstring('Wrote {} on {}!'.format(data.encode('utf-8'),self.com_port))
            except serial.SerialTimeoutException:
                try:
                    logstring("TimeoutError while writing")
                    self.had_error = True
                    self.my_serial.close()
                    self._MarkPortClosed()
                except:  
                    raise                
            except serial.SerialException:
                try:
                    logstring("SerialException while writing")
                    self.had_error = True
                    self.my_serial.close()
                    self._MarkPortClosed()
                except:  
                    raise
            if result:
                return result
        else:
            logstring("not going to write {}".format(data))
            #pass
                
  
    async def read(self):
        """
        This is performs a read if there is any data waiting
        Otherwise it will return None and perform a brief sleep along the way

        :return: One character
        """

        # wait for a character to become available and read from
        # the serial port
        if (self.my_serial is not None) and self._SerialPortChecker.IsPortAvailable and self._IsPortOpen:
            #logstring("attempting a read: is it inwaiting? {}".format(self.my_serial.inWaiting()))
            try:            
                if not self.my_serial.inWaiting():
                    #logstring("inWaiting is false, so sleeping for a bit..")
                    await asyncio.sleep(self.sleep_tune)
                    return None
                else:
                    data = self.my_serial.read()
                    return ord(data)
            except serial.SerialException:
                try:
                    self.had_error = True
                    self.my_serial.close()
                    self._MarkPortClosed()
                    return None
                except:  
                    raise
        else:
            await asyncio.sleep(self.sleep_tune)
            return None

    
    def close(self):
        """
        Close the serial port
        """
        if self._SerialPortChecker.IsPortAvailable and self._IsPortOpen:
            self.my_serial.close()
            logstring("Closing up port {}".format(self.com_port))
            self._MarkPortClosed()

    async def open(self):
        """
        Open the serial port
        """
        logstring("Yay, we're in the CurrentPort, about to open it  {}     {}".format(self._SerialPortChecker.IsPortAvailable, self._IsPortOpen))
        
        if self.IsPortAvailable and (self._IsPortOpen == False):
            logstring("iT IS AVAILable and not already open")
            self.my_serial = serial.Serial(self.com_port, self.speed, timeout=1, writeTimeout=1)
            #self.my_serial.open()
            logstring("Opening up port {} and clearing input output buffers".format(self.com_port))
            
            self.my_serial.reset_output_buffer()
            self.my_serial.reset_input_buffer()
            self._parent.com_port = self.com_port
            self.had_error = False
            await self._MarkPortOpen()


    def set_dtr(self, state):
        """
        Set DTR state
        :param state: DTR state
        """
        self.my_serial.setDTR(state)
            