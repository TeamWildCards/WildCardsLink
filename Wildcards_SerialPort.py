
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
        
        
        
    def AutoEnumerate(self)
        if self.localworker is None:
                worker_loop = asyncio.new_event_loop()
                worker = Thread(target=self.start_loop, args=(worker_loop,))
                # Start the thread
                worker.daemon = True  #ensure the threads are killed when the process ends
                worker.start()
                self.localworker = worker
                self.localworker_loop = worker_loop
            self.localworker_loop.call_soon_threadsafe(self.CheckPort, port)

    def start_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()             
            
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
            