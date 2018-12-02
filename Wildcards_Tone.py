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

class Tone(WildcardsFirmataBaseObject):

    def __init__(self, ID, numpins):
        super().__init__(ID)

        self._numpins = numpins
        
        self._playtone = False
        self._pin_number = 0
        self._frequency = 0
        self._duration = None
        
        self._stoptone = False
        self._stop_tone_on_pin = 0
        
        self._last_sent_pin_number = 0
        self._last_sent_frequency = 0
        self._last_sent_duration = None

    def play_tone(self, pin_number, frequency=440, duration=0):
        if (frequency == 0):  #route to stoptone instead
            self.stop_tone(pin_number)
        else:     
            self._pin_number = round_decimal(pin_number)
            self._frequency = round_decimal(frequency)
            self._duration = round_decimal(duration)
            self._playtone = True
    #presently, FirmataPlus doesn't track that tone() changes
    #the pin mode to output. This may be an area for future 
    #improvement
                    
                    
    def stop_tone(self, pin_number):
        #at least for Wildcards/Arduino, it only makes sense to stop the 
        #tone on the last pin, because only one tone can be played at a time
        if isnumeric(pin_number) and (pin_number == self._last_sent_pin_number):
                self._pin_number = pin_number
                #internal setting to determine what to write
                self._stoptone = True
                self._playtone = False #if stop tone was called, then don't play a tone
                                       #unless play_tone is called specifically afterwards

    @property
    def pin_number(self):
        return self._pin_number

    @property
    def frequency(self):
        return self._frequency

    @property
    def duration(self):
        return self._duration

    @property
    def last_sent_pin_number(self):
        return self._last_sent_pin_number

    @property
    def last_sent_frequency(self):
        return self._last_sent_frequency

    @property
    def last_sent_duration(self):
        return self._last_sent_duration
        
    @property
    def to_be_written (self):
        return self._stoptone or self._playtone   
    
    def generate_byte_string(self):
        output = ""
        if self._stoptone == True:
            output += WrapSysEx(chr(PrivateConstants.TONE_DATA) + 
                                chr(Constants.TONE_NO_TONE) +
                                To7BitBytes(self._pin_number))
            self._stoptone = False
        if self._playtone == True:
            output += WrapSysEx(chr(PrivateConstants.TONE_DATA) + 
                                chr(Constants.TONE_TONE) +
                                To7BitBytes(self._pin_number) + 
                                To7BitBytes(self._frequency, 2) +   
                                To7BitBytes(self._duration, 2)) 
            self._last_sent_pin_number = self._pin_number
            self._last_sent_frequency = self._frequency
            self._last_sent_duration = self._duration                      
            self._playtone = False                               
        return output