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
from Wildcards_Logger import *

class Pin(WildcardsFirmataBaseObject):

    def __init__(self, ID, PinNum, HasInput=True,
                 HasPullup=True, HasOutput=True,
                 HasAnalog=False, AnalogPinNum = 127,
                 AnalogResolution=0, HasPWM=False,
                 PWMResolution=14, HasI2C=False):
        super().__init__(ID)

        self._value = 0
        self._last_sent_value = 0

        self._mode = Constants.NOMODESET
        self._last_sent_mode = Constants.NOMODESET
        #self._mode = Constants.OUTPUT   #this is the default in Firmata, unless the pin has Analog Input capability
        #self._last_sent_mode = Constants.OUTPUT
        #self._mode = Constants.INPUT
        #self._last_sent_mode = Constants.INPUT
        self._isI2Cenabled = False

        self._need_to_write_mode = False
        self._need_to_config_servo = False 
        self._need_to_perform_digital_write = False 
        self._need_to_perform_analog_write = False 
        self._need_to_send_analog_reporting = False 
        self._need_to_query_pin_state = False 

     
        self._PinNum = PinNum      # valid_pin(, 256) #move this check to higher level??
        self._AnalogPinNum = AnalogPinNum  #only used if HasAnalog==True
        
        self._HasInput = HasInput
        self._HasPullup = HasPullup
        self._HasOutput = HasOutput        
        self._HasAnalog = HasAnalog
        self._AnalogResolution = AnalogResolution
        self._HasPWM = HasPWM
        self._PWMResolution = PWMResolution
        self._HasI2C = HasI2C
        

        
        self._servo_min_pulse = 544
        self._servo_max_pulse = 2400
        self._last_sent_servo_min_pulse = 0
        self._last_sent_servo_max_pulse = 0  

        self._report_analog = 0        
        self._last_sent_report_analog = 0

        self.report_digital = 0        
        self.last_sent_report_digital = 0
        
        self._DigitalReportingEnabled = False
        self._need_to_send_digital_reporting = False
        
        # if HasAnalog:
            # self._mode = Constants.ANALOG
            # self._last_sent_mode = Constants.ANALOG
            # self._report_analog = 1        
            # self._last_sent_report_analog = 1
            
    def SetPinMode(self, mode):  #when sending pin numbers to set mode,
                                 #only digital pin numbering scheme is used
        logstring("setting mode to {} {} {}".format(mode, self._HasAnalog, self._HasOutput))
        if self._HasAnalog:
            logstring("spm 1")
            if mode == Constants.ANALOG: 
                logstring("spm 1.5")
                self._report_analog = 1  #always send through analog reporting messages as they incite an immediate response
                
            else:
                logstring("spm 2")
                self._report_analog = 0  #don't bother sending "turn off analog reports" as second time
        
        self._value = 0    
        #debug in here
        logstring("spm 3")
        if mode == Constants.ANALOG:
            logstring("spm 4")
            if self._HasAnalog:
                logstring("spm 5")
                if self._HasOutput or self._HasPullup or self._HasInput:
                    logstring("spm 6")
                    self._value
                logstring("spm 7")                    
                self._mode = Constants.ANALOG
                self._need_to_write_mode = True #always resend the analog reporting message
                self._need_to_config_servo = False 
                self._need_to_send_analog_reporting = False #no need because it is already going to handle during mode change  
                self._need_to_perform_analog_write = False
                logstring("spm 8")
        elif mode == Constants.INPUT:
            if self._HasInput:
                self._mode = Constants.INPUT
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True
                self._need_to_config_servo = False
                self._need_to_perform_analog_write = False
        elif mode == Constants.PULLUP:
            if self._HasPullup:
                self._mode = Constants.PULLUP
                self._value = 1
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True
                self._need_to_config_servo = False
                self._need_to_perform_analog_write = False
        elif mode == Constants.OUTPUT:
            if self._HasOutput:
                self._mode = Constants.OUTPUT
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True
                self._need_to_config_servo = False   
                self._need_to_perform_analog_write = False
        elif mode == Constants.PWM:
            if self._HasPWM:
                self._mode = Constants.PWM
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True
                self._need_to_config_servo = False
        elif mode == Constants.SERVO:
            if self._HasOutput:
                self._mode = Constants.SERVO
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True  
        elif mode == Constants.I2C:
            if self._HasI2C:
                self._mode = Constants.I2C
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True
                self._need_to_config_servo = False
                self._need_to_perform_analog_write = False
        elif mode == Constants.SERIAL:
            self._mode = Constants.SERIAL
            if self._mode != self._last_sent_mode:
                self._need_to_write_mode = True
            self._need_to_config_servo = False
            self._need_to_perform_analog_write = False
        elif mode == Constants.TONE:
            if self._HasOutput:
                #seems like the firmata code should check for digital to avoid serial pins? mistake in FirmataPlus?
                self._mode = Constants.TONE
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True  
                self._need_to_config_servo = False
                self._need_to_perform_analog_write = False
        elif mode == Constants.SONAR:
            if self._HasOutput and self._HasInput: #should change...
                #seems like the firmata code should check for digital to avoid serial pins? mistake in FirmataPlus?
                self._mode = Constants.SONAR
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True  
                self._need_to_config_servo = False
                self._need_to_perform_analog_write = False
        elif mode == Constants.STEPPER:
            if self._HasOutput:
                #seems like the firmata code should check for digital to avoid serial pins? mistake in FirmataPlus?
                self._mode = Constants.STEPPER
                if self._mode != self._last_sent_mode:
                    self._need_to_write_mode = True  
                self._need_to_config_servo = False
                self._need_to_perform_analog_write = False
        else:
            pass #no encoder? interesting....
            #unknown pin mode, do nothing
        logstring("mode is now {} for pin num {}".format(self._mode, self._PinNum))
    
    def enable_digital_reporting(self):
        self._DigitalReportingEnabled = True
        self._need_to_send_digital_reporting = True

    def disable_digital_reporting(self):
        self._DigitalReportingEnabled = False        
        self._need_to_send_digital_reporting = True
        
    def enable_analog_reporting(self):
        self._report_analog = 1     #can only do reporting on up to 16 analog pins, because firmata uses an int to store this info
        self._need_to_send_analog_reporting = True  #don't need to check if it is changing; if this is called, send it again
     
    def disable_analog_reporting(self):
        self._report_analog = 0
        if  self._report_analog == self._last_sent_report_analog:
            self._need_to_send_analog_reporting = False
        else:
            self._need_to_send_analog_reporting = True        
       
    def AnalogWrite(self, value):
        if self._mode == Constants.SERVO or self._mode == Constants.PWM:
            self._value = value
            if self._value != self._last_sent_value:
                self._need_to_perform_analog_write = True
            else:
                self._need_to_perform_analog_write = False
    
   
          
    def DigitalWrite(self, value, PermitWriteToInputPin = True):
        #If PermitWriteToInputPin is True, then this pin will be written to for both OUTPUT and INPUT pins
        #For INPUT pins, this means you can enable and disable the pullup
        #If PermitWriteToInputPin is False, you can only write to output pins.
        #This allows for the distinction between Set Digital Pin Value (0xF5) behavior and
        #Digital Write (0x90) in Firmata protocol
        if self._HasOutput or (self._HasInput and self._HasPullup):
            logstring("ok1 mode is {} for pin number {}".format(self._mode, self._PinNum))
            if self._mode == Constants.OUTPUT or (self._mode == Constants.INPUT and PermitWriteToInputPin):
                logstring("ok2")
                self._value = value
                logstring("ok3")
                if (self._value != 0 and self._last_sent_value == 0) or \
                   (self._value == 0 and self._last_sent_value != 0):

                    #no need to re-send if we're just changing the positive value used
                    #but do re-send if we're going 0 to non zero (or vice versa)
                    logstring("going to perform a digital write")
                    self._need_to_perform_digital_write = True
                else:
                    logstring("no need to perform a digital write")
                    self._need_to_perform_digital_write = False
            logstring("ok4")
        logstring("ok5")  
        
    def ConfigServo(self, min_pulse, max_pulse):
        self._servo_min_pulse = min_pulse
        self._servo_min_pulse = max_pulse
        self._mode = Constants.SERVO
        if (self._servo_min_pulse == self._last_sent_servo_min_pulse and
            self._servo_max_pulse == self._last_sent_servo_max_pulse and
            self._mode == self._last_sent_mode):
           pass
        else:
            self._need_to_write_mode = False
            self._need_to_config_servo = True 
     
    def PinStateQuery(self):
        self._need_to_query_pin_state = True 
        
    @property
    def DigitalReportingEnabled(self):
        return self._DigitalReportingEnabled        

    @property
    def need_to_send_digital_reporting(self):
        return self._need_to_send_digital_reporting        

                
        
    @property
    def value(self):
        return self._value

    @property
    def last_sent_value(self):
        return self._last_sent_value
        
    @property
    def to_be_written(self):
        return self._need_to_write_mode | \
               self._need_to_config_servo | \
               self._need_to_perform_digital_write | \
               self._need_to_perform_analog_write | \
               self._need_to_send_analog_reporting | \
               self._need_to_query_pin_state
               
    @property
    def need_to_perform_digital_write(self):
        return self._need_to_perform_digital_write               
        
    def generate_byte_string(self):
        output = ""
        if self._need_to_config_servo == True:
            output += WrapSysEx(chr(PrivateConstants.SERVO_CONFIG) + chr(self._PinNum) +
                               To7BitBytes(self._servo_min_pulse, 2) +
                               To7BitBytes(self._servo_max_pulse, 2)) 
            self._last_sent_servo_min_pulse = self._servo_min_pulse
            self._last_sent_servo_max_pulse = self._servo_max_pulse                  
            self._need_to_config_servo = False
        if self._need_to_write_mode == True:
            output += chr(PrivateConstants.SET_PIN_MODE) + \
                     To7BitBytes(self._PinNum) + \
                     To7BitBytes(self._mode) 
            self._last_sent_mode = self._mode
            self._need_to_write_mode = False
        if self._need_to_send_analog_reporting == True:
            if self._AnalogPinNum < 16:
                #Firmata allows analog reporting only for the first 16 analog pins
                output += chr(PrivateConstants.REPORT_ANALOG + self._AnalogPinNum) + \
                              To7BitBytes(self._report_analog)
            self._need_to_send_analog_reporting = False
        if self._need_to_send_digital_reporting == True:
            #collecting the info and sending this byte happens at the port level, so just turn it off
            self._need_to_send_digital_reporting = False
        if self._need_to_perform_digital_write == True:
            #collecting the info and sending this byte happens at the port level, so just turn off the flag here
            self._need_to_perform_digital_write = False
        if self._need_to_perform_analog_write == True:
            if self._PinNum < 16:
                #send via normal analog write
                output += chr(PrivateConstants.ANALOG_MESSAGE + self._PinNum) + \
                              To7BitBytes(self._value, 2)
            else: # #################make sure this was fixed
                #send via sysex as extended analog
                output += WrapSysEx(chr(PrivateConstants.EXTENDED_ANALOG) + \
                               To7BitBytes(self._PinNum) +\
                               To7BitBytes(self._value, 3)) 
            self._need_to_perform_analog_write = False
        if self._need_to_query_pin_state == True:  
            output += WrapSysEx(chr(PrivateConstants.PIN_STATE_QUERY) + \
                                self._PinNum)
            self._need_to_query_pin_state = False 
        self._last_sent_value = self._value
        return output
