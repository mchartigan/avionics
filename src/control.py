import sys, os
import time
import json, math
import queue
from collections import deque
from threading import Thread, Event
import logging
from math import atan, pi
import RPi.GPIO as GPIO
from array import *

sys.path.append(os.path.abspath(os.path.join('..', 'lib')))

from RadioModule import Module
from CommunicationsDriver import Comm

QDM_PIN = 13
IGNITION_PIN = 6
ROCKET_LOG_PIN = 22
STABILIZATION_PIN = 21

class Control:

    class Collection(Thread):
        """
        Spawn a Thread to repeat at a given interval
        Arguments:
            obj : a Function object to be executed
        """
        def __init__(self, function, freq):
            Thread.__init__(self, daemon=True)
            # Could be used to prematurely stop thread using self.trigger.set()
            self.trigger = Event()
            self.fn = function
            self.freq = freq

        def run(self):
            while not self.trigger.wait(1 / self.freq):
                self.fn()

    @staticmethod
    def generate_status_json():
        json = {}
        json["origin"] = "status"
        json["QDM"] = 0
        json["Ignition"] = 0
        json["Stabilization"] = 0
        return json

    def __init__(self, name):
        # Set up info logging
        self.console = logging.getLogger('control')
        _format = "%(asctime)s %(threadName)s %(levelname)s > %(message)s"
        logging.basicConfig(
            level=logging.INFO, filename='../logs/status_control.log', filemode='a+', format=_format
        )

        self.console.info(f"\n\n### Starting {name} ###\n")
        
        # Create a data queue
        self.gx_queue = deque([])
        self.gy_queue = deque([])
        self.gz_queue = deque([])
        self.time_queue = deque([])

        # GPIO SETUP
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(QDM_PIN, GPIO.OUT)
        GPIO.output(QDM_PIN, GPIO.LOW)  # Turn on QDM dead switch
        GPIO.setup(IGNITION_PIN, GPIO.OUT)
        GPIO.setup(ROCKET_LOG_PIN, GPIO.OUT)
        GPIO.output(ROCKET_LOG_PIN, GPIO.HIGH)
        GPIO.setup(STABILIZATION_PIN, GPIO.OUT)
        
        self.altitude = None
        # self.rocket = None

        time.sleep(2)
        self.c = Comm.get_instance(self)
        self.commands = queue.Queue(maxsize=10)
        self.c.bind(self.commands)

        self.json = None
        
        self.console.info("Initialization complete")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Specify cleanup procedure. Protects against most crashes
        """
        if exc_type is not None: self.console.critical(f"{exc_type.__name__}: {exc_value}")
        else: self.console.info("Control.py completed successfully.")
        GPIO.cleanup()

    def read_data(self, proxy):
        '''
        Reads data from Manager.list() given by sensors.py

        Arguments:
            proxy : list containing dict and time
        '''
        self.json = proxy[0]

        if self.json:
            self.send()  # send data over radio

            self.altitude = self.json['GPS']['alt']
            gx = self.json['gyro']['x']
            gy = self.json['gyro']['y']
            gz = self.json['gyro']['z']
            # time = balloon['time']

            if (len(list(self.gx_queue)) > 100): 
                self.gx_queue.popleft()
                self.gy_queue.popleft()
                self.gz_queue.popleft()
                # self.time_queue.popleft()
            
            self.gx_queue.append(gx)
            self.gy_queue.append(gy)
            self.gz_queue.append(gz)
            # self.time_queue.append(time)

            # print(f"{time} : {gx},{gy},{gz}")

            logging.debug("Data received")

    def send(self):
        """
        Sends most recent data collected over radio
        """
        # print("JSON: ", self.json)
        # hello = {"hello": 1}
        if self.json:
            self.c.send(self.json, "balloon")

    def lowpass_gyro(self):
        """
        TODO
        Implements a low-pass filter to accurately determine and return spinrate
        magnitude
        """
        length = len(list(self.gx_queue))
        gx, gy, gz = 0

        if length > 10:
            for i in range(10, 0, -1):
                gx += self.gx_queue[length - i] / 10
                gy += self.gy_queue[length - i] / 10
                gz += self.gz_queue[length - i] / 10
        else:
            gx = self.gx_queue[length - 1]
            gy = self.gy_queue[length - 1]
            gz = self.gz_queue[length - 1]

        return math.sqrt(gx**2 + gy**2 + gz**2)

    def launch_condition(self):
        '''
        Returns True if both spinrate and altitude are within spec.

        return result: launch condition true or false
        '''

        altitude = (self.altitude<=25500) & (self.altitude >= 24500)
        spinrate = self.lowpass_gyro()
        logging.info(f"Altitude: {self.altitude}m - Spinrate: {spinrate}dps")
        

        return (altitude & (spinrate < 5))

    def stabilization(self):
        """
        Checks ability to stabilize, dependent on altitude. Sends update to 
        ground station with action taken.
        """
        logging.info("Stabilization attempted")
        # Bounds hard-coded for "ease" of manipulation (not worth the effort)
        # condition = (self.altitude<=25500) & (self.altitude >= 24500)
        condition = True
        data = Control.generate_status_json()

        if (condition):
            GPIO.output(STABILIZATION_PIN, GPIO.HIGH)
            print("stabilization")
            data["Stabilization"] = 1
            logging.info("Stabilization initiated")
        else:
            logging.error(f"Stabilization failed: altitude {self.altitude}m not within bounds")
        
        self.c.send(data, "status")
        
    def ignition(self, mode):
        '''
        This checks condition and starts ignition
        Parameters: - mode: test mode or pre-launch mode
                    - datarange: compare data btw two computers
                    - datain: data from sensors

        test mode: flow current for 0.1 sec
        pre-launch mode: flow current for 10 sec

        return void
        '''
        logging.info("Ignition attempted")
        data = Control.generate_status_json()

        # launch = self.launch_condition()
        launch = True
        if launch:
            data["Ignition"] = 1

            if (mode == 1):  # testing mode (avoid igniting motor)
                GPIO.output(IGNITION_PIN, GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(IGNITION_PIN, GPIO.LOW)
                logging.info("Ignition initiated (testing)")

            elif (mode == 2):  # Ignite motor
                GPIO.output(ROCKET_LOG_PIN, GPIO.LOW)
                time.sleep(5)  # tell rocket to start logging and give appropriate time
                print("ign out")
                GPIO.output(IGNITION_PIN, GPIO.HIGH)
                time.sleep(10)  # Needs to be experimentally verified
                GPIO.output(IGNITION_PIN, GPIO.LOW)
                logging.info("Ignition initiated")
        else:
            logging.error("Ignition failed: altitude and/or spinrate not within tolerance")

        self.c.send(data, "status")

    def qdm_check(self, QDM):
        '''
        This checks if we need to QDM.
        Parameter: QDM

        if QDM = 0, QDM initiated
        else, do nothing

        return void
        '''

        if QDM:
            GPIO.output(QDM_PIN, GPIO.LOW)
        else:
            GPIO.output(QDM_PIN, GPIO.HIGH)

            data = Control.generate_status_json()
            data["QDM"] = 1
            print("qdm")
            self.c.send(data, "status")
            logging.info("QDM initiated")

    def connection_check(self):
#        return self.c.remote_device
        return True
    

if __name__ == "__main__":
    """
    Controls all command processes for the balloon flight computer.
    """
    print("Running control.py ...\n")

    with Control("balloon") as ctrl:
        mode = 2 # mode 1 = testmode / mode 2 = pre-launch mode

        # Can't collect data in only this file

        while True:
            # Control loop to determine radio disconnection
            result = ctrl.connection_check()
            endT = datetime.now() + timedelta(seconds=300)  # Wait 5 min. to reestablish signal
            while ((result == None) & (datetime.now() < endT)):
                result = ctrl.connection_check()
                sleep(0.5)  # Don't overload CPU

            # These don't need to be parallel to the radio connection, since we won't
            # be getting commands if the radio is down
            if result == 0:
                ctrl.qdm_check(0)
            else:
                # Receive commands and iterate through them
                ctrl.receive_data()
                while not ctrl.commands.empty():
                    GSDATA = ctrl.commands.get()

                    CType = GSDATA['command']
                    if (CType == 'QDM'):
                        ctrl.qdm_check(0)
                    # Are ignition and stabilize same signal?
                    if (CType == 'Stabilize'):
                        ctrl.stabilization()
                    if (CType == 'Ignition'):
                        ctrl.ignition(mode)
