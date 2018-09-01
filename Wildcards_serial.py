
import asyncio
import sys
import logging
import time
import serial
import concurrent.futures
from threading import Thread
from itertools import cycle

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
        self.com_port = com_port  #this just stores the com port to use temporarily until a CurrentPort object takes over
        self.sleep_tune = sleep_tune
        self.speed = speed
        self.CurrentPort = None
        self.Ports = []
        sys.stdout.flush()


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
        if com_port not in self.locations:
            print("locs {}".format(self.locations))
            self.locations.insert(0,com_port)
        detected = None

        for device in self.locations:
            self.Ports.append(Port(self, device))
            
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
        #print("appending to port list {}".format(portname))
        self._parent.UpdatePortList(self._portlist)
            
    def RemoveFromPortList(self, portname):
        self._portlist.remove(portname)
        print("updating port list {}".format(self._portlist))
        self._parent.UpdatePortList(self._portlist)

    async def PortOpened(self):
        await self._parent.SerialOpened()
        
    def PortClosed(self, com_port):
        self._parent.SerialClosed()
        
    async def OpenNamedSerialPort(self, portname, clear_port_error_status = True):
        print("opening this port: {}".format(portname))
        if portname not in self.locations: #add to locations if it isn't already in there
            self.locations.insert(0, portname)
            self.Ports.append(Port(self, portname))
        
        for x in self.Ports:  #find the requested port in the list of ports
            if x.com_port == portname:
                PortToOpen = x
                
        #now that it is in the port list, we wait for it to become available
        if not PortToOpen.HasBeenCheckedForAvailability(): #wait for avaialability checks to complete if needed
            await asyncio.sleep(self.sleep_tune)
            
        if clear_port_error_status == True:
            PortToOpen.had_error = False
            
        if (PortToOpen.IsPortAvailable) and (PortToOpen.had_error == False): #port is available and operational 
            if self.CurrentPort is None:
                self.CurrentPort = PortToOpen #assign the requested port as the current port
                await self.CurrentPort.open()  #and open the requested serial port     
            else:
                if (self.CurrentPort.IsPortOpen() == False):
                    self.CurrentPort = PortToOpen #switch to the requested port
                    await self.CurrentPort.open()  #and open the requested serial port   
                else:
                    if self.CurrentPort.com_port != portname: #CurrentPort is a different port than we want
                        print("closing2 port: {}".format(self.CurrentPort.com_port))
                        self.CurrentPort.close()    #so close it
                        self.CurrentPort = PortToOpen #switch to the requested port
                        await self.CurrentPort.open()  #and open the requested serial port
                    #otherwise, we already have the requested port open, so ignore
        # If the port isn't available, or has failed due to an error, there is nothing we can do to open it        
    
    async def NextAvailablePort(self): #returns the name of the next available port
        while True:
            if self.CurrentPort is None:
                if self.Ports is not None:
                    for x in self.Ports:
                        if x.IsPortAvailable() and x.had_error == False:
                            return x
            else:
                FoundCurrentPort = False
                #loop through all valid ports after the currently-selected one
                for x in self.Ports:
                    if x.com_port == self.CurrentPort.com_port:
                        FoundCurrentPort = True
                    else:
                        if FoundCurrentPort:
                            #print("checkingavail of {}".format(x.com_port))
                            if x.IsPortAvailable() and x.had_error == False:
                                print("nextavaila1 is {}".format(x.com_port))
                                return x
                #loop through all ports, skipping only the one we are currently on. 
                for x in self.Ports:
                    if x.IsPortAvailable() and x.had_error == False:
                            print("nextavaila2 is {}".format(x.com_port))
                            return x    
            #print("waiting1")
            await asyncio.sleep(0.5)  #keep waiting for an available, non-erroneous port to show up        
        
    async def KeepTryingToOpenSerialPorts(self):
        #loop through available ports, trying them out
        #only try the ones that don't have a history of errors
        while True:
            print("KeepingTryingToOpenSerialPorts {}".format(self.CurrentPort))
            if (self.CurrentPort is not None):
                if self.CurrentPort.IsPortOpen() == True: #we already have an open port, nothing to do
                    await asyncio.sleep(1)
                    print("Finished sleeping in KTTOSP1")
                else:
                    myport = await self.NextAvailablePort()
                    print("Got the next available port as {}".format(myport.com_port))
                    await self.OpenNamedSerialPort(myport.com_port, clear_port_error_status = False)      
                    print("Finished sleeping in KTTOSP2")
            else: #the current port was None
                myport = await self.NextAvailablePort()
                print("Got the next available port from None as {}".format(myport.com_port))
                await self.OpenNamedSerialPort(myport.com_port, clear_port_error_status = False)    
                print("Finished opening Names Serial Port")
            print("waiting2")
            await asyncio.sleep(1)
            print("Finished sleeping in KTTOSP3")
 
    def StartService(self):
        print("trying first")
        #self.set_first_available_port()
        print("autofind")
        loop = asyncio.get_event_loop()
        loop.create_task(self.autoenumerate_ports())
        loop.create_task(self.KeepTryingToOpenSerialPorts())
        
    async def autoenumerate_ports(self):
        while True:
            print("autoenum")
            self._discover_ports_async() 
            print("sleeping for 1 sec before next autoenum")
            await asyncio.sleep(1)    
            print("time to wake up and do another autoenum")
            
    def CheckPort(self, myport):
        if myport is not None:
            myport.CheckPort()
    
    def start_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever() 
        
    # async def _discover_ports_async(self):
        # loop = asyncio.get_event_loop()
        ##this worked but I wanted the tasks to be done in parallel instead of just async 
        ##to avoid blocking calls that might take awhile to run
        # futures = []
        # for port in self.Ports:
            # #loop.create_task(asyncio.wait_for(self.CheckPort(port), timeout=0.01))
            # futures.append(self.CheckPort(port))
        # loop.create_task(asyncio.wait(futures, timeout=0.01))
     
    def _discover_ports_async(self):
        """
        This is a private utility method.
        This method attempts to discover the com ports that may be hosting Firmata

        :returns: Detected Comport
        """
        print("starting to set up port discovery")
        for port in self.Ports:
            if port.localworker is None:
                worker_loop = asyncio.new_event_loop()
                worker = Thread(target=self.start_loop, args=(worker_loop,))
                # Start the thread
                worker.daemon = True  #ensure the threads are killed when the process ends
                worker.start()
                port.localworker = worker
                port.localworker_loop = worker_loop
            port.localworker_loop.call_soon_threadsafe(self.CheckPort, port)
            
        print("finished setting up port discovery")

