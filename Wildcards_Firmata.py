"""
 Copyright (c) 2015-2017 Alan Yorinks All rights reserved.
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
import glob
#import logging
import sys
import time
import decimal
import math
import serial
import inspect

from constants import Constants
from pin_data import PinData
from private_constants import PrivateConstants
from Wildcards_FirmataBaseObject import *
from Wildcards_Serial import WildCardsSerial
from Wildcards_Pin import Pin
from Wildcards_Port import Port
from Wildcards_Tone import Tone
from Wildcards_KeepAlive import KeepAlive

from Wildcards_Logger import *
#from Wildcards_I2C import I2C

class WildcardsFirmata(WildcardsFirmataBaseObject):
    """
    This class exposes and implements the Firmata-related management,
    It includes the public API methods as well as
    a set of private methods.

    After instantiating this class, its "start" method MUST be called to
    perform Arduino pin auto-detection.
    """

    def __init__(self, parent=None, arduino_wait=2, sleep_tune=0.001, baud_rate=57600):
        super().__init__("WildCardsFirmata")
        
        """
        This is the "constructor" method for the PymataCore class.

        If log_output is set to True, a log file called 'wildcards.log'
        will be created in the current directory and all output
        will be written to the log.


        :param arduino_wait: Amount of time to wait for Arduino to reset.
                             UNO takes 2 seconds, Leonardo can be zero
        :param sleep_tune: This parameter sets the amount of time to default 
                           for asyncio.sleep
        :param com_port: Manually selected com port - normally it is
                         auto-detected
        :param baud_rate: This parameter sets the bit rate for comms with Firmata
                           over the serial port

        :returns: This method never returns
        """
        
        self.gothere = False
                
        self._parent = parent
         
        self.baud_rate = baud_rate
        self.byte_rate = baud_rate / 8  #57600 bps = 7200 Bps
        
        self.sleep_tune = sleep_tune
        self.arduino_wait = arduino_wait

        self.hall_encoder = False

        # this dictionary for mapping incoming Firmata message types to
        # handlers for the messages
        self.command_dictionary = {PrivateConstants.REPORT_VERSION:
                                       self._report_version,
                                   PrivateConstants.REPORT_FIRMWARE:
                                       self._report_firmware,
                                   PrivateConstants.CAPABILITY_RESPONSE:
                                       self._capability_response,
                                   PrivateConstants.ANALOG_MAPPING_RESPONSE:
                                       self._analog_mapping_response,
                                   PrivateConstants.PIN_STATE_RESPONSE:
                                       self._pin_state_response,
                                   PrivateConstants.STRING_DATA:
                                       self._string_data,
                                   PrivateConstants.ANALOG_MESSAGE:
                                       self._analog_message,
                                   PrivateConstants.DIGITAL_MESSAGE:
                                       self._digital_message,
                                   PrivateConstants.I2C_REPLY:
                                       self._i2c_reply,
                                   PrivateConstants.SONAR_DATA:
                                       self._sonar_data,
                                   PrivateConstants.ENCODER_DATA:
                                       self._encoder_data,
                                   PrivateConstants.PIXY_DATA:
                                       self._pixy_data}



        logstring('Wildcards Link Version ' + \
                  PrivateConstants.WILDCARDS_VERSION)
        logstring(' Copyright (c) 2015-2017 Alan Yorinks All rights reserved.')
        logstring(' Copyright (c) 2018-2019 Dynamic Phase, LLC. All rights reserved.')


        self.sleep_tune = sleep_tune

        self._clear_stored_response_dictionaries()

        self._valid_target_exists = False
        
        self.loop = None
        self.the_task = None
        self.serial_port = None
        self.serial_manager = None

        self.keep_alive_interval = 0
        self.period = 0
        self.margin = 0
        

        # set up signal handler for controlC
        self.loop = asyncio.get_event_loop()
        self.the_task = self.loop.create_task(self._command_dispatcher())
        
    def generate_byte_string(self):
        return super().generate_byte_string()

    def _clear_stored_response_dictionaries(self):
        logstring("Clearing all responses")
        # report query results are stored in this dictionary
        self.query_reply_data = {PrivateConstants.REPORT_VERSION: '',
                                 PrivateConstants.STRING_DATA: '',
                                 PrivateConstants.REPORT_FIRMWARE: '',
                                 PrivateConstants.CAPABILITY_RESPONSE: None,
                                 PrivateConstants.ANALOG_MAPPING_RESPONSE: None,
                                 PrivateConstants.PIN_STATE_RESPONSE: None}

        # An i2c_map entry consists of a device i2c address as the key, and
        #  the value of the key consists of a dictionary containing 2 entries.
        #  The first entry. 'value' contains the last value reported, and
        # the second, 'callback' contains a reference to a callback function.
        # For example:
        # {12345: {'value': 23, 'callback': None}}
        self.i2c_map = {}

        # the active_sonar_map maps the sonar trigger pin number (the key)
        # to the current data value returned
        # if a callback was specified, it is stored in the map as well.
        # an entry in the map consists of:
        #   pin: [callback, [current_data_returned]]
        self.active_sonar_map = {}

        # The latch_map is a dictionary that stores all latches setup by
        # the user.
        # The key is a string defined as follows:
        #   Digital Pin : D + pin number (D12)
        #   Analog  Pin: A + pin number (A3)

        # The value associated with each key is a list comprised of:

        # [latched_state, threshold_type,
        #  threshold_value, latched_data, time_stamp]

        # latched_state: Each list entry contains a latch state,
        #                a threshold type, a threshold value value the data
        #                value at time of latching,  and a date stamp
        #                when latched.
        # A latch state:

        # LATCH_IGNORE = 0   # this item currently not participating in latching
        # LATCH_ARMED = 1    # When the next item value change is received and,
        #                    # if it matches the latch
        #                    # criteria, the data will be latched
        # LATCH_LATCHED = 2  # data has been latched. Read the data to
        #                    # re-arm the latch

        # threshold type:
        #     LATCH_EQ = 0  data value is equal to the latch threshold value
        #     LATCH_GT = 1  data value is greater than the latch
        #                   threshold value
        #     LATCH_LT = 2  data value is less than the latch threshold value
        #     LATCH_GTE = 3  data value is greater than or equal to the
        #                    latch threshold value
        #     LATCH_LTE = 4 # data value is less than or equal to the
        #                     latch threshold value

        # threshold value: target threshold data value

        # latched data value: value of data at time of latching event

        # time stamp: time of latching event

        # analog_latch_table entry = pin: [latched_state, threshold_type,
        #                            threshold_value, latched_data, time_stamp]
        # digital_latch_table_entry = pin: [latched_state, threshold_type,
        #                                   latched_data, time_stamp]

        self.latch_map = {}

        # The correct reader and writer methods will be set after
        # the serial port is assigned
        self.read = None
        self.write = None
        
        # a list of PinData objects - one for each pin segregate by pin type
        #these hold current values reported back, as well as callback functions
        self.analog_pins = []
        self.analog_pins_analog_numbering = []
        self.digital_pins = []
        self.pixy_blocks = []        
        

    def disconnect_port_due_to_error(self):
        self._parent.WildSerial.CurrentPort.had_error =  True
        self.remove_serial_port()
        
    def remove_serial_port(self):
        self._valid_target_exists = False
        #self.serial_port = None
        
        #clear ReadBuffer here too?
       
    async def assign_serial_port(self, serial_manager):
        """
        This method is called any time a new serial port is assumed to have
        a Firmata-based device running on it. It verifies whether there actually is
        a Firmata device based on the responses recieved.
        If it is not operating like a Firmata device, it is marked as having an error
        and ignored unless/until a new device is plugged into the serial port
        
        Future: possibly attempt to load firmata?
        :returns: No return value.
         """
        #logstring("you are now in assign_serial_port")
        if serial_manager is None:
            return
            
        if serial_manager.CurrentPort is None:
            return
                        
        self._clear_stored_response_dictionaries()

        self.serial_manager = serial_manager
        self.serial_port = serial_manager.CurrentPort   
        #to remove, only used for testing right now
        self.serial_port_name = serial_manager.CurrentPort.com_port
        
        # set the read and write handles
        self.read = self.serial_manager.CurrentPort.read
        self.write = self.serial_manager.CurrentPort.write

        self._valid_target_exists = True
        

        #keeps a direct reference to the pins
        self._digital_pins_directly = []
        self._analog_pins_directly = []
        
        #and ports
        self._ports_directly = []
        
        # wait for arduino to go through a reset cycle if need be
        logstring("Waiting for 2 seconds...")
        time.sleep(self.arduino_wait)
        #logstring("time is up!")
        #await asyncio.sleep(self.arduino_wait)

        # register the get_command method with the event loop
        self.loop = asyncio.get_event_loop()

        logstring("Setting up Firmata on port {}".format(self.serial_port.com_port))

        # get arduino firmware version and print it
        logstring("Checking Firmware version")
        firmware_version = await self.get_firmware_version()
        logstring("Finished checking Firmware version")
        if not firmware_version:
            logerr('*** Firmware Version retrieval timed out. ***')
            logerr('Firmata not found')
            try:
                # attempt to autoload firmata here, if fails again, mark the port as error
                self.disconnect_port_due_to_error()
                return
            except RuntimeError:
                self.disconnect_port_due_to_error()
                return
            except TypeError:
                self.disconnect_port_due_to_error()
                return
        logstring("\nFirmware ID: " + firmware_version)
        logstring("On port {}".format(self.serial_port_name))
        # get an analog pin map

        # try to get an analog report. if it comes back as none - shutdown
        # report = await self.get_analog_map()
        logstring("Fetching analog mapping")
        analogreport = await self.get_analog_map()
        #logstring("got analog map")
        if not analogreport:
            logerr('*** Analog map retrieval timed out. ***')
            logerr('Analog Pin Mapping not found')
            try:
                # attempt to autoload firmata here, if fails again, mark the port as error
                self.disconnect_port_due_to_error()
                return
            except RuntimeError:
                self.disconnect_port_due_to_error()
                return
            except TypeError:
                self.disconnect_port_due_to_error()
                return
                
        capabilityreport = await self.get_capability_report()
        if not capabilityreport:
            logerr('*** Capability Report retrieval timed out. ***')
            logerr('Capability Report not found')
            try:
                # attempt to autoload firmata here, if fails again, mark the port as error
                self.disconnect_port_due_to_error()
                return
            except RuntimeError:
                self.disconnect_port_due_to_error()
                return
            except TypeError:
                self.disconnect_port_due_to_error()
                return        
        # custom assemble the pin lists
        pininfo = iter(capabilityreport)
        
        
        self._nested_objects = []
        
        
        for i, analogpinmapping in enumerate(analogreport):
            #set up the data structure that captures data that comes from Firmata
            digital_data = PinData()
            self.digital_pins.append(digital_data)
            HasAnalog = False
            analog_data = PinData()
            self.analog_pins.append(analog_data)
            if analogpinmapping != Constants.IGNORE:
                self.analog_pins_analog_numbering.append(analog_data)
                HasAnalog = True
            #set up the data structure that captures data to be sent to Firmata
            port_num = math.floor(i/8)
            pin_num_within_port = i%8
            HasInput = False
            HasOutput = False
            HasPullup = False
            HasAnalog2 = False
            AnalogResolution = 0
            AnalogPinNum = 127
            HasPWM = False
            PWMResolution = 0
            HasI2C = False
            try:
                nextbyte = next(pininfo)
                while nextbyte != 127:  #127 signals the end of the information for a pin
                    resolutionbyte = next(pininfo)
                    if nextbyte == Constants.INPUT:
                        HasInput = True
                    if nextbyte == Constants.OUTPUT:
                        HasOutput = True
                    if nextbyte == Constants.PULLUP:
                        HasPullup = True
                    if nextbyte == Constants.ANALOG:
                        HasAnalog2 = True 
                        AnalogResolution = resolutionbyte
                        AnalogPinNum = analogpinmapping
                    if nextbyte == Constants.PWM:
                        HasPWM = True,
                        PWMResolution=14
                    if nextbyte == Constants.SERVO:
                        pass
                        #nothing to do. we treat it like an OUTPUT
                        #resolution is fixed...may do something with this
                        #in the future if there are issues with some platform?
                    if nextbyte == Constants.I2C:
                        HasI2C = True
                    nextbyte = next(pininfo)
            except StopIteration:
                pass
                
            if HasAnalog2 != HasAnalog:
                #this really shouldn't happen, but might as well catch it anyway
                raise Exception("The Analog Pin Map disagrees with the Capabilty Report as to whether pin {} is an analog pin".format(i))
            
            #this sets the pin number 0-7 within each port
            if pin_num_within_port == 0: #Yay, new port, create it:
                current_port = Port("Port {}".format(port_num),
                                                   port_num)
                self._nested_objects.append(current_port)
                self._ports_directly.append(current_port)
            
            newpin = Pin(ID = "Pin {} of Port {} hasanalog = {}".format(pin_num_within_port,
                                                                       port_num, HasAnalog),
                                       PinNum = i, HasInput=HasInput,
                                       HasPullup=HasPullup, HasOutput=HasOutput,
                                       HasAnalog=HasAnalog, AnalogPinNum=analogpinmapping,
                                       AnalogResolution=AnalogResolution, HasPWM=HasPWM,
                                       PWMResolution=PWMResolution, HasI2C=HasI2C)
            current_port.pins.append(newpin)
            self._digital_pins_directly.append(newpin)
            logstring("Appending a new pin {}   len {}".format(newpin._ID, len(self._digital_pins_directly)))
            if HasAnalog:
                self._analog_pins_directly.append(newpin)
                
            

        logstring('Auto-discovery complete. Found ' + \
                 str(len(self.digital_pins)) + ' Digital Pins and ' + \
                 str(len(self.analog_pins_analog_numbering)) + ' Analog Pins')

        self._numpins = len(self.digital_pins)
        self._numports = math.ceil(self._numpins/8)


        self.KeepAlive = KeepAlive("Keep Alive")
        self._nested_objects.append(self.KeepAlive)
        
        self.Tone = Tone("Tone", self._numpins)
        self._nested_objects.append(self.Tone)
        
        #self.EncoderConfig = EncoderConfig("Encoder Config", self._numpins)
        #self._nested_objects.append(self.EncoderConfig)
        

    def AssignSerialPort(self, port):
        self.SerialPort = port
        
    def analog_read(self, pin):
        """
        Retrieve the last data update for the specified analog pin.

        :param pin: Analog pin number (ex. A2 is specified as 2)
        :returns: Last value reported for the analog pin
        """
        return self.analog_pins_analog_numbering[pin].current_value

    def analog_write(self, pin, value):
        """
        Set the selected pin to the specified value. This will use ANALOG_MESSAGE if possible,
        but switch to extended analog sysex message if pin is out of range
        
        :param pin: PWM pin number
        :param value: Pin value (0 - 0x4000) or (0 - 16384). In PWM mode, this sets a duty cycle between 0 to 255. In Servo mode, when the values are 0-180, the units are degrees. Values up to 544 are maxed out at 180 degrees. Beyond 544, the units are microseconds of the pulse duration (typical guaranteed servo range is 1ms to 2ms, but often goes a bit beyond thaton either end)
        :returns: No return value
        """
        self._digital_pins_directly[pin].AnalogWrite(value)

    def digital_read(self, pin):
        """
        Retrieve the last data update for the specified digital pin.

        :param pin: Digital pin number
        :returns: Last value reported for the digital pin
        """
        self._digital_pins_directly[pin].PinStateQuery()
        return self.digital_pins[pin].current_value

    def digital_pin_write(self, pin, value):
        """
        Set the specified pin to the specified value directly without port manipulation.

        :param pin: pin number
        :param value: pin value
        :returns: No return value
        """

        self._digital_pins_directly[pin].DigitalWrite(value, PermitWriteToInputPin = False)

    def digital_write(self, pin, value):
        """
        Set the specified pin to the specified value.

        :param pin: pin number
        :param value: pin value
        :returns: No return value
        """
        #logstring("going for pin {} and value {} while pincount is {}".format(pin, value, len(self._digital_pins_directly)))
        self._digital_pins_directly[pin].DigitalWrite(value)
        #logstring("finished digital write")

    def digital_port_write(self, port, value):
        """
        Set the specified port to the specified value.

        :param port: port number
        :param value: port value
        :returns: No return value
        """
        self._ports_directly[port].DigitalWrite(value)
        
    def disable_analog_reporting(self, pin):
        """
        Disables analog reporting for a single analog pin.

        :param pin: Analog pin number. For example for A0, the number is 0.
        :returns: No return value
        """
        self._analog_pins_directly[pin].disable_analog_reporting()

    def disable_digital_reporting(self, pin):
        """
        Disables digital reporting. By turning reporting off for this pin,
        Reporting is disabled for all 8 bits in the "port"

        :param pin: Pin and all pins for this port
        :returns: No return value
        """
        port = pin // 8
        self._ports_directly[port].disable_digital_reporting()

    async def encoder_config(self, pin_a, pin_b, cb=None,
                             hall_encoder=False):
        """
        This command enables the rotary encoder support and will
        enable encoder reporting.

        This command is not part of StandardFirmata. For 2-pin + ground
        encoders, FirmataPlus is required to be used. For 2-pin rotary encoder,
        and for hall effect wheel encoder support, FirmataPlusRB is required.

        Encoder data is retrieved by performing a digital_read from pin a
        (encoder pin_a).

        When using 2 hall effect sensors (e.g. 2 wheel robot)
        specify pin_a for 1st encoder and pin_b for 2nd encoder.

        :param pin_a: Encoder pin 1.
        :param pin_b: Encoder pin 2.
        :param cb: callback function to report encoder changes
        :param hall_encoder: wheel hall_encoder - set to
                             True to select hall encoder support support.
        :returns: No return value
        """
        # checked when encoder data is returned
        self.hall_encoder = hall_encoder
        data = [pin_a, pin_b]
        if cb:
            self.digital_pins[pin_a].cb = cb

        await self._send_sysex(PrivateConstants.ENCODER_CONFIG, data)

    async def encoder_read(self, pin):
        """
        This method retrieves the latest encoder data value

        :param pin: Encoder Pin
        :returns: encoder data value
        """
        return self.digital_pins[pin].current_value

    def enable_analog_reporting(self, pin):
        """
        Enables analog reporting. By turning reporting on for a single pin,

        :param pin: Analog pin number. For example for A0, the number is 0.
        :returns: No return value
        """
        self._analog_pins_directly[pin].enable_analog_reporting()

    def enable_digital_reporting(self, pin):
        """
        Enables digital reporting. By turning reporting on for all 8 bits
        in the "port" - this is part of Firmata's protocol specification.

        :param pin: The pin for which reporting should be turned on. Firmata
                    will turn on reporting for the entire report, whether you 
                    like it or not. So it goes...
        :returns: No return value
        """
        port = pin // 8
        self._ports_directly[port].enable_digital_reporting()

    async def extended_analog(self, pin, data):
        """
        This method will send an extended-data analog write command to the
        selected pin.

        :param pin: 0 - 127
        :param data: 0 - 0xfffff
        :returns: No return value
        """
        analog_data = [pin, data & 0x7f, (data >> 7) & 0x7f, (data >> 14) & 0x7f]
        await self._send_sysex(PrivateConstants.EXTENDED_ANALOG, analog_data)

    async def get_analog_latch_data(self, pin):
        """
        A list is returned containing the latch state for the pin, the
        latched value, and the time stamp
        [latched_state, threshold_type, threshold_value,
         latched_data, time_stamp]

        :param pin: Pin number.
        :returns:  [latched_state, threshold_type, threshold_value,
                    latched_data, time_stamp]
        """
        key = 'A' + str(pin)
        if key in self.latch_map:
            entry = self.latch_map.get(key)
            return entry
        else:
            return None

    async def get_analog_map(self):
        """
        This method requests a Firmata analog map query and returns the results.

        :returns: An analog map response or None if a timeout occurs
        """
        # get the current time to make sure a report is retrieved
        current_time = time.time()

        # if we do not have existing report results, send a Firmata
        # message to request one
        if self.query_reply_data.get(
                PrivateConstants.ANALOG_MAPPING_RESPONSE) is None:
            logstring("Requesting analog mapping")
            await self._send_sysex(PrivateConstants.ANALOG_MAPPING_QUERY, None)
            # wait for the report results to return for 2 seconds
            # if the timer expires, leave empty handed
            while self.query_reply_data.get(
                    PrivateConstants.ANALOG_MAPPING_RESPONSE) is None:
                elapsed_time = time.time()
                if elapsed_time - current_time > 10:
                    return None
                await asyncio.sleep(self.sleep_tune)
        return self.query_reply_data.get(
            PrivateConstants.ANALOG_MAPPING_RESPONSE)

    async def get_capability_report(self):
        """
        This method requests and returns a Firmata capability query report

        :returns: A capability report in the form of a list
        """
        if self.query_reply_data.get(
                PrivateConstants.CAPABILITY_QUERY) is None:
            await self._send_sysex(PrivateConstants.CAPABILITY_QUERY, None)
            while self.query_reply_data.get(
                    PrivateConstants.CAPABILITY_RESPONSE) is None:
                await asyncio.sleep(self.sleep_tune)
        return self.query_reply_data.get(PrivateConstants.CAPABILITY_RESPONSE)

    async def get_digital_latch_data(self, pin):
        """
        A list is returned containing the latch state for the pin, the
        latched value, and the time stamp
        [pin_num, latch_state, latched_value, time_stamp]

        :param pin: Pin number.
        :returns:  [latched_state, threshold_type, threshold_value,
                   latched_data, time_stamp]
        """
        key = 'D' + str(pin)
        if key in self.latch_map:
            entry = self.latch_map.get(key)
            return entry
        else:
            return None

    async def get_firmware_version(self):
        """
        This method retrieves the Firmata firmware version

        :returns: Firmata firmware version
        """
        current_time = time.time()
        #logstring("setting current time {}".format(current_time))
        #logstring("1")
        if self.query_reply_data.get(PrivateConstants.REPORT_FIRMWARE) == '':
            #logstring("2")
            #logstring("checking time now 1 {}".format(time.time()))
            await self._send_sysex(PrivateConstants.REPORT_FIRMWARE, None)
            #logstring("checking time now 2 {}".format(time.time()))
            #logstring("3")
            if self.serial_port.IsPortOpen == False:
                #logstring("Looks like that port wasn't working!!!!!!!!!!!!!????")
                return None
            while self.query_reply_data.get(
                    PrivateConstants.REPORT_FIRMWARE) == '':
                #logstring("4")
                elapsed_time = time.time()
                #logstring("setting elapsed time {}".format(elapsed_time))
                #logstring("5")
                if elapsed_time - current_time > 3:
                    #logstring("really took too long:  {}  {}   {}".format(elapsed_time, current_time, elapsed_time - current_time))
                    return None
                #logstring("7")    
                if self.serial_port.IsPortOpen == False:
                    #logstring("Looks like that port wasn't working!!!!!!!!!!!!!")
                    return None
                await asyncio.sleep(self.sleep_tune)
                #logstring("8")
            #logstring("Geez, that took:  {}  {}   {}        ??????????????????".format(elapsed_time, current_time, elapsed_time - current_time))
                
        reply = ''
        #logstring("9")
        for x in self.query_reply_data.get(PrivateConstants.REPORT_FIRMWARE):
            reply_data = ord(x)
            if reply_data:
                reply += chr(reply_data)
        self.query_reply_data[PrivateConstants.REPORT_FIRMWARE] = reply
        #logstring("10")
        return self.query_reply_data.get(PrivateConstants.REPORT_FIRMWARE)

    async def get_protocol_version(self):
        """
        This method returns the major and minor values for the protocol
        version, i.e. 2.4

        :returns: Firmata protocol version
        """
        if self.query_reply_data.get(PrivateConstants.REPORT_VERSION) == '':
            await self._send_command([PrivateConstants.REPORT_VERSION])
            while self.query_reply_data.get(
                    PrivateConstants.REPORT_VERSION) == '':
                await asyncio.sleep(self.sleep_tune)
        return self.query_reply_data.get(PrivateConstants.REPORT_VERSION)

    async def get_pin_state(self, pin):
        """
        This method retrieves a pin state report for the specified pin

        :param pin: Pin of interest
        :returns: pin state report
        """
        pin_list = [pin]
        await self._send_sysex(PrivateConstants.PIN_STATE_QUERY, pin_list)
        while self.query_reply_data.get(
                PrivateConstants.PIN_STATE_RESPONSE) is None:
            await asyncio.sleep(self.sleep_tune)
        pin_state_report = self.query_reply_data.get(
            PrivateConstants.PIN_STATE_RESPONSE)
        self.query_reply_data[PrivateConstants.PIN_STATE_RESPONSE] = None
        return pin_state_report

    # noinspection PyMethodMayBeStatic
    async def get_wildcards_version(self):
        """
        This method retrieves the Wildcards version number

        :returns: Wildcards version number.
        """
        return PrivateConstants.WILDCARDS_VERSION

    # noinspection PyIncorrectDocstring
    async def i2c_config(self, read_delay_time=0):
        """
        NOTE: THIS METHOD MUST BE CALLED BEFORE ANY I2C REQUEST IS MADE
        This method initializes Firmata for I2c operations.

        :param read_delay_time (in microseconds): an optional parameter,
                                                  default is 0
        :returns: No Return Value
        """
        data = [read_delay_time & 0x7f, (read_delay_time >> 7) & 0x7f]
        await self._send_sysex(PrivateConstants.I2C_CONFIG, data)

    async def i2c_read_data(self, address):
        """
        This method retrieves cached i2c data to support a polling mode.

        :param address: I2C device address
        :returns: Last cached value read
        """
        if address in self.i2c_map:
            map_entry = self.i2c_map.get(address)
            data = map_entry.get('value')
            return data
        else:
            return None

    async def i2c_read_request(self, address, register, number_of_bytes,
                               read_type, cb=None):
        """
        This method requests the read of an i2c device. Results are retrieved
        by a call to i2c_get_read_data(). or by callback.

        If a callback method is provided, when data is received from the
        device it will be sent to the callback method.
        Some devices require that transmission be restarted
        (e.g. MMA8452Q accelerometer).
        Use Constants.I2C_READ | Constants.I2C_END_TX_MASK for those cases.

        :param address: i2c device address
        :param register: register number (can be set to zero. If set to None,
                         register is not sent)
        :param number_of_bytes: number of bytes expected to be returned
        :param read_type: I2C_READ or I2C_READ_CONTINUOUSLY. I2C_END_TX_MASK
                          may be OR'ed when required
        :param cb: Optional callback function to report i2c data as a
                   result of read command
        :returns: No return value.
        """
        if address not in self.i2c_map:
            self.i2c_map[address] = {'value': None, 'callback': cb}
        if register is None:
            data = [address, read_type, number_of_bytes & 0x7f,
                    (number_of_bytes >> 7) & 0x7f]        
        else:
            data = [address, read_type, register & 0x7f, (register >> 7) & 0x7f,
                    number_of_bytes & 0x7f, (number_of_bytes >> 7) & 0x7f]
        await self._send_sysex(PrivateConstants.I2C_REQUEST, data)

    async def i2c_stop_reading(self, address):
        """
        This method requests the read of an i2c device. Results are retrieved
        by a call to i2c_get_read_data(). or by callback.

        If a callback method is provided, when data is received from the
        device it will be sent to the callback method.
        Some devices require that transmission be restarted
        (e.g. MMA8452Q accelerometer).
        Use Constants.I2C_READ | Constants.I2C_END_TX_MASK for those cases.

        :param address: i2c device address
        :returns: No return value.
        """
        data = [address, Constants.I2C_STOP_READING]
        await self._send_sysex(PrivateConstants.I2C_REQUEST, data)
        
        
    async def i2c_write_request(self, address, args):
        """
        Write data to an i2c device.

        :param address: i2c device address
        :param args: A variable number of bytes to be sent to the device
                     passed in as a list
        :returns: No return value.
        """
        data = [address, Constants.I2C_WRITE]
        for item in args:
            item_lsb = item & 0x7f
            data.append(item_lsb)
            item_msb = (item >> 7) & 0x7f
            data.append(item_msb)
        await self._send_sysex(PrivateConstants.I2C_REQUEST, data)

    async def keep_alive(self, period=1, margin=.3):
        """
        Periodically send a keep alive message to the Arduino.
        Frequency of keep alive transmission is calculated as follows:
        keep_alive_sent = period - (period * margin)


        :param period: Time period between keepalives. Range is 0-10 seconds. 0 disables the keepalive mechanism.
        :param margin: Safety margin to assure keepalives are sent before period expires. Range is 0.1 to 0.9
        :returns: No return value
        """
        self.KeepAlive.interval = period
        self.KeepAlive.margin = margin

    async def play_tone(self, pin, tone_command, frequency=440, duration=0):
        """
        This method will call the Tone library for the selected pin.
        It requires FirmataPlus to be loaded onto the arduino

        If the tone command is set to TONE_TONE, then the specified tone will be played.

        Else, if the tone command is TONE_NO_TONE, then any currently playing tone will be disabled.

        :param pin: Pin number
        :param tone_command: Either TONE_TONE, or TONE_NO_TONE
        :param frequency: Frequency of tone in Hz. Default 440Hz for Stuttgart pitch, the general tuning standard
        :param duration: Duration of tone in milliseconds. default 0 = unlimited duration
        :returns: No return value
        """
        if tone_command == Constants.TONE_TONE:
            self.Tone.play_tone(pin, frequency, duration)
        if tone_command == Constants.TONE_NO_TONE:   
            self.Tone.stop_tone(pin)


    async def send_reset(self):
        """
        Send a Sysex reset command to the arduino

        :returns: No return value.
        """
        try:
            await self._send_command([PrivateConstants.SYSTEM_RESET])
        except RuntimeError:
            exit(0) #keep this??

    async def servo_config(self, pin, min_pulse=544, max_pulse=2400):
        """
        Configure a pin as a servo pin. Set pulse min, max in ms.
        Use this method (not set_pin_mode) to configure a pin for servo
        operation.

        :param pin: Servo Pin.
        :param min_pulse: Min pulse width in ms.
        :param max_pulse: Max pulse width in ms.
        :returns: No return value
        """
        #command = [pin, min_pulse & 0x7f, (min_pulse >> 7) & 0x7f, max_pulse & 0x7f,
        #           (max_pulse >> 7) & 0x7f]

        self._digital_pins_directly[pin].ConfigServo(min_pulse, max_pulse)
        #await self._send_sysex(PrivateConstants.SERVO_CONFIG, command)

    async def set_analog_latch(self, pin, threshold_type, threshold_value,
                               cb=None):
        """
        This method "arms" an analog pin for its data to be latched and saved
        in the latching table
        If a callback method is provided, when latching criteria is achieved,
        the callback function is called with latching data notification.

        Data returned in the callback list has the pin number as the
        first element,

        :param pin: Analog pin number
                    (value following an 'A' designator, i.e. A5 = 5
        :param threshold_type: ANALOG_LATCH_GT | ANALOG_LATCH_LT  |
                               ANALOG_LATCH_GTE | ANALOG_LATCH_LTE
        :param threshold_value: numerical value - between 0 and 1023
        :param cb: callback method
        :returns: True if successful, False if parameter data is invalid
        """
        if Constants.LATCH_GT <= threshold_type <= Constants.LATCH_LTE:
            key = 'A' + str(pin)
            if 0 <= threshold_value <= 1023:
                self.latch_map[key] = [Constants.LATCH_ARMED, threshold_type,
                                       threshold_value, 0, 0, cb]
                return True
        else:
            return False

    async def set_digital_latch(self, pin, threshold_value, cb=None):
        """
        This method "arms" a digital pin for its data to be latched and
        saved in the latching table
        If a callback method is provided, when latching criteria is achieved,
        the callback function is called with latching data notification.

        Data returned in the callback list has the pin number as the
        first element,

        :param pin: Digital pin number
        :param threshold_value: 0 or 1
        :param cb: callback function
        :returns: True if successful, False if parameter data is invalid
        """
        if 0 <= threshold_value <= 1:
            key = 'D' + str(pin)
            self.latch_map[key] = [Constants.LATCH_ARMED, Constants.LATCH_EQ,
                                   threshold_value, 0, 0, cb]
            return True
        else:
            return False

    async def set_pin_mode(self, pin_number, pin_state, callback=None):
        """
        This method sets the pin mode for the specified pin.
        For Servo, use servo_config() instead.

        :param pin_number: Arduino Pin Number
        :param pin_state: INPUT/OUTPUT/ANALOG/PWM - for SERVO use
                          servo_config()
        :param callback: Optional: A reference to a call back function to be
                         called when pin data value changes
        :returns: No return value
        """

        # There is a potential start up race condition when running pymata3.
        # This is a workaround for that race condition
        #
        if not len(self.digital_pins):
            await asyncio.sleep(2)
        if callback:
            if pin_state == Constants.INPUT:
                self.digital_pins[pin_number].cb = callback
            elif pin_state == Constants.ANALOG:
                self.analog_pins[pin_number].cb = callback
            #else:
            #    logstring('set_pin_mode: callback ignored for pin '
            #              'state: {}'.format(pin_state))

        pin_mode = pin_state
        self._digital_pins_directly[pin_number].SetPinMode(pin_mode)
        if pin_state == Constants.ANALOG:
            self._digital_pins_directly[pin_number].enable_analog_reporting()
        elif pin_state == Constants.INPUT:
            logstring("Setting digital pin directly as INPUT")
            self._digital_pins_directly[pin_number].enable_digital_reporting()
        else:
            pass

    async def set_sampling_interval(self, interval):
        """
        This method sends the desired sampling interval to Firmata.
        Note: Standard Firmata  will ignore any interval less than
              10 milliseconds

        :param interval: Integer value for desired sampling interval
                         in milliseconds
        :returns: No return value.
        """
        data = [interval & 0x7f, (interval >> 7) & 0x7f]
        await self._send_sysex(PrivateConstants.SAMPLING_INTERVAL, data)

    async def sleep(self, sleep_time):
        """
        This method is a proxy method for asyncio.sleep

        :param sleep_time: Sleep interval in seconds
        :returns: No return value.
        """
        await asyncio.sleep(sleep_time)

    async def sonar_config(self, trigger_pin, echo_pin, cb=None,
                           ping_interval=50, max_distance=350):
        """
        Configure the pins,ping interval and maximum distance for an HC-SR04
        type device.
        Single pin configuration may be used. To do so, set both the trigger
        and echo pins to the same value.
        Up to a maximum of 6 SONAR devices is supported
        If the maximum is exceeded a message is sent to the console and the
        request is ignored.
        NOTE: data is measured in centimeters

        :param trigger_pin: The pin number of for the trigger (transmitter).
        :param echo_pin: The pin number for the received echo.
        :param cb: optional callback function to report sonar data changes
        :param ping_interval: Minimum interval between pings. Lowest number
                              to use is 33 ms.Max is 127ms. Setting to 50ms
                              make it work for up to 428cm, we will set our
                              measurement max lower
        :param max_distance: Maximum distance in cm. Max is 350cm.
        :returns: No return value.
        """
        # if there is an entry for the trigger pin in existence, just exit
        if trigger_pin in self.active_sonar_map:
            return

        if max_distance > 350:
            max_distance = 350
        max_distance_lsb = max_distance & 0x7f
        max_distance_msb = (max_distance >> 7) & 0x7f
        data = [trigger_pin, echo_pin, ping_interval, max_distance_lsb,
                max_distance_msb]
        await self.set_pin_mode(trigger_pin, Constants.SONAR, Constants.INPUT)
        await self.set_pin_mode(echo_pin, Constants.SONAR, Constants.INPUT)
        # update the ping data map for this pin
        if len(self.active_sonar_map) > 6:
            logstring('sonar_config: maximum number of '
                      'devices assigned - ignoring request')
        else:
            self.active_sonar_map[trigger_pin] = [cb, 0]

        await self._send_sysex(PrivateConstants.SONAR_CONFIG, data)

    async def sonar_data_retrieve(self, trigger_pin):
        """
        Retrieve Ping (HC-SR04 type) data. The data is presented as a
        dictionary.
        The 'key' is the trigger pin specified in sonar_config()
        and the 'data' is the current measured distance (in centimeters)
        for that pin. If there is no data, the value is set to None.

        :param trigger_pin: key into sonar data map
        :returns: active_sonar_map
        """
        # sonar_pin_entry = self.active_sonar_map[pin]
        sonar_pin_entry = self.active_sonar_map.get(trigger_pin)
        value = sonar_pin_entry[1]
        return value

    async def stepper_config(self, steps_per_revolution, stepper_pins):
        """
        Configure stepper motor prior to operation.
        This is a FirmataPlus feature.

        :param steps_per_revolution: number of steps per motor revolution
        :param stepper_pins: a list of control pin numbers - either 4 or 2
        :returns: No return value.
        """
        data = [PrivateConstants.STEPPER_CONFIGURE, steps_per_revolution & 0x7f,
                (steps_per_revolution >> 7) & 0x7f]
        for pin in range(len(stepper_pins)):
            data.append(stepper_pins[pin])
        await self._send_sysex(PrivateConstants.STEPPER_DATA, data)

    async def stepper_step(self, motor_speed, number_of_steps):
        """
        Move a stepper motor for the number of steps at the specified speed
        This is a FirmataPlus feature.

        :param motor_speed: 21 bits of data to set motor speed
        :param number_of_steps: 14 bits for number of steps & direction
                                positive is forward, negative is reverse
        :returns: No return value.
        """
        if number_of_steps > 0:
            direction = 1
        else:
            direction = 0
        abs_number_of_steps = abs(number_of_steps)
        data = [PrivateConstants.STEPPER_STEP, motor_speed & 0x7f,
                (motor_speed >> 7) & 0x7f, (motor_speed >> 14) & 0x7f,
                abs_number_of_steps & 0x7f, (abs_number_of_steps >> 7) & 0x7f, direction]
        await self._send_sysex(PrivateConstants.STEPPER_DATA, data)

    async def pixy_init(self, max_blocks=5, cb=None):
        """
        Initialize Pixy and enable Pixy block reporting.
        This is a FirmataPlusRB feature.

        :param cb: callback function to report Pixy blocks
        :param max_blocks: Maximum number of Pixy blocks to report when many signatures are found.
        :returns: No return value.
        """
        if cb:
            self.digital_pins[PrivateConstants.PIN_PIXY_MOSI].cb = cb  # Pixy uses SPI.  Pin 11 is MOSI.
        data = [PrivateConstants.PIXY_INIT, max_blocks & 0x7f]
        await self._send_sysex(PrivateConstants.PIXY_CONFIG, data)

    async def pixy_set_servos(self, s0, s1):
        """
        Sends the setServos Pixy command.
        This method sets the pan/tilt servos that are plugged into Pixy's two servo ports.

        :param s0: value 0 to 1000
        :param s1: value 0 to 1000
        :returns: No return value.
        """
        data = [PrivateConstants.PIXY_SET_SERVOS, s0 & 0x7f, (s0 >> 7) & 0x7f, s1 & 0x7f, (s1 >> 7) & 0x7f]
        await self._send_sysex(PrivateConstants.PIXY_CONFIG, data)

    async def pixy_set_brightness(self, brightness):
        """
        Sends the setBrightness Pixy command.
        This method sets the brightness (exposure) of Pixy's camera.

        :param brightness: range between 0 and 255 with 255 being the brightest setting
        :returns: No return value.
        """
        data = [PrivateConstants.PIXY_SET_BRIGHTNESS, brightness & 0x7f, (brightness >> 7) & 0x7f]
        await self._send_sysex(PrivateConstants.PIXY_CONFIG, data)

    async def pixy_set_led(self, r, g, b):
        """
        Sends the setLed Pixy command.
        This method sets the RGB LED on front of Pixy.

        :param r: red range between 0 and 255
        :param g: green range between 0 and 255
        :param b: blue range between 0 and 255
        :returns: No return value.
        """
        data = [PrivateConstants.PIXY_SET_LED, r & 0x7f, (r >> 7) & 0x7f, g & 0x7f, (g >> 7) & 0x7f, b & 0x7f,
                (b >> 7) & 0x7f]
        await self._send_sysex(PrivateConstants.PIXY_CONFIG, data)

    async def _command_dispatcher(self):
        """
        This is a private method.
        It continually accepts and interprets data coming from Firmata,and then
        dispatches the correct handler to process the data.

        :returns: This method never returns
        """
        # sysex commands are assembled into this list for processing
        #checkingport = self.serial_port.com_port
        logstring("Starting Command Dispatcher")
        sysex = []
        while True:
            if self._valid_target_exists:
                #logstring("Command Dispatcher: Valid Target")
                try:
                    #logstring("Command Dispatcher: Reading Next Byte")
                    #donothing = self.donothingatall()
                    #logstring("Command Dispatcher: didnothingatall")
                    next_command_byte = await self.read_next_byte()
                    #logstring("Command Dispatcher: Next Byte Read {}".format(next_command_byte))
                    # if this is a SYSEX command, then assemble the entire
                    # command process it
                    if next_command_byte == PrivateConstants.START_SYSEX:
                        while next_command_byte != PrivateConstants.END_SYSEX:
                            # because self.  is awaited, i think we can remove this sleep, and the next
                            #await asyncio.sleep(self.sleep_tune)
                            next_command_byte = await self.read_next_byte()
                            sysex.append(next_command_byte)
                        await self.command_dictionary[sysex[0]](sysex)
                        sysex = []
                        await asyncio.sleep(self.sleep_tune)
                    # if this is an analog message, process it.
                    elif 0xE0 <= next_command_byte <= 0xEF:
                        # analog message
                        # assemble the entire analog message in command
                        command = []
                        # get the pin number for the message
                        pin = next_command_byte & 0x0f
                        command.append(pin)
                        # get the next 2 bytes for the command
                        command = await self._wait_for_data(command, 2)
                        # process the analog message
                        logstring("Analog Message received {}".format(command))
                        await self._analog_message(command)
                    # handle the digital message
                    elif 0x90 <= next_command_byte <= 0x9F:
                        command = []
                        port = next_command_byte & 0x0f
                        command.append(port)
                        command = await self._wait_for_data(command, 2)
                        await self._digital_message(command)
                    # handle all other messages by looking them up in the
                    # command dictionary
                    elif next_command_byte in self.command_dictionary:
                        await self.command_dictionary[next_command_byte]()
                        await asyncio.sleep(self.sleep_tune)
                    else:
                        # we need to yield back to the loop
                        await asyncio.sleep(self.sleep_tune)
                        continue
                    #logstring("finished this read cycle")                        
                except ConnectionAbortedError as ex:
                    logstring(ex)
                    #print("An exception occurred on the asyncio event loop while receiving data.  Invalid message.")
            else:
                await asyncio.sleep(0.01)

    '''
    Firmata message handlers
    '''

    async def _analog_mapping_response(self, data):
        """
        This is a private message handler method.
        It is a message handler for the analog mapping response message

        :param data: response data
        :returns: none - but saves the response
        """
        self.query_reply_data[PrivateConstants.ANALOG_MAPPING_RESPONSE] = \
            data[1:-1]

    async def _analog_message(self, data):
        """
        This is a private message handler method.
        It is a message handler for analog messages.

        :param data: message data
        :returns: None - but saves the data in the pins structure
        """
        pin = data[0]
        value = (data[PrivateConstants.MSB] << 7) + data[PrivateConstants.LSB]
        #logstring("Value was {}".format(value))
        # if self.analog_pins[pin].current_value != value:
        self.analog_pins_analog_numbering[pin].current_value = value

        # append pin number, pin value, and pin type to return value and return as a list
        message = [pin, value, Constants.ANALOG]

        if self.analog_pins_analog_numbering[pin].cb:
            if inspect.iscoroutinefunction(self.analog_pins_analog_numbering[pin].cb):
                await self.analog_pins_analog_numbering[pin].cb(message)
            else:
                loop = self.loop
                loop.call_soon(self.analog_pins_analog_numbering[pin].cb, message)

        # is there a latch entry for this pin?
        key = 'A' + str(pin)
        if key in self.latch_map:
            await self._check_latch_data(key, message[1])

    async def _capability_response(self, data):
        """
        This is a private message handler method.
        It is a message handler for capability report responses.

        :param data: capability report
        :returns: None - but report is saved
        """
        self.query_reply_data[PrivateConstants.CAPABILITY_RESPONSE] = data[1:-1]

    async def _digital_message(self, data):
        """
        This is a private message handler method.
        It is a message handler for Digital Messages.

        :param data: digital message

        :returns: None - but update is saved in pins structure
        """
        try:
            port = data[0]
            port_data = (data[PrivateConstants.MSB] << 7) + \
                        data[PrivateConstants.LSB]
            port_starting_pin = port * 8
            logstring("Digital message received: {} {}  {}".format(port, port_data, port_starting_pin))
            for pin in range(port_starting_pin, min(port_starting_pin + 8, len(self.digital_pins))):
                # get pin value
                #logstring("doing pin {}".format(pin))
                value = port_data & 0x01

                # set the current value in the pin structure
                self.digital_pins[pin].current_value = value
                # append pin number, pin value, and pin type to return value and return as a list
                message = [pin, value, Constants.INPUT]

                #logstring("2a doing pin {}".format(self.digital_pins[pin].cb))
                if self.digital_pins[pin].cb:
                    if inspect.iscoroutinefunction(self.digital_pins[pin].cb):
                        await self.digital_pins[pin].cb(message)
                    else:
                        loop = self.loop
                        loop.call_soon(self.digital_pins[pin].cb, message)

                    # is there a latch entry for this pin?
                    key = 'D' + str(pin)
                    if key in self.latch_map:
                        await self._check_latch_data(key, port_data & 0x01)       
                port_data >>= 1
            #logstring("finished digital message function")
        except Exception as inst:
                print(inst)
                raise
    async def _encoder_data(self, data):
        """
        This is a private message handler method.
        It handles encoder data messages.

        :param data: encoder data
        :returns: None - but update is saved in the digital pins structure
        """
        # strip off sysex start and end
        data = data[1:-1]
        pin = data[0]
        if not self.hall_encoder:
            val = int((data[PrivateConstants.MSB] << 7) +
                      data[PrivateConstants.LSB])
            # set value so that it shows positive and negative values
            if val > 8192:
                val -= 16384
            # if this value is different that is what is already in the
            # table store it and check for callback
            if val != self.digital_pins[pin].current_value:
                self.digital_pins[pin].current_value = val
                if self.digital_pins[pin].cb:
                    if inspect.iscoroutinefunction(self.digital_pins[pin].cb):
                        await self.digital_pins[pin].cb(val)
                    else:
                        loop = self.loop
                        loop.call_soon(self.digital_pins[pin].cb, val)
        else:
            #this one is not used by Wildcards presently
            hall_data = [int((data[2] << 7) + data[1]), int((data[5] << 7) +
                                                            data[4])]

            if inspect.iscoroutinefunction(self.digital_pins[pin].cb):
                await self.digital_pins[pin].cb(hall_data)
            else:
                loop = self.loop
                loop.call_soon(self.digital_pins[pin].cb, hall_data)

    # noinspection PyDictCreation
    async def _pixy_data(self, data):
        """
        This is a private message handler method.
        It handles pixy data messages.

        :param data: pixy data
        :returns: None - but update is saved in the digital pins structure
        """
        if len(self.digital_pins) < PrivateConstants.PIN_PIXY_MOSI:
            # Pixy data sent before board finished pin discovery.
            # print("Pixy data sent before board finished pin discovery.")
            return

        # strip off sysex start and end
        data = data[1:-1]
        num_blocks = data[0]  # First byte is the number of blocks.
        # Prepare the new blocks list and then used it to overwrite the pixy_blocks.
        blocks = []
        # noinspection PyDictCreation
        for i in range(num_blocks):
            block = {}
            block["signature"] = int((data[i * 12 + 2] << 7) + data[i * 12 + 1])
            block["x"] = int((data[i * 12 + 4] << 7) + data[i * 12 + 3])
            block["y"] = int((data[i * 12 + 6] << 7) + data[i * 12 + 5])
            block["width"] = int((data[i * 12 + 8] << 7) + data[i * 12 + 7])
            block["height"] = int((data[i * 12 + 10] << 7) + data[i * 12 + 9])
            block["angle"] = int((data[i * 12 + 12] << 7) + data[i * 12 + 11])
            blocks.append(block)
        self.pixy_blocks = blocks
        if self.digital_pins[PrivateConstants.PIN_PIXY_MOSI].cb:
            if inspect.iscoroutinefunction(self.digital_pins[PrivateConstants.PIN_PIXY_MOSI].cb):
                await self.digital_pins[PrivateConstants.PIN_PIXY_MOSI].cb(blocks)
            else:
                loop = self.loop
                loop.call_soon(self.digital_pins[PrivateConstants.PIN_PIXY_MOSI].cb, blocks)

    async def _i2c_reply(self, data):
        """
        This is a private message handler method.
        It handles replies to i2c_read requests. It stores the data
        for each i2c device address in a dictionary called i2c_map.
        The data may be retrieved via a polling call to i2c_get_read_data().
        If a callback was specified in pymata.i2c_read, the raw data is sent
        through the callback

        :param data: raw data returned from i2c device
        """
        # remove the start and end sysex commands from the data
        data = data[1:-1]
        reply_data = []
        # reassemble the data from the firmata 2 byte format
        address = (data[0] & 0x7f) + (data[1] << 7)

        # if we have an entry in the i2c_map, proceed
        if address in self.i2c_map:
            # get 2 bytes, combine them and append to reply data list
            for i in range(0, len(data), 2):
                combined_data = (data[i] & 0x7f) + (data[i + 1] << 7)
                reply_data.append(combined_data)

            # place the data in the i2c map without storing the address byte or
            #  register byte (returned data only)
            map_entry = self.i2c_map.get(address)
            map_entry['value'] = reply_data[2:]
            self.i2c_map[address] = map_entry
            cb = map_entry.get('callback')
            if cb:
                # send everything, including address and register bytes back
                # to caller
                if inspect.iscoroutinefunction(cb):
                    await cb(reply_data)
                else:
                    loop = self.loop
                    loop.call_soon(cb, reply_data)
                await asyncio.sleep(self.sleep_tune)

    async def _pin_state_response(self, data):
        """
        This is a private message handler method.
        It handles pin state query response messages.

        :param data: Pin state message
        :returns: None - but response is saved
        """
        self.query_reply_data[PrivateConstants.PIN_STATE_RESPONSE] = data[1:-1]

    async def _report_firmware(self, sysex_data):
        """
        This is a private message handler method.
        This method handles the sysex 'report firmware' command sent by
        Firmata (0x79).
        It assembles the firmware version by concatenating the major and
         minor version number components and
        the firmware identifier into a string.
        e.g. "2.3 StandardFirmata.ino"

        :param sysex_data: Sysex data sent from Firmata
        :returns: None
        """
        # first byte after command is major number
        firmware_report_iterator = iter(sysex_data)
        
        major = sysex_data[1]
        version_string = str(major)

        # next byte is minor number
        minor = sysex_data[2]

        # append a dot to major number
        version_string += '.'

        # append minor number
        version_string += str(minor)
        # add a space after the major and minor numbers
        version_string += ' '

        # slice the identifier - from the first byte after the minor
        #  number up until, but not including the END_SYSEX byte

        name = sysex_data[3:-1]
        firmware_name_iterator = iter(name)
        # convert the identifier to printable text and add each character
        # to the version string
        for e in firmware_name_iterator:
            version_string += chr(e + (next(firmware_name_iterator) << 7))

        # store the value
        self.query_reply_data[PrivateConstants.REPORT_FIRMWARE] = version_string

    async def _report_version(self):
        """
        This is a private message handler method.
        This method reads the following 2 bytes after the report version
        command (0xF9 - non sysex).
        The first byte is the major number and the second byte is the
        minor number.

        :returns: None
        """
        # get next two bytes
        major = await self.read()
        version_string = str(major)
        minor = await self.read()
        version_string += '.'
        version_string += str(minor)
        self.query_reply_data[PrivateConstants.REPORT_VERSION] = version_string

    async def _sonar_data(self, data):
        """
        This method handles the incoming sonar data message and stores
        the data in the response table.

        :param data: Message data from Firmata
        :returns: No return value.
        """

        # strip off sysex start and end
        data = data[1:-1]
        pin_number = data[0]
        val = int((data[PrivateConstants.MSB] << 7) +
                  data[PrivateConstants.LSB])
        reply_data = []

        sonar_pin_entry = self.active_sonar_map[pin_number]

        if sonar_pin_entry[0] is not None:
            # check if value changed since last reading
            if sonar_pin_entry[2] != val:
                sonar_pin_entry[2] = val
                self.active_sonar_map[pin_number] = sonar_pin_entry
                # Do a callback if one is specified in the table
                if sonar_pin_entry[0]:
                    # if this is an asyncio callback type
                    reply_data.append(pin_number)
                    reply_data.append(val)
                    if inspect.iscoroutinefunction(sonar_pin_entry[0]):
                        await sonar_pin_entry[0](reply_data)
                    else:
                        loop = self.loop
                        loop.call_soon(sonar_pin_entry[0], reply_data)

        # update the data in the table with latest value
        else:
            sonar_pin_entry[1] = val
            self.active_sonar_map[pin_number] = sonar_pin_entry

        await asyncio.sleep(self.sleep_tune)

    async def _string_data(self, data):
        """
        This is a private message handler method.
        It is the message handler for String data messages that will be
        printed to the console.
        :param data:  message
        :returns: None - message is sent to console
        """
        reply = ''
        data = data[1:-1]
        for x in data:
            reply_data = x
            if reply_data:
                reply += chr(reply_data)
        logstring(reply)

    '''
    utilities
    '''

    async def _check_latch_data(self, key, data):
        """
        This is a private utility method.
        When a data change message is received this method checks to see if
        latching needs to be processed

        :param key: encoded pin number
        :param data: data change
        :returns: None
        """
        process = False
        latching_entry = self.latch_map.get(key)
        if latching_entry[Constants.LATCH_STATE] == Constants.LATCH_ARMED:
            # Has the latching criteria been met
            if latching_entry[Constants.LATCHED_THRESHOLD_TYPE] == \
                    Constants.LATCH_EQ:
                if data == latching_entry[Constants.LATCH_DATA_TARGET]:
                    process = True
            elif latching_entry[Constants.LATCHED_THRESHOLD_TYPE] == \
                    Constants.LATCH_GT:
                if data > latching_entry[Constants.LATCH_DATA_TARGET]:
                    process = True
            elif latching_entry[Constants.LATCHED_THRESHOLD_TYPE] == \
                    Constants.LATCH_GTE:
                if data >= latching_entry[Constants.LATCH_DATA_TARGET]:
                    process = True
            elif latching_entry[Constants.LATCHED_THRESHOLD_TYPE] == \
                    Constants.LATCH_LT:
                if data < latching_entry[Constants.LATCH_DATA_TARGET]:
                    process = True
            elif latching_entry[Constants.LATCHED_THRESHOLD_TYPE] == \
                    Constants.LATCH_LTE:
                if data <= latching_entry[Constants.LATCH_DATA_TARGET]:
                    process = True
            if process:
                latching_entry[Constants.LATCHED_DATA] = data
                await self._process_latching(key, latching_entry)


    # noinspection PyMethodMayBeStatic
    def _format_capability_report(self, data):
        """
        This is a private utility method.
        This method formats a capability report if the user wishes to
        send it to the console.
        If log_output = True, no output is generated

        :param data: Capability report
        :returns: None
        """



        pin_modes = {0: 'Digital_Input', 1: 'Digital_Output',
                     2: 'Analog', 3: 'PWM', 4: 'Servo',
                     5: 'Shift', 6: 'I2C', 7: 'One Wire',
                     8: 'Stepper', 9: 'Encoder'}
        x = 0
        pin = 0

        logstring('\nCapability Report')
        logstring('-----------------\n')
        while x < len(data):
            # get index of next end marker
            logstring('{} {}{}'.format('Pin', str(pin), ':'))
            while data[x] != 127:
                mode_str = ""
                pin_mode = pin_modes.get(data[x])
                mode_str += str(pin_mode)
                x += 1
                bits = data[x]
                logstring('{:>5}{}{} {}'.format('  ', mode_str, ':', bits))
                x += 1
            x += 1
            pin += 1

    async def _process_latching(self, key, latching_entry):
        """
        This is a private utility method.
        This method process latching events and either returns them via
        callback or stores them in the latch map

        :param key: Encoded pin
        :param latching_entry: a latch table entry
        :returns: Callback or store data in latch map
        """
        if latching_entry[Constants.LATCH_CALLBACK]:
            # auto clear entry and execute the callback
            if inspect.iscoroutinefunction(latching_entry[Constants.LATCH_CALLBACK]):
                await latching_entry[Constants.LATCH_CALLBACK] \
                    ([key, latching_entry[Constants.LATCHED_DATA], time.time()])
            else:
                latching_entry[Constants.LATCH_CALLBACK] \
                    ([key, latching_entry[Constants.LATCHED_DATA], time.time()])
            self.latch_map[key] = [0, 0, 0, 0, 0, None]
        else:
            updated_latch_entry = latching_entry
            updated_latch_entry[Constants.LATCH_STATE] = \
                Constants.LATCH_LATCHED
            updated_latch_entry[Constants.LATCHED_DATA] = \
                latching_entry[Constants.LATCHED_DATA]
            # time stamp it
            updated_latch_entry[Constants.LATCHED_TIME_STAMP] = time.time()
            self.latch_map[key] = updated_latch_entry

    async def _send_command(self, command):
        """
        This is a private utility method.
        The method sends a non-sysex command to Firmata.

        :param command:  command data
        :returns: length of data sent
        """
        send_message = ""

        for i in command:
            send_message += chr(i)
        result = None
        for data in send_message:
            if self.serial_port is not None:
                try:
                    result = self.write(data)
                except():
                    logerr('Cannot send command')
        return result

    async def _send_sysex(self, sysex_command, sysex_data=None):
        """
        This is a private utility method.
        This method sends a sysex command to Firmata.

        :param sysex_command: sysex command
        :param sysex_data: data for command
        :returns : No return value.
        """
        if not sysex_data:
            sysex_data = []
        #logstring("sending {}".format(sysex_command))
        # convert the message command and data to characters
        sysex_message = chr(PrivateConstants.START_SYSEX)
        sysex_message += chr(sysex_command)
        if len(sysex_data):
            for d in sysex_data:
                sysex_message += chr(d)
        sysex_message += chr(PrivateConstants.END_SYSEX)
        for data in sysex_message:
            if self.serial_port is not None:
                #print("serial port is {}".format(self.serial_port))
                 #someday make write awaitable
                #logstring("{}".format(data))
                self.write(data)
        #await asyncio.sleep(0.1)
        
        
    async def _wait_for_data(self, current_command, number_of_bytes):
        """
        This is a private utility method.
        This method accumulates the requested number of bytes and
        then returns the full command

        :param current_command:  command id
        :param number_of_bytes:  how many bytes to wait for
        :returns: command
        """
        while number_of_bytes:
            next_command_byte = await self.read_next_byte()
            current_command.append(next_command_byte)
            number_of_bytes -= 1
        return current_command

    async def write_continuously(self):            
        start_time = time.perf_counter()
        end_time = time.perf_counter()
        while True:
            #take everything that needs to be written and store it as a byte string
            data = self.generate_byte_string()
            #logstring("sending byte string {}".format(data))
            
            
            
            #estimate how long the write will take, and add  a little
            #extra downtime ( like 10% could be removed for throughput reasons later)
            #the idea behind the extra downtime is that sometimes writing data will
            #block program execution (depends on the USB-UART driver, e.g the Windows Driver
            #will block, but FTDI's VCP won't block until/unless the buffers are full)
            write_time = self._estimate_write_time(data) * 1.1
            
            #set the sleep time to the write time + margin, or the tune time (typ 1ms),
            #whichever is larger
            if write_time < self.sleep_tune:
                write_time = self.sleep_tune
            start_time = time.perf_counter()
            if self._valid_target_exists and len(data) > 0:
                self.write(data)
            else:
                #if there was nothing to write, just set the write time back to the tune time
                write_time = self.sleep_tune
            end_time = time.perf_counter()
            
            #sleep until the tune time is up, or the write time + margin has expired (whichever is greater)
            if end_time - start_time < write_time:
                await asyncio.sleep(write_time - (end_time - start_time))
    
    
    def _estimate_write_time(self, data):
        """
        This is a private utility method.
        This method calculates the estimate write time (with margin) based
        on the number of bytes and the requested number of bytes and
        then returns the full command

        :param data:  bytes being sent to the write command
        :returns: estimated time to send the message in seconds
        """
        return (len(data.encode('utf-8'))/(self.byte_rate))*1.25
        #1.25 multiplier accounts for start & stop bits
       

        
    async def read_next_byte(self):
        while True:
            #logstring("So we're in --...")
            #logstring("So 2....   {}".format(self.serial_manager.ReadBuffer))
            #logstring("So 3...  {}".format(len(self.serial_manager.ReadBuffer)))
            if len(self.serial_manager.ReadBuffer) > 0:
                val =  self.serial_manager.ReadBuffer.pop(0)
                #logstring("Popping from ReadBuffer:   {}".format(val))
                return val
            else:
                if self._valid_target_exists:
                    #logstring("Nothing in buffer, sleeping")
                    await asyncio.sleep(0.1)
                else:
                    logstring("No valid target...")
                    raise ConnectionAbortedError("No Valid Target Connected")  #may want to change this...

async def read_nothing():
    return None
    
    
async def write_nothing(data):
    return None

    