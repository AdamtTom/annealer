#!/usr/bin/python
from machine import Pin
import utime
import math

class MAX31855(object):
    '''MicroPython driver for [MAX38155 Cold-Junction Compensated Thermocouple-to-Digital Converter](http://www.maximintegrated.com/datasheet/index.mvp/id/7273)
    '''
    def __init__(self, so_pin=21, cs_pin=22, sck_pin=23, units = "c"):
        '''Initialize Soft (Bitbang) SPI bus

        Parameters:
        - so_pin:  Data input (SO / MOSI) pin (Any GPIO)
        - cs_pin:    Chip Select (CS) / Slave Select (SS) pin (Any GPIO)
        - sck_pin: Clock (SCLK / SCK) pin (Any GPIO)
        - units:     (optional) unit of measurement to return. ("c" (default) | "k" | "f")
        '''
        self.cs = Pin(cs_pin, Pin.OUT)
        self.so = Pin(so_pin, Pin.IN)
        self.sck = Pin(sck_pin, Pin.OUT)
        self.units = units
        self.data = None
        self.noConnection = self.shortToGround = self.shortToVCC = self.unknownError = False

        self.cs.on()
        self.so.off()
        self.sck.off()

    def readCelsius(self):
        '''Reads SPI bus and returns current value of thermocouple.'''
        self.read()
        self.checkErrors()
        return self.data_to_LinearizedTempC()

    def readFahrenheit(self):
        return self.readCelsius() * 9.0/5.0 + 32

    def read_rj_Celsius(self):
        '''Reads SPI bus and returns current value of reference junction.'''
        self.read()
        return self.data_to_rj_temperature()

    def read_rj_Fahrenheit(self):
        '''Reads SPI bus and returns current value of reference junction.'''
        self.read()
        return self.data_to_rj_temperature() * 9.0/5.0 + 32
    
    delayus = 20
    
    def read(self):
        '''Reads 32 bits of the SPI bus & stores as an integer in self.data.'''
        bytesin = 0
        # Select the chip
        self.cs.off()
        utime.sleep_us(self.delayus)
        # Read in 32 bits
        for i in range(32):
            self.sck.off()
            utime.sleep_us(self.delayus)
            bytesin = bytesin << 1
            if (self.so.value()):
                bytesin = bytesin | 1
            self.sck.on()
            utime.sleep_us(self.delayus)
        # Unselect the chip
        self.cs.on()
        # Save data
        self.data = bytesin

    def checkErrors(self, data_32 = None):
        '''Checks error bits to see if there are any SCV, SCG, or OC faults'''
        if data_32 is None:
            data_32 = self.data
        anyErrors = (data_32 & 0x10000) != 0    # Fault bit, D16
        if anyErrors:
            self.noConnection = (data_32 & 0x00000001) != 0       # OC bit, D0
            self.shortToGround = (data_32 & 0x00000002) != 0      # SCG bit, D1
            self.shortToVCC = (data_32 & 0x00000004) != 0         # SCV bit, D2
            self.unknownError = not (self.noConnection | self.shortToGround | self.shortToVCC)    # Errk!
        else:
            self.noConnection = self.shortToGround = self.shortToVCC = self.unknownError = False

    def data_to_tc_temperature(self, data_32 = None):
        '''Takes an integer and returns a thermocouple temperature in celsius.'''
        if data_32 is None:
            data_32 = self.data
        tc_data = ((data_32 >> 18) & 0x3FFF)
        return self.convert_tc_data(tc_data)

    def data_to_rj_temperature(self, data_32 = None):
        '''Takes an integer and returns a reference junction temperature in celsius.'''
        if data_32 is None:
            data_32 = self.data
        rj_data = ((data_32 >> 4) & 0xFFF)
        return self.convert_rj_data(rj_data)

    def convert_tc_data(self, tc_data):
        '''Convert thermocouple data to a useful number (celsius).'''
        if tc_data & 0x2000:
            # two's compliment
            without_resolution = ~tc_data & 0x1FFF
            without_resolution += 1
            without_resolution *= -1
        else:
            without_resolution = tc_data & 0x1FFF
        return without_resolution * 0.25

    def convert_rj_data(self, rj_data):
        '''Convert reference junction data to a useful number (celsius).'''
        if rj_data & 0x800:
           without_resolution = ~rj_data & 0x7FF
           without_resolution += 1
           without_resolution *= -1
        else:
             without_resolution = rj_data & 0x7FF
        return without_resolution * 0.0625

    def data_to_LinearizedTempC(self, data_32 = None):
        '''Return the NIST-linearized thermocouple temperature value in degrees
        celsius. See https://learn.adafruit.com/calibrating-sensors/maxim-31855-linearization for more infoo.
        This code came from https://github.com/nightmechanic/FuzzypicoReflow/blob/master/lib/max31855.py
'''
        if data_32 is None:
            data_32 = self.data
        #       extract TC temp
        #       Check if signed bit is set.
        if data_32 & 0x80000000:
            # Negative value, take 2's compliment. Compute this with subtraction
            # because python is a little odd about handling signed/unsigned.
            data_32 >>= 18
            data_32 -= 16384
        else:
            # Positive value, just shift the bits to get the value.
            data_32 >>= 18
        # Scale by 0.25 degrees C per bit and return value.
        TC_temp =  data_32 * 0.25
        # Extract Internal Temp
        data_32 = self.data
        # Ignore bottom 4 bits of thermocouple data.
        data_32 >>= 4
        # Grab bottom 11 bits as internal temperature data.
        Internal_Temp= data_32 & 0x7FF
        if data_32 & 0x800:
            # Negative value, take 2's compliment. Compute this with subtraction
            # because python is a little odd about handling signed/unsigned.
            Internal_Temp -= 4096
        # Scale by 0.0625 degrees C per bit and return value.
        Internal_Temp = Internal_Temp * 0.0625

        # MAX31855 thermocouple voltage reading in mV
        thermocoupleVoltage = (TC_temp - Internal_Temp) * 0.041276
        # MAX31855 cold junction voltage reading in mV
        coldJunctionTemperature = Internal_Temp
        coldJunctionVoltage = (-0.176004136860E-01 +
            0.389212049750E-01  * coldJunctionTemperature +
            0.185587700320E-04  * math.pow(coldJunctionTemperature, 2.0) +
            -0.994575928740E-07 * math.pow(coldJunctionTemperature, 3.0) +
            0.318409457190E-09  * math.pow(coldJunctionTemperature, 4.0) +
            -0.560728448890E-12 * math.pow(coldJunctionTemperature, 5.0) +
            0.560750590590E-15  * math.pow(coldJunctionTemperature, 6.0) +
            -0.320207200030E-18 * math.pow(coldJunctionTemperature, 7.0) +
            0.971511471520E-22  * math.pow(coldJunctionTemperature, 8.0) +
            -0.121047212750E-25 * math.pow(coldJunctionTemperature, 9.0) +
            0.118597600000E+00  * math.exp(-0.118343200000E-03 * math.pow((coldJunctionTemperature-0.126968600000E+03), 2.0)))
        # cold junction voltage + thermocouple voltage
        voltageSum = thermocoupleVoltage + coldJunctionVoltage
        # calculate corrected temperature reading based on coefficients for 3 different ranges
        # float b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10;
        if voltageSum < 0:
            b0 = 0.0000000E+00
            b1 = 2.5173462E+01
            b2 = -1.1662878E+00
            b3 = -1.0833638E+00
            b4 = -8.9773540E-01
            b5 = -3.7342377E-01
            b6 = -8.6632643E-02
            b7 = -1.0450598E-02
            b8 = -5.1920577E-04
            b9 = 0.0000000E+00
        elif voltageSum < 20.644:
            b0 = 0.000000E+00
            b1 = 2.508355E+01
            b2 = 7.860106E-02
            b3 = -2.503131E-01
            b4 = 8.315270E-02
            b5 = -1.228034E-02
            b6 = 9.804036E-04
            b7 = -4.413030E-05
            b8 = 1.057734E-06
            b9 = -1.052755E-08
        elif voltageSum < 54.886:
            b0 = -1.318058E+02
            b1 = 4.830222E+01
            b2 = -1.646031E+00
            b3 = 5.464731E-02
            b4 = -9.650715E-04
            b5 = 8.802193E-06
            b6 = -3.110810E-08
            b7 = 0.000000E+00
            b8 = 0.000000E+00
            b9 = 0.000000E+00
        else:
            # TODO: handle error - out of range
            return 0
        return (b0 +
            b1 * voltageSum +
            b2 * pow(voltageSum, 2.0) +
            b3 * pow(voltageSum, 3.0) +
            b4 * pow(voltageSum, 4.0) +
            b5 * pow(voltageSum, 5.0) +
            b6 * pow(voltageSum, 6.0) +
            b7 * pow(voltageSum, 7.0) +
            b8 * pow(voltageSum, 8.0) +
            b9 * pow(voltageSum, 9.0))


class MAX31855Error(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)