class Port:
    def __init__(self, parent=None, com_port=None, speed=57600, sleep_tune=.5):
        self._parent = parent
        self._IsPortOpen = False
        self._IsPortAvailable = False
        self.com_port = com_port
        self.sleep_tune = sleep_tune
        self.speed = speed
        self._timetocheck = 0  #how long did it take to check the port?
        self._start = time.time()
        self._end = time.time()
        self.localworker = None
        self.localworker_loop = None
        self._checked = False
        self.had_error = False
        self.my_serial = None
        
    def CheckPort(self): #checking to see if the port is available
        #print("Running CheckPort  {}   {}   {}".format(self._timetocheck, self._start, self._end))
        #print("checking port on {}".format(self.com_port))
        if self.com_port is not None:
            if self._IsPortOpen == False:
                #only very infrequency check ports that take too long to check
                #they are likely throwing an OS error
                if (self._timetocheck < 0.3) or ((self._end + self._timetocheck * 100) < time.time()):
                    self._start = time.time()
                    try:
                        serialport = serial.Serial(self.com_port, self.speed, timeout=10)
                        serialport.close()
                        print("found ports {}...{}".format(self.com_port, self._timetocheck))
                        self._MarkPortAvailable()
                    except serial.SerialException as e:
                        #print("error number {}".format(e))
                        self._MarkPortUnavailable()
                        pass
                    self._end = time.time()
                    self._timetocheck = self._end - self._start
                    #print("time to check {} was {}".format(self.com_port, self._timetocheck))
            else:
                self._MarkPortAvailable()
        else:
            self._MarkPortUnavailable()
        self._checked = True

    def IsPortAvailable(self):
        return self._IsPortAvailable
        
    def IsPortOpen(self):
        return self._IsPortOpen
        
    def _MarkPortAvailable(self):
        if self._IsPortAvailable == False:
            self._IsPortAvailable = True
            self.had_error = False #no known errors so far
            self._parent.AppendToPortList(self.com_port)
            
    def _MarkPortUnavailable(self):
        if self._IsPortAvailable:
            self._IsPortAvailable = False
            self._parent.RemoveFromPortList(self.com_port) 
        if self._IsPortOpen:
            self.my_serial.close()
            self._MarkPortClosed()

    async def _MarkPortOpen(self):
        if self._IsPortOpen == False:
            self._IsPortOpen = True
            await self._parent.PortOpened()

    def _MarkPortClosed(self):
        if self._IsPortOpen == True:
            self._IsPortOpen = False
            self._parent.PortClosed(self.com_port)
            
    def get_serial(self):
        return self.my_serial

    def HasBeenCheckedForAvailability(self):
        return self._checked
                    
    def write(self, data):
        """
        This is s call to pyserial write. It provides a
        write and returns the number of bytes written upon
        completion

        :param data: Data to be written
        :return: Number of bytes written
        """
        if self._IsPortAvailable and self._IsPortOpen:
            result = None
            try:
                result = self.my_serial.write(bytes([ord(data)]))
                print('Wrote {} on {}!'.format(ord(data),self.com_port))
            except serial.SerialTimeoutException:
                try:
                    self.had_error = True
                    self.my_serial.close()
                    self._MarkPortClosed()
                except:  
                    raise                
            except serial.SerialException:
                try:
                    self.had_error = True
                    self.my_serial.close()
                    self._MarkPortClosed()
                except:  
                    raise
            if result:
                return result
  
    async def readline(self):
        """
        This is an asyncio-adapted version of pyserial read.
        It provides a non-blocking read and returns a line of data read.

        :return: A line of data
        """
        # wait for a line to become available and read from
        # the serial port
        data = ""
        while True:
            try:
                newchar = await self.read()
                data += newchar
                if newchar == 10: #if "\n" newline character is encountered
                    return data
            except serial.SerialException:
                try:
                    self.had_error = True
                    self.my_serial.close()
                    self._MarkPortClosed()
                except:  
                    raise

    async def read(self):
        """
        This is an asyncio-adapted version of pyserial read
        that provides non-blocking read.

        :return: One character
        """

        # wait for a character to become available and read from
        # the serial port
        while True:
            if (self.my_serial is not None):
                print("attempting a read: is it inwaiting? {}".format(self.my_serial.inWaiting()))
                try:            
                    if not self.my_serial.inWaiting():
                        print("giving up on read for now")
                        await asyncio.sleep(self.sleep_tune)
                    else:
                        print("found some data for read")
                        data = self.my_serial.read()
                        print("returning data from read")
                        return ord(data)
                except serial.SerialException:
                    try:
                        self.had_error = True
                        self.my_serial.close()
                        self._MarkPortClosed()
                    except:  
                        raise
            else:
                print("There is no port to read from!!!!!!!!!!!!!  EEEEEEEK!")
                await asyncio.sleep(self.sleep_tune)
                print("Woke up from the read sleep...")

    def close(self):
        """
        Close the serial port
        """
        if self._IsPortAvailable and self._IsPortOpen:
            self.my_serial.close()
            print("closing up new: port {}".format(self.com_port))
            self._MarkPortClosed()

    async def open(self):
        """
        Open the serial port
        """

        if self._IsPortAvailable and (self._IsPortOpen == False):
            self.my_serial = serial.Serial(self.com_port, self.speed, timeout=1,
                                               writeTimeout=1)
            #self.my_serial.open()
            print("opening up new port: {} and clearing input output buffers".format(self.com_port))
            
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
            