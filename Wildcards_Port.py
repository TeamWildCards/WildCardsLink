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


from Wildcards_FirmataBaseObject import *
from constants import Constants
from private_constants import PrivateConstants
from Wildcards_Pin import Pin


class Port(WildcardsFirmataBaseObject):

    def __init__(self, ID, PortNum):
        super().__init__(ID)

        self.pins = []
        self._last_sent_value = 0
        self._mode = Constants.INPUT
        self._last_sent_mode = Constants.INPUT
        self._isI2Cenabled = False

        self._need_to_send_digital_reporting = False 

        self._PortNum = valid_port(PortNum, 16)

        self._report_digital = 0        
        self.last_sent_report_digital = 0
        
        #timestamp messages as they are received for comparison purposes?
        
    def enable_digital_reporting(self, value):
        self._report_digital = 1
        self._need_to_send_digital_reporting = True
     
    def disable_digital_reporting(self):
        self._report_digital = 0
        if  self._report_digital == self._last_sent_report_digital:
            self._need_to_send_digital_reporting = False
        else:
            self._need_to_send_digital_reporting = True        
            
    def DigitalWrite(self, value):  #writes an entire port of 1s and 0s at once
        for i, pin in enumerate(self.pins):
            pin.DigitalWrite((value >> i) & 0x01)

    @property
    def to_be_written(self):
        return self._need_to_send_digital_reporting
        

    def generate_byte_string(self):
        """
        Creates the byte string for this object and any children objects
        """
        byte_string = ""
        need_to_perform_digital_write = False
        digital_value_to_write = 0
        digital_reporting = self._report_digital  #if the port has digital reporting turned on, then report digital
        for pin in self.pins:
            if pin.need_to_perform_digital_write:
                need_to_perform_digital_write = True
            if pin.need_to_send_digital_reporting:
                self._need_to_send_digital_reporting = True
                #logstring("looks like we need to send digital reporting...")
            if pin.DigitalReportingEnabled:  #if any of the pins have digital reporting turned on, then report digital
                #logstring("digital reporting is true!")
                digital_reporting = 1
            byte_string += pin.generate_byte_string()


        if need_to_perform_digital_write:
            byte_to_write = 0
            for i, pin in enumerate(self.pins):
                if pin.value:
                    byte_to_write += (1 << i)
            byte_string += chr(PrivateConstants.DIGITAL_MESSAGE + (0x0F & self._PortNum)) + \
                               To7BitBytes(byte_to_write, 2)  
                               
        if self._need_to_send_digital_reporting:
            byte_string += chr(PrivateConstants.REPORT_DIGITAL + (0x0F & self._PortNum)) + \
                               To7BitBytes(digital_reporting)              
        self._need_to_send_digital_reporting = False
        
        return byte_string
