#!/usr/bin/env python
from PyTango import *
from PyQt4.QtCore import *
from time import sleep

def main():
    try:
        tango = DeviceProxy("tango://haspp02oh1:10000/p02/keithley3706/eh2b.01")
        print(tango)
        print(tango.info())
        print(tango.status())
        print("device is %s"%tango.state())
        admname = tango.adm_name()
        print("Control Server: %s"%admname)
        adm = DeviceProxy(admname)
        print(adm.info())
        print(adm.status())
        print("adm is %s\n"%adm.state())

    except DevFailed, error:
        print("a pity indeed - no access to the device")
        exit(0)

    tng = TangoObject("tango://haspp02oh1:10000/p02/keithley3706/eh2b.01", "tango://haspp02oh1.desy.de:10000/dserver/Keithley3706/EH2B")
    print("\t admstate is %s; devstate is %s;"%tng.initDevice())
    print(tng.makeMeasurement())

#Tango object - communication, etc
class TangoObject(QObject):
    def __init__(self, devname, admname, parent=None):
        super(TangoObject, self).__init__(parent)
        self.initDeviceName(devname, admname)
    
    # save device names
    def initDeviceName(self, devname, admname):
        (self.ch1, self.ch2, self.ch3, self.ch4) = (0,0,0,0)
        #setup device and its admin object name
        self.devname = devname
        self.admname = admname
    
    # init device - run as a check - if device is there, is it's service is there, is the device connected
    def initDevice(self):
        #check adm - running or not
        (admstate, devstate)= (self.getTangoState(self.admname), False)

       # if adm state is ok - try to see if we have device state OK
        if(admstate):
            devstate = self.getTangoState(self.devname)
        else:
            #kindly ask user to start server through tango
            return (admstate, devstate)

        # simple (not elaborative) check if we can set parameters to Keithley (default units: 2, TC: 1)
        if(devstate):
            state = self.setupKeithley3706()
        
        # if adm is on, but some trouble with a device (it is not ON or cannot setup initial values - reboot device, reboot server) 
        # try to reboot adm server, reboot keithley and get a connection to device
        # kindly ask user to reboot Keithley, wait for it to start up
        if(not devstate and admstate):
            devstate = self.restartDevice(self.admname, self.devname) # should come to life

        return (admstate, devstate)

    def initDummy(self):
        return 0
    
    def measDummy(self):
        return gauss(20, 0.1)
    
    def measDevice(self):
        return  self.measureKeithley3706()
        
    
    def initMeasurement(self):
        return self.initDevice()
    
    
    def makeMeasurement(self):
        return self.measDevice()
    
    # thorough check of a device state 
    def getTangoState(self, tangoname):
        state = False
        try:
            dev = DeviceProxy(tangoname)
            if(dev.state()==DevState.ON):
                state = True
        except DevError, error:
            state = False
        return state
    
    # setup Keithley 3706 measurement
    # make device setup units and Tc several times to make sure it responds
    def setupKeithley3706(self):
        dev = DeviceProxy(self.devname)
        (oldunits, oldtc) = (dev.read_attribute("Units"), dev.read_attribute("Thermocouple"))
        
        (settc, setunits) = (1, 3)
        
        # initial setup - step 1
        if(oldtc!=settc):
           dev.command_inout("SetMeasurement")
           dev.write_attribute("Thermocouple", 0)
        
        if(oldunits!=setunits):
            dev.command_inout("SetMeasurement")
            dev.write_attribute("Units", 0)
        
        (oldunits, oldtc) = (dev.read_attribute("Units"), dev.read_attribute("Thermocouple"))
        
        # final setup - step 2
        if(oldtc!=settc):
           dev.command_inout("SetMeasurement")
           dev.write_attribute("Thermocouple", settc)
        
        if(oldunits!=setunits):
            dev.command_inout("SetMeasurement")
            dev.write_attribute("Units", setunits)
            
        (units, tc) = (dev.read_attribute("Units"), dev.read_attribute("Thermocouple"))
        
        #check settings - if different from settc and setunits - probably we need to restart the device
        state = False
        if(oldunits!=setunits and oldtc==settc):
            state = True
        return state

    # measuring is less protected than check procedure
    # check device state - simple check, function returns flag to discriminate error state
    # o give a hint to the user
    def measureKeithley3706(self):
        #check device state
        state = self.getTangoState(self.devname)
        if(not state):
            return (False, 0, 0, 0, 0)
        
        dev = DeviceProxy(self.devname)
        dev.command_inout("StartMeasurement")
        
        #simple loop, can make a timeout loop
        while(dev.state()!=DevState.ON):
            continue
        
        return (True, dev.read_attribute("ValueCh1").value, dev.read_attribute("ValueCh2").value, dev.read_attribute("ValueCh3").value, dev.read_attribute("ValueCh4").value)
    
    # restart device server using name of the device and its server 
    def restartDevice(self, tangoadmname, tangodevname):
        (admstate, devstate) = (False, False)
        adm = DeviceProxy(tangoadmname)
        
        adm.command_inout("RestartServer")

        # wait for adm to come back to life
        # we hope, otherwise - will be endless loop
        # we wait until the server really comes back online
        # unlike the case of the device it is highly unlikely that server will not get DevState.ON
        while(admstate != DevState.ON):
            try:
                admstate = adm.state()
            except DevFailed, error:
                continue
            except DevError, error:
                continue
        
        if(admstate == DevState.ON):
            admstate = True
        else:
            admstate = False

        # wait for the device to come back to life
        # we hope, otherwise - will be endless loop
        # wait just until the device comes back to life 
        # the state can be different from DevState.ON
        bflag = False
        while(not bflag):
            try:
                devstate = self.getState()    #throws exceptions unless the device is alive
                bflag = True    #breaks the loop than the device comes to life
            except DevFailed, error:
                continue
            except DevError, error:
                continue

        if(devstate !=DevState.ON):
                devstate = False
        else:
                devstate = True
            
        return (admstate, devstate)

if __name__ == '__main__':
    main()
