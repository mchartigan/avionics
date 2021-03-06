import serial
import json
import time
import sys, os
sys.path.append(os.path.abspath(os.path.join('..', 'logs')))

import mpu9250

# from RadioModule import Module

class SerialPort():
    """
    Object to control serial port functionality.
    """

    def __init__(self, name, port):
        """
        Initializes the Port object

        Args:
            name: String ID for serial port 
            port: USB connection for Arduino in '/dev/tty*'
            manager: A Manager() dict object passed through by config.py
        """
        print("Initializing {} at port {}...".format(name, port))
        self.name = name
        self.port = port
        self.json = {"Altitude": 0,   # Initialize dictionary structure
        "GPS": {
            "longitude": 0,
            "latitude": 0
            },
        "Gyroscope": {
            "x": 0,
            "y": 0,
            "z": 0
            },
        "Magnetometer": {
            "x": 0,
            "y": 0,
            "z": 0
            },
        "Temperature": 0,
        "Accelerometer": {
            "x": 0,
            "y": 0,
            "z": 0
            }
        }

        # Open log file
        try:
            os.remove('../logs/data.log')
        except FileNotFoundError:
            pass
        
        self.log = open('../logs/data.log', 'a+')
        # Write header
        self.log.write('time (s),pressure,long,lat,g_x (dps),g_y (dps),g_z (dps),m_x (mT),m_y (mT),m_z (mT),temp (C),a_x (mg),a_y (mg),a_z (mg)\n')

        self.ser = serial.Serial(self.port, 115200)
 
        """
        try:
            self.radio = Module.get_instance(self)  # Initialize radio communication
        except Exception as e:
            print(e)
        """
        self.startTime = time.time()
        print(f'Starting at {self.startTime}s.')
        print("Initialization complete.")

    def writeDict(self):
        """
        Reads from Serial connection and writes to dict
   
        gyroX, gyroY, gyroZ = readGyro()
        magX, magY, magZ = readMagnet()
        gpsLat, gpsLong, gpsAlt = readGPS()
        accelX, accelY, accelZ = readAccel()
        temp = readTemperature()
        """
        try:
            ln = self.ser.readline().decode('utf-8').rstrip()
            if ln.split(':')[0] == "ERROR":
                pass
            else:
                self.log.write('{:.4f}, {}\n'.format(time.time()-self.startTime, ln))

        except UnicodeDecodeError as e:
            self.log.write(f'{e}\n')
            print(f'{e}\n')
            
        
        """
        # Assigning each value in given list to dict entry
        self.json["Altitude"] = gpsAlt
        self.json["GPS"]["longitude"] = gpsLong
        self.json["GPS"]["latitude"] = gpsLat
        self.json["Gyroscope"]["x"] = gyroX
        self.json["Gyroscope"]["y"] = gyroY
        self.json["Gyroscope"]["z"] = gyroZ
        self.json["Magnetometer"]["x"] = magX
        self.json["Magnetometer"]["y"] = magY
        self.json["Magnetometer"]["z"] = magZ
        self.json["Temperature"] = temp
        self.json["Accelerometer"]["x"] = accelX
        self.json["Accelerometer"]["y"] = accelY
        self.json["Accelerometer"]["z"] = accelZ
        """

    def JSONpass(self, manager):
        """
        Overwrites dict with sensor data and sends over radio

        Args:
            manager: A Manager() dict object passed through by config.py
        """
        self.writeDict()

        # This is straight up cancerous, but the way dict management works between
        # processes requires the dict to be reassigned to notify the DictProxy
        # of changes to itself
        time.sleep(0.01)
        temp = manager[0]
        temp = self.json
        # Reassign here
        manager[0] = temp

        """
        try:
            self.radio.send(json.dumps(self.json))  # Send json over radio
        except Exception as e:
            print(e)
        """

    def speedTest(self, dur):
        """
        Tests the speed of data acquisition from Arduino for a given time.

        Args:
            dur: duration (in seconds) of test
        """
        start = time.time()
        i = 0
        while time.time() < start + dur:
            self.writeDict()
            i = i + 1
        print("\nPolling rate: {} Hz\n".format(i / dur))


    def readAccel(self):
        """
        Reads acceleration from the MPU9250 chip
        """
        return self.imu.accel()

    def readGyro(self):
        """
        Reads gyroscopic data from the MPU9250 chip
        """
        return self.imu.gyro()

    def readMagnet(self):
        """
        Read magnetometer data from the MPU9250 chip
        """
        return self.imu.mag()

    def readTemperature(self):
        """
        Reads temperature data from the MS5611 chip
        """
        return self.imu.temp()

    def readGPS(self):
        """
        Reads GPS data from the NEO7M chip
        """
        return (longitude, latitude, altitude)
