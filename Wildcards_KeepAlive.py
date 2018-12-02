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
import time
import asyncio

class KeepAlive(WildcardsFirmataBaseObject):

    def __init__(self, ID):
        super().__init__(ID)
        
        self._interval = 0
        self._last_sent_interval = 0
        self._margin = 0.3
        self._last_ping = time.perf_counter()
        
        self.loop = asyncio.get_event_loop()
        self.the_task = self.loop.create_task(self._ping_keepalive())
        
    @property
    def interval(self):
        return self._interval
   
    @interval.setter
    def interval(self, interval):
        if isnumeric(interval):
            # bound the interval between 0 and 10 seconds, integer only
            if interval < 0:
                self._interval = 0
            if interval > 10:
                self._interval = 10
            self._interval = round_decimal(interval)
            if self._interval == self._last_sent_interval:
                self._to_be_written = False
            else:
                self._to_be_written = True
 

    @property
    def last_sent_interval(self):
        return self._last_sent_interval

    @property
    def last_ping(self):
        #last time of ping sent based on time.perf_counter()
        #subtract from time.perf_counter() to find time since last ping
        return self._last_ping

    @property    
    def margin(self):
        return self._margin

    @margin.setter
    def margin(self, margin = 0.3):
        if isnumeric(margin):
            # bound the interval between 0 and 10 seconds, integer only
            if margin < 0.1:
                self._interval = 0.1
            if margin > 0.9:
                self._interval = 0.9
            self._margin = round_decimal(margin, 1)

    def generate_byte_string(self):
        output = ""
        if self._to_be_written == True:
            #creates the byte string and resets the to_be_written state
            output = WrapSysEx(KEEP_ALIVE + To7BitBytes(self._interval, 2))
            self._last_sent_interval = self._interval
            #record this timestamp as the last time the keepalive was sent
            self._last_ping = time.perf_counter()
        return output

    async def _ping_keepalive(self):
        while True:
            if self._last_sent_interval > 0:
                if (time.perf_counter() - self._last_ping) < (self._last_sent_interval * self._margin):  
                    self._to_be_written = True
            #regardless, we can now sleep for a half second, 
            #which is guaranteed to be less than the minimum keepalive interval
            await asyncio.sleep(0.5)
