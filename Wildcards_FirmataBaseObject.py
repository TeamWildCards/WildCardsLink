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

import decimal
from constants import Constants
from private_constants import PrivateConstants
from Wildcards_Logger import *

class WildcardsFirmataBaseObject:
    """
    This class represents one "object" within firmata, which means that it can be queried for output,
    """
	

    def __init__(self, ID):
        """
        This is the "constructor" method for a basic WildcardsFirmataObject.
		"""
        self._ID = ID
        self._nested_objects = []
        #default boolean to track whether something needs to be written.
        #Derived classes may use alternative implementations
        self._to_be_written = False
	
		
    def generate_byte_string(self):
        """
        Creates the byte string for this object and any children objects
        """
        byte_string = ""
        #logstring("ID is {}".format(self._ID))
        for x in self._nested_objects:
            #logstring("ID is {}".format(x._ID))
            byte_string += x.generate_byte_string()
        self._to_be_written = False
        return byte_string
		
    @property
    def ID(self):
        return self._ID

    @property
    def to_be_written (self):
        return self._to_be_written
        
#some utility functions		

def WrapSysEx(bytestring):
    """
    Adds the leading and trailing bytes for all SysEx messages

    :param bytestring:  the message to be wrapped
    
    :returns: bytestring with the leading and trailing SysEx bytes added
    """
    return chr(PrivateConstants.START_SYSEX) + bytestring + chr(PrivateConstants.END_SYSEX)

def UnwrapSysEx(bytestring):
    """
    Removes leading and trailing bytes for all SysEx messages

    :param bytestring:  the message to be unwrapped
    
    :returns: bytestring with the leading and trailing SysEx bytes removed
    """
    return bytestring[1:-1]
    
def To7BitBytes(x, NumBytes=1):
    """
    Converts the numeric input into 7-bit bytes, little endian

    :param x:  value to convert
    :param NumBytes:  the lenght of the resulting bytestring
    
    :returns: byte string of length NumBytes
    """
    result = chr(x & 0x7f)
    for bytenum in range(1,NumBytes):
        result = result + chr((x >> bytenum*7) & 0x7f)
    return result
    
def round_decimal(x, digits = 0):
    """
    Performs traditonal rounding as taught in math classes

    :param x:  value to round
    :param digits:  the number of digits to the right of the
                    decimal to display (can be positive or negative)
    
    :returns: byte string of length NumBytes
    """
     
    #casting to string
    x = decimal.Decimal(str(x))
    #string in scientific notation for significant digits: 1e^x     
    string =  '1e' + str(-1*digits)
    #rounding for integers
    if digits <= 0:
        return int(x.quantize(decimal.Decimal(string), rounding='ROUND_HALF_UP'))
    else:
        return float(x.quantize(decimal.Decimal(string), rounding='ROUND_HALF_UP'))    

def valid_pin(pin, numpins):
    """
    Determines the validity of a submitted pin value. Checks for numeric, rounds to integer
    and ensures it is within bounds of 0 to numpins-1.

    :param x:  value to pin to check

    :returns: pin number if valid. Otherwise, returns False
    """
    rnumpins = round_decimal(numpins)
    if rnumpins < 0:
        raise ValueError("Number of pins must be positive, "
                         "but {} was provided".format(rnumpins))

    rpin = round_decimal(pin)
    if rpin >= 0 and rpin < rnumpins:
        return rpin
    else:
        raise ValueError("Pin number must be between 0 and {}".format(rnumpins))


def valid_port(port, numports):
    """
    Determines the validity of a submitted port value. Checks for numeric, rounds to integer
    and ensures it is within bounds of 0 to numports-1.

    :param x:  value to port to check

    :returns: port number if valid. Otherwise, rasies an error
    """
    rnumports = round_decimal(numports)
    if rnumports < 0:
        raise ValueError("Number of ports must be positive, "
                         "but {} was provided".format(numports))
  

    rport = round_decimal(port)
    if rport >= 0 and rport < rnumports:
        return rport
    else:
        raise ValueError("Port number must be between 0 and {}".format(rnumports))
