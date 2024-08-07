#import RPi.GPIO as GPIO
import threading
import time
import gpiod
#from gpiod.line import Direction
import select

from datetime import timedelta
from gpiod.line import Bias, Edge
import os

#class FilamentMotionSensorTimeoutDetection(threading.Thread):
class SmartFilamentSensorGPIOThread(threading.Thread):
    used_pin = -1
    max_not_moving_time = -1
    keepRunning = True

    # Initialize FilamentMotionSensor
    def __init__(self, threadID, threadName, pUsedPin, pMaxNotMovingTime, pLogger, pData, pCallback=None):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = threadName
        self.callback = pCallback
        self._logger = pLogger
        self._data = pData

        self.max_not_moving_time = pMaxNotMovingTime
        self._data.last_motion_detected = time.time()
        self.keepRunning = True
        ''' depreciated
        # Remove event, if already an event was set
        try:
            GPIO.remove_event_detect(self.used_pin)
        except:
            self._logger.warn("Pin " + str(pUsedPin) + " not used before")
            
        GPIO.add_event_detect(self.used_pin, GPIO.BOTH, callback=self.motion)
        '''
        #os.uname().nodename
        rpi_model = os.uname().nodename
        self.chip_address = '/dev/gpiochip4' if (rpi_model=='rpi5') else '/dev/gpiochip0'
        self._logger.debug("RPi model: " + rpi_model + ". GPIO chip address:", self.chip_address + ". Configured sensor pin:" + str(pUsedPin))

        self.used_pin = pUsedPin

    # Override run method of threading
    def run(self):

        self._data.last_motion_detected = time.time()
        line_gpio_pin = self.used_pin
        with gpiod.request_lines( self.chip_address,  consumer="motion-sensor-line-value", config={ line_gpio_pin: gpiod.LineSettings( edge_detection=Edge.BOTH, bias=Bias.PULL_UP, debounce_period=timedelta(milliseconds=10), ) }, ) as request:
            poll = select.poll()
            poll.register(request.fd, select.POLLIN)

                
            while self.keepRunning:

                # Other fds could be registered with the poll and be handled
                # separately using the return value (fd, event) from poll()
                poll.poll(250)
                
                if request.wait_edge_events(0.25):
                    for event in request.read_edge_events():
                        

                        print( "line_gpio_pin: {} event #{}".format( event.line_offset, event.line_seqno ) )
                        if (event.line_offset==self.used_pin):
                            self._data.last_motion_detected = time.time()
                            self.callback(True)
                            self._logger.debug("Motion detected at " + str(self._data.last_motion_detected))

                timespan = (time.time() - self._data.last_motion_detected)

                if (timespan > self.max_not_moving_time):
                    if(self.callback != None):
                        self.callback(False)

                

            poll.unregister(request.fd)



    ''' depreciated
    # Eventhandler for GPIO filament sensor signal
    # The new state of the GPIO pin is read and determinated.
    # It is checked if motion is detected and printed to the console.
    def motion(self, pPin):
        self._data.last_motion_detected = time.time()
        self.callback(True)
        self._logger.debug("Motion detected at " + str(self._data.last_motion_detected))
    '''


