#!/usr/bin/env python
# written by Konstantin Glazyrin 
# GPL license applies

from __future__ import division
import os
import sys
import time
from PyQt4.QtCore import *
from PyQt4.QtGui import *
#from PyTango import *

#import dummy stuf
from random import gauss
from math import sqrt

#qwt import
from PyQt4.Qwt5.qplt import *

#PyTango
from PyTango import *

#constants - labels
BTNSTARTM1 = "Start Meas."
BTNSTARTM2 = "Stop Meas."
BTNSTARTW1 = "Start Save"
BTNSTARTW2 = "Stop Save"

#constants - graph window shows data no older than TIMELIMIT in msecs
TIMELIMIT = 1800000

# TANGO ACCESS
K3706DEVICE = "tango://haspp02oh1:10000/p02/keithley3706/eh2b.01"
K3706ADM = "tango://haspp02oh1.desy.de:10000/dserver/Keithley3706/EH2B"

DISCLAMER = """-- gui for measurements - specific for Keithley 3706 --
-- GPL licence applies - as we use QT library for free --

version 0.6
0.6 imporvement - change of vertical axis scale from default (autoscale)
0.5 improvement - a choice from sensor types and unit settings is available
0.4 improvement - fixed Keithley overflow message (intrinsic bug - Keithley - Tango communication)
0.3 improvement - updated TangoObject - implemented real device
0.2 improvement - graph window (python 2.6!!!)
0.1 improvement - basic gui
coding by Konstantin Glazyrin
contact lorcat@gmail.com for questions, comments and suggestions 
"""

# thermocouple units
# thermocouple settings used to setup Keithley device
TCSET = {0: "J", 1: "K", 2:"T", 3:"D", 4:"R", 5:"S", 6:"B", 7:"N"}
UNITSSET = {0:"Volts", 1:"dB", 2:"Celsius", 3:"Kelvin", 4:"Fahrenheit"}

# default values for graph y axis scalng
(PLOTYMIN, PLOTYMAX) = (250., 400.)

class Form(QMainWindow):
#
# Class constructor
#
    def __init__(self, parent=None, app=None):
        super(Form, self).__init__(parent)
        self.initVars(app)
        self.initUi()

        # special threads
        # device state check thread - called by btnsetup
        self.thCheck = ThreadCheck(self.tango, (self.btnstartonce, self.btnstart, self.btnstartwrite, self.btnsetup, self.btnkicktango), self)

        # brutal tango server reboot thread
        self.thKickTango = ThreadKickTango(self.tango, (self.btnstartonce, self.btnstart, self.btnstartwrite, self.btnsetup, self.btnkicktango), self)

        # final step
        # signals to be used by threads and other things
        self.prepareSignals()

#
#Class initialization
#
    def initVars(self, app=None):
        self.app = app

        #tango object Device - first, adm server - second, self - third for messages
        self.tango = TangoObject(K3706DEVICE, K3706ADM, self)

        # current path
        self.dir = QDir.currentPath()

        #window with graph
        self.graph = TCGraph("Thermocouple Runner", self)

        #data saving writer thread
        self.thWrite = ThreadWriteWrapper()

        #measurement thread - pass wrapper be reference, so if the writer thread will change - we will not see that
        self.thMeas = ThreadMeasure(self.tango, self.thWrite)

        #set of measured and tracked data - this data gets written
        self.dataset = {"ch1": [], "ch2": [], "ch3": [], "ch4": [], 
                        "ch1mean":0, "ch2mean":0, "ch3mean":0, "ch4mean":0,
                        "ch1std": 0, "ch2std": 0, "ch3std": 0, "ch4std": 0,
                        "ch1sum":0,"ch2sum":0,"ch3sum":0,"ch4sum":0,
                        "ch1track": Qt.Unchecked, "ch2track": Qt.Unchecked,"ch3track": Qt.Unchecked,"ch4track": Qt.Unchecked}
        self.datasetlock = QMutex()

        # set of data for visualizing in the graph - just visualizing 
        # data format ts: [ch1..ch4]
        self.datagraph = {}
        self.datagraphmutext = QMutex()

        # Graph window coords
        self.posgraph = None
    
    def initUi(self):
    
        #background - color
        pal = QPalette()
        self.setAutoFillBackground(True)
        pal.setColor(QPalette.Window, QColor('orange').light())
        self.setPalette(pal)

        QWidget
        #size
        self.resize(550, 300)
        self.setWindowTitle("Keithley3706 control")

        #main central widget
        cntWidget = QWidget()
        
        #main grid
        grid = QGridLayout()
        gbleft = QGroupBox("\tTemperature\t")
        gbabovebottom = QGroupBox("\tSensor Control\t")
        gbbottom = QGroupBox("\tControl\t")
        grid.addWidget(gbleft, 0, 0)
        grid.addWidget(gbabovebottom, 1, 0)
        grid.addWidget(gbbottom, 2, 0)

        # font for comboboxes
        #font4cb = QFont("Arial", 12, QFont.DemiBold)
        #gbleft.setFont(font4cb)
        #gbabovebottom.setFont(font4cb)
        #gbbottom.setFont(font4cb)
        gbabovebottom.setFlat(True)
        
        #status bar
        self.status = self.statusBar()
        self.status.setSizeGripEnabled(False)
        
        #left grid
        gbleft_grd = QGridLayout()

        self.ch1 = QLabel("0.0");
        self.ch2 = QLabel("0.0");
        self.ch3 = QLabel("0.0");
        self.ch4 = QLabel("0.0");

        self.ch1cp = QToolButton();
        self.ch2cp = QToolButton();
        self.ch3cp = QToolButton();
        self.ch4cp = QToolButton();

        self.ch1cp.setToolTip("Copy Ch1 values to Clipboard")
        self.ch2cp.setToolTip("Copy Ch2 values to Clipboard")
        self.ch3cp.setToolTip("Copy Ch3 values to Clipboard")
        self.ch4cp.setToolTip("Copy Ch4 values to Clipboard")

        # check boxes to track values measured
        self.ch1track = QCheckBox("");
        self.ch1track.setCheckState(self.dataset["ch1track"])
        self.ch2track = QCheckBox("");
        self.ch2track.setCheckState(self.dataset["ch2track"])
        self.ch3track = QCheckBox("");
        self.ch3track.setCheckState(self.dataset["ch3track"])
        self.ch4track = QCheckBox("");
        self.ch4track.setCheckState(self.dataset["ch4track"])

        self.ch1track.setToolTip("Check to start tracking Ch1 values")
        self.ch2track.setToolTip("Check to start tracking Ch2 values")
        self.ch3track.setToolTip("Check to start tracking Ch3 values")
        self.ch4track.setToolTip("Check to start tracking Ch4 values")

        self.ch1mean = QLabel("0.0");
        self.ch2mean = QLabel("0.0");
        self.ch3mean = QLabel("0.0");
        self.ch4mean = QLabel("0.0");

        self.ch1std = QLabel("0.0");
        self.ch2std = QLabel("0.0");
        self.ch3std = QLabel("0.0");
        self.ch4std = QLabel("0.0");

        self.ch1cpmean = QToolButton();
        self.ch2cpmean = QToolButton();
        self.ch3cpmean = QToolButton();
        self.ch4cpmean = QToolButton();

        self.ch1cpmean.setToolTip("Copy Ch1 mean + std values to Clipboard")
        self.ch2cpmean.setToolTip("Copy Ch2 mean + std values to Clipboard")
        self.ch3cpmean.setToolTip("Copy Ch3 mean + std values to Clipboard")
        self.ch4cpmean.setToolTip("Copy Ch4 mean + std values to Clipboard")

        #adjust labels width
        
        self.setLabMinWidth((self.ch4std, self.ch3std, self.ch2std, self.ch1std, self.ch4mean, self.ch3mean, self.ch2mean, self.ch1mean,
            self.ch4, self.ch3, self.ch2, self.ch1))

        #just labels naming the columns
        gbleft_grd.addWidget(QLabel("Channel #:"), 0, 0)
        gbleft_grd.addWidget(QLabel("Value:"), 0, 1)
        gbleft_grd.addWidget(QLabel("Cp."), 0, 2)
        gbleft_grd.addWidget(QLabel("Trk."), 0, 3)
        gbleft_grd.addWidget(QLabel("Mean Value:"), 0, 4)
        gbleft_grd.addWidget(QLabel("Std:"), 0, 6)
        gbleft_grd.addWidget(QLabel("Cp."), 0, 7)

        gbleft_grd.addWidget(QLabel("Channel 1"), 1, 0)
        gbleft_grd.addWidget(self.ch1, 1, 1)
        gbleft_grd.addWidget(self.ch1cp, 1, 2)
        gbleft_grd.addWidget(self.ch1track, 1, 3)
        gbleft_grd.addWidget(self.ch1mean, 1, 4)
        gbleft_grd.addWidget(QLabel("+/-"), 1, 5)
        gbleft_grd.addWidget(self.ch1std, 1, 6)
        gbleft_grd.addWidget(self.ch1cpmean, 1, 7)

        gbleft_grd.addWidget(QLabel("Channel 2"), 2, 0)
        gbleft_grd.addWidget(self.ch2, 2, 1)
        gbleft_grd.addWidget(self.ch2cp, 2, 2)
        gbleft_grd.addWidget(self.ch2track, 2, 3)
        gbleft_grd.addWidget(self.ch2mean, 2, 4)
        gbleft_grd.addWidget(QLabel("+/-"), 2, 5)
        gbleft_grd.addWidget(self.ch2std, 2, 6)
        gbleft_grd.addWidget(self.ch2cpmean, 2, 7)


        gbleft_grd.addWidget(QLabel("Channel 3"), 3, 0)
        gbleft_grd.addWidget(self.ch3, 3, 1)
        gbleft_grd.addWidget(self.ch3cp, 3, 2)
        gbleft_grd.addWidget(self.ch3track, 3, 3)
        gbleft_grd.addWidget(self.ch3mean, 3, 4)
        gbleft_grd.addWidget(QLabel("+/-"), 3, 5)
        gbleft_grd.addWidget(self.ch3std, 3, 6)
        gbleft_grd.addWidget(self.ch3cpmean, 3, 7)

        gbleft_grd.addWidget(QLabel("Channel 4"), 4, 0)
        gbleft_grd.addWidget(self.ch4, 4, 1)
        gbleft_grd.addWidget(self.ch4cp, 4, 2)
        gbleft_grd.addWidget(self.ch4track, 4, 3)
        gbleft_grd.addWidget(self.ch4mean, 4, 4)
        gbleft_grd.addWidget(QLabel("+/-"), 4, 5)
        gbleft_grd.addWidget(self.ch4std, 4, 6)
        gbleft_grd.addWidget(self.ch4cpmean, 4, 7)

        gbleft.setLayout(gbleft_grd)
        
        #sensor setup grid
        gbabovebottom_grd = QGridLayout()
        self.cbsensor = QComboBox()
        self.cbsensor.setToolTip("Sensor type used for temperature measurement (TC: K, R, J, etc.)")
        self.cbunits = QComboBox()
        self.cbunits.setToolTip("Units used in temperature measurement")
        self.makeSensorInterface()

        gbabovebottom_grd.addWidget(QLabel("Sensor type:"),0,0)
        gbabovebottom_grd.addWidget(self.cbsensor,0,1)
        gbabovebottom_grd.addWidget(QLabel("\tUnits:"),0,2)
        gbabovebottom_grd.addWidget(self.cbunits,0,3)
        gbabovebottom.setLayout(gbabovebottom_grd)
        gbabovebottom_grd.setColumnStretch(1,50)
        gbabovebottom_grd.setColumnStretch(3,50)

        #control grid grid
        gbbottom_grd = QHBoxLayout()

        #bottom grid - left side - control buttons
        wdtemp = QWidget()
        wdtemp_lay = QGridLayout()
        wdtemp.setLayout(wdtemp_lay)
        self.btnsetup = QPushButton("Check\nTango")
        self.btnsetup.setToolTip("Checks device state and connection")
        self.btnstart = QPushButton(BTNSTARTM1)
        self.btnstart.setToolTip("Starts/Stops continuous measurement loop")
        self.btnstartonce = QPushButton("One Meas.")
        self.btnstartonce.setToolTip("Makes one measurement")
        self.btnstartwrite = QPushButton(BTNSTARTW1)
        self.btnstartwrite.setToolTip("Starts/Stops data logging into a file")
        self.btnkicktango = QPushButton("Kick\nTango")
        self.btnkicktango.setToolTip("Brutally restarts adm Tango server responsible for Keithley3706 control and communication")

        self.setBtnMinDimensions((self.btnstart, self.btnsetup, self.btnstartwrite, self.btnstartonce, self.btnkicktango))
        wdtemp_lay.addWidget(self.btnsetup, 0, 0)
        wdtemp_lay.addWidget(self.btnkicktango, 0, 1)
        wdtemp_lay.addWidget(self.btnstartwrite, 1, 2)
        wdtemp_lay.addWidget(self.btnstartonce, 1, 0)
        wdtemp_lay.addWidget(self.btnstart, 1, 1)
        gbbottom_grd.addWidget(wdtemp)

        #gbottom - right side - file name part
        
        wdtemp = QWidget()
        wdtemp_lay = QVBoxLayout()
        wdtemp.setLayout(wdtemp_lay)

        wdtemp_temp = QWidget()
        wdtemp_temp_lay = QGridLayout()
        wdtemp_temp.setLayout(wdtemp_temp_lay)
        wdtemp_temp_lay.addWidget(QLabel("File path:"), 0, 0)
        wdtemp_temp_lay.addWidget(QLabel("File name:"), 1, 0)
        self.tlfilepath = QLineEdit()
        self.tlfilepath.setText(self.dir)
        self.tlfilepath.setToolTip("File path information")
        self.tlfilename = QLineEdit()
        self.tlfilepath.setDisabled(True)
        self.tlfilename.setText("experiment_")
        self.tlfilename.setToolTip("File name information")

        self.btnfindpath = QToolButton()
        self.btnfindpath.setToolTip("Select file path by browsing local directories")
        wdtemp_temp_lay.addWidget(self.tlfilepath, 0, 1)
        wdtemp_temp_lay.addWidget(self.btnfindpath, 0, 2)
        wdtemp_temp_lay.addWidget(self.tlfilename, 1, 1)

        # checkbox part - plot graph
        wdtemp_temp_lay.addWidget(QLabel(""), 2, 0)
        self.cbgraph = QCheckBox("Show Graph")
        self.cbgraph.setToolTip("Toggles graph window visibility")
        self.cbgraphclr = QCheckBox("Clear Graph")
        self.cbgraphclr.setToolTip("Clear data points from graph")
        wdtemp_temp_lay.addWidget(self.cbgraph, 3, 0)
        wdtemp_temp_lay.addWidget(self.cbgraphclr, 3, 1)
        wdtemp_lay.addWidget(wdtemp_temp)
        wdtemp_lay.addStretch()

        gbbottom_grd.addWidget(wdtemp)
        gbbottom_grd.addStretch()
        gbbottom.setLayout(gbbottom_grd)
        
        cntWidget.setLayout(grid)
        self.setCentralWidget(cntWidget)

        #
        #setup actions - clicks, etc.
        #

        # copy buttons - values, mean+std
        self.ch1cp_callback = lambda who="one": self.copyDataButton(who)
        self.connect(self.ch1cp, SIGNAL("clicked()"), self.ch1cp_callback)
        self.ch2cp_callback = lambda who="two": self.copyDataButton(who)
        self.connect(self.ch2cp, SIGNAL("clicked()"), self.ch2cp_callback)
        self.ch3cp_callback = lambda who="three": self.copyDataButton(who)
        self.connect(self.ch3cp, SIGNAL("clicked()"), self.ch3cp_callback)
        self.ch4cp_callback = lambda who="four": self.copyDataButton(who)
        self.connect(self.ch4cp, SIGNAL("clicked()"), self.ch4cp_callback)

        self.ch1cp_callback = lambda who="one mean+std": self.copyDataButton(who)
        self.connect(self.ch1cpmean, SIGNAL("clicked()"), self.ch1cp_callback)
        self.ch2cp_callback = lambda who="two mean+std": self.copyDataButton(who)
        self.connect(self.ch2cpmean, SIGNAL("clicked()"), self.ch2cp_callback)
        self.ch3cp_callback = lambda who="three mean+std": self.copyDataButton(who)
        self.connect(self.ch3cpmean, SIGNAL("clicked()"), self.ch3cp_callback)
        self.ch4cp_callback = lambda who="four mean+std": self.copyDataButton(who)
        self.connect(self.ch4cpmean, SIGNAL("clicked()"), self.ch4cp_callback)

        #copy.clear()
        #copy.setText("Hello World")

        # track check boxes - use click instead of .stateChanged(int) to make processing easier
        # passing reference to data, widget to check for state, labels with mean and std values for cleaning
        self.cbch1_callback = lambda who="ch1", widget=self.ch1track, lbmean=self.ch1mean, lbstd=self.ch1std: self.cbTrackChanged(who, widget, lbmean, lbstd)
        self.connect(self.ch1track, SIGNAL("clicked()"), self.cbch1_callback)

        self.cbch2_callback = lambda who="ch2", widget=self.ch2track, lbmean=self.ch2mean, lbstd=self.ch2std: self.cbTrackChanged(who, widget, lbmean, lbstd)
        self.connect(self.ch2track, SIGNAL("clicked()"), self.cbch2_callback)

        self.cbch3_callback = lambda who="ch3", widget=self.ch3track, lbmean=self.ch3mean, lbstd=self.ch3std: self.cbTrackChanged(who, widget, lbmean, lbstd)
        self.connect(self.ch3track, SIGNAL("clicked()"), self.cbch3_callback)

        self.cbch4_callback = lambda who="ch4", widget=self.ch4track, lbmean=self.ch4mean, lbstd=self.ch4std: self.cbTrackChanged(who, widget, lbmean, lbstd)
        self.connect(self.ch4track, SIGNAL("clicked()"), self.cbch4_callback)


        # setup-check button
        self.connect(self.btnsetup, SIGNAL("clicked()"), self.btnsetup_clicked)

        # forceful kick Tango button - restart tango server, reinitialize device
        self.connect(self.btnkicktango, SIGNAL("clicked()"), self.btnkicktango_clicked)

        # start-stop measurement button
        self.connect(self.btnstart, SIGNAL("clicked()"), self.btnstart_clicked)
        self.connect(self.btnstartonce, SIGNAL("clicked()"), self.btnstartonce_clicked)

        # start-stop writer button
        self.connect(self.btnstartwrite, SIGNAL("clicked()"), self.btnstartwrite_clicked)

        # find path button
        self.connect(self.btnfindpath, SIGNAL("clicked()"), self.openFileDialog)

        #checkbox controling graph visibility
        self.connect(self.cbgraph, SIGNAL("clicked()"), self.showGraph)
        self.connect(self.cbgraphclr, SIGNAL("clicked()"), self.clrGraph)

        #graphWindow
        self.connect(self, SIGNAL("plotGraph"), self.graph.showData)
        
        # icon 
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(255,255,0))
        self.setWindowIcon(QIcon(pixmap))
        
##
## Service functions
##
    def showGraph(self):
        if(self.graph.isHidden()):
            rect = self.frameGeometry() 
            self.graph.show()
            self.graph.move(QPoint(rect.x()+rect.width(), rect.y()))
        else:
            self.graph.hide()

    # setup comboboxes - units + thermocouples
    def makeSensorInterface(self):
        ks = sorted(TCSET.keys())
        # show thermocouple types
        for k in ks:
            strtc = QString("  %i - Thermocouple type - %s " %(k, TCSET[k]))
            self.cbsensor.addItem(strtc, QVariant(k))
        self.cbsensor.setCurrentIndex(1) # K -type by default

        # show measured scales
        ks = sorted(UNITSSET.keys())
        for k in ks:
            strunits = QString("  %i - %s" %(k, UNITSSET[k]))
            self.cbunits.addItem(strunits, QVariant(k))
        self.cbunits.setCurrentIndex(3) # Kelvin by default

    # get the latest point, leave it be, clean others
    def clrGraph(self):
        with(QMutexLocker(self.datagraphmutext)):
            self.datagraph = {}
        self.emit(SIGNAL("plotGraph"), self.datagraph)
        self.cbgraphclr.setCheckState(False)

    # movement of the main window + simultaneous movement of the child window
    def moveEvent(self, event):
        (pos, oldpos) = (event.pos(), event.oldPos())

        if(self.isActiveWindow()):
            rect = self.frameGeometry() 
            self.graph.move(QPoint(rect.x()+rect.width(), rect.y()))

    # initialization or reinitialization of movements
    def prepareSignals(self):
        #update interface with measured values
        self.connect(self.thMeas, SIGNAL("report"), self.reportMeasurements)
        #enable all main buttons when measurements are done
        self.connect(self.thMeas, SIGNAL("finished()"), self.cleanBtns)
        #get reports from Check and KickTango thread
        self.connect(self.thCheck, SIGNAL("report"), self.showLongMessage)
        self.connect(self.thKickTango, SIGNAL("report"), self.showLongMessage)

    #disable certain main buttons
    def setBtnDisabled(self, btndict):
        for key in btndict:
            if(key=="1"):                  # setup or check
                self.btnsetup.setDisabled(btndict[key])
            elif(key=="2"):                # start write
                self.btnstartwrite.setDisabled(btndict[key])
            elif(key=="3"):                # start one shot read
                self.btnstartonce.setDisabled(btndict[key])
            elif(key=="4"):                # start loop read
                self.btnstart.setDisabled(btndict[key])

    # enable all main buttons
    def cleanBtns(self):
        self.setWidgetEnabled(self.ch1track, self.ch2track, self.ch3track, self.ch4track, 
            self.btnstart, self.btnstartonce, self.btnsetup, self.btnstartwrite, self.btnkicktango, self.cbunits, self.cbsensor)

    # control visual - enabled disabled status for controls tied to data write routing
    def setWriteControlsDisabled(self):
        (bfdialog, bfilename) = (True, True)
        if(self.thWrite.isFinished()):
            (bfdialog, bfilename) = (False, False)

        self.btnfindpath.setDisabled(bfdialog)
        self.tlfilename.setDisabled(bfdialog)

    #disable list of controls
    def setWidgetDisabled(self, *tlist):
        temp = tlist
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            temp = tlist[0]
        for w in temp:
            w.setDisabled(True)

    #enable list of controls
    def setWidgetEnabled(self, *tlist):
        r = tlist
        if(type(tlist[0])==type([]) or type(tlist[0])==type(())):
            r = tlist[0]
        for w in r:
            w.setDisabled(False)

    # main function to update interface and report values
    # and keep track of the values per channel as well as their mean and std
    # get values as float, preformat them if needed
    def reportMeasurements(self, report):
        (bError, ch1, ch2, ch3, ch4) = report

        # return if error is set - prevent writing, anything else
        if(bError):
            self.showLongMessage("Error: device access error. (1) Stop measurements (2) Check device connectivity")
            return

        #track values, add to the list, compute mean, std
        self.trackNewValues(ch1, ch2, ch3, ch4)
        (ch1mean, ch1std, ch2mean, ch2std, ch3mean, ch3std, ch4mean, ch4std) = (self.dataset["ch1mean"], self.dataset["ch1std"], self.dataset["ch2mean"], self.dataset["ch2std"],
                                                                                self.dataset["ch3mean"], self.dataset["ch3std"], self.dataset["ch4mean"], self.dataset["ch4std"])

        # date and time functions - to generate timestamp
        datetime = QDateTimeM().currentDateTime()
        date = datetime.date()
        time = datetime.time()
        timestamp = datetime.toMSecsSinceEpoch()

        # data for graph - what we show - separate data stream +1 timestamp, +4 channels
        # add new values
        with(QMutexLocker(self.datagraphmutext)):
            self.datagraph[timestamp] = (ch1, ch2, ch3, ch4)
            # parse the data for the time limit
            # we need no data older than TIMELIMIT
	    self.datagraph = dict((k,v) for (k,v) in self.datagraph.iteritems() if k>timestamp-TIMELIMIT)
	

        # forward data to the graph window
        self.emit(SIGNAL("plotGraph"), self.datagraph)


        #prepare values for file and gui
        (sch1, sch2, sch3, sch4, sch1mean, sch2mean, sch3mean, sch4mean, sch1std, sch2std, sch3std, sch4std) = self.formatMeasurement(ch1, ch2, ch3, ch4,
                                        ch1mean, ch2mean, ch3mean, ch4mean,
                                        ch1std, ch2std, ch3std,ch4std)

        # provide data to writer to save in file
        if(self.thWrite.isRunning()):
            time = "%i\t%04i-%02i-%02i\t%02i:%02i:%02i:%03i"%(timestamp, date.year(), date.month(), date.day(),time.hour(), time.minute(), time.second(), time.msec())
            string = QString("%s\t%s\t%s\t%s\t%s\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\t%.2f\n"%(time, sch1, sch2, sch3, sch4, 
                                                                ch1mean, ch1std, ch2mean, ch2std, 
                                                                ch3mean, ch3std, ch4mean, ch4std))
            self.thWrite.addData(string)

        # show data in gui
        self.showShortMessage("Value received: (%s) (%s) (%s) (%s)" % (sch1, sch2, sch3, sch4))
        self.ch1.setText(sch1)
        self.ch2.setText(sch2)
        self.ch3.setText(sch3)
        self.ch4.setText(sch4)

        if(self.dataset["ch1track"]==Qt.Checked):
            self.ch1mean.setText(sch1mean)
            self.ch1std.setText(sch1std)

        if(self.dataset["ch2track"]==Qt.Checked):
            self.ch2mean.setText(sch2mean)
            self.ch2std.setText(sch2std)

        if(self.dataset["ch3track"]==Qt.Checked):
            self.ch3mean.setText(sch3mean)
            self.ch3std.setText(sch3std)

        if(self.dataset["ch4track"]==Qt.Checked):
            self.ch4mean.setText(sch4mean)
            self.ch4std.setText(sch4std)



    #track values, compute mean, std, lock values for writing
    def trackNewValues(self, *tlist):
        (ch1, ch2, ch3, ch4) = tlist
        with(QMutexLocker(self.datasetlock)):       #lock for writing 

            # check tracking checkboxes
            # check if values are None - Keithley overflow - channels disconnected
            if(self.dataset["ch1track"]==Qt.Checked and ch1 != None):      #ch1
                self.dataset["ch1"].append(ch1)
                self.dataset["ch1sum"] += ch1
                self.dataset["ch1mean"] = self.dataset["ch1sum"]/len(self.dataset["ch1"])
                self.dataset["ch1std"] = self.calculateStd(self.dataset["ch1"], self.dataset["ch1mean"])
            if(self.dataset["ch2track"]==Qt.Checked and ch2 != None):       #ch2
                self.dataset["ch2"].append(ch2)
                self.dataset["ch2sum"] += ch2
                self.dataset["ch2mean"] = self.dataset["ch2sum"]/len(self.dataset["ch2"])
                self.dataset["ch2std"] = self.calculateStd(self.dataset["ch2"], self.dataset["ch2mean"])
            if(self.dataset["ch3track"]==Qt.Checked and ch3 != None):       #ch3
                self.dataset["ch3"].append(ch3)
                self.dataset["ch3sum"] += ch3
                self.dataset["ch3mean"] = self.dataset["ch3sum"]/len(self.dataset["ch3"])
                self.dataset["ch3std"] = self.calculateStd(self.dataset["ch3"], self.dataset["ch3mean"])
            if(self.dataset["ch4track"]==Qt.Checked and ch4 != None):       #ch4
                self.dataset["ch4"].append(ch4)
                self.dataset["ch4sum"] += ch4
                self.dataset["ch4mean"] = self.dataset["ch4sum"]/len(self.dataset["ch4"])
                self.dataset["ch4std"] = self.calculateStd(self.dataset["ch4"], self.dataset["ch4mean"])
        return

    # track None values
    def trackNoneValues(self, *tlist):
        vals = []
        for i in tlist:
            if(i is None):
                vals.append("n.a.")
            else:
                vals.append("%.2f" % v)
        return vals



    #calculate std
    def calculateStd(self, tlist, mean):
        std = 0
        if(len(tlist)>1):
            for v in tlist:
                std = std + (v-mean)**2
            std = sqrt(std/(len(tlist)-1)) #math.sqrt - faster alternative to power
        return std


    # format values we show in the interface
    def formatMeasurement(self, *args):
        tlist = []
        if(len(args)):
            for arg in args:
                if(arg != None):
                    tlist.append("%.3f" % arg)
                else:
                    tlist.append("n.a.")
        return tlist

    #use file dialog to select filenames for saving data
    def openFileDialog(self):
        fdir = self.tlfilepath.text()
        fname = self.tlfilename.text()

        currdir = QDir(fdir)
        currpath = currdir.filePath(fname)

        fdialog = QFileDialog.getSaveFileName(self, "Select File Name", fdir, "Any files: (*.*);; Ascii files (*.txt *.dat *.xy)")

        while(not self.checkFile(fdialog) and not self.checkFile(currpath)):
            fdialog = QFileDialog.getSaveFileName(self, "Select File Name", fdir, "Any files: (*.*);; Ascii files (*.txt *.dat *.xy)")

        path = fdialog
        if(fdialog): #filename is correct from the dialog
            finfo = QFileInfo(fdialog)
            self.tlfilepath.setText(finfo.path())
            self.tlfilename.setText(finfo.fileName())
        else:        #cancel was pressed
            path = currpath
        
        self.status.showMessage("Using file: "+path, 5000)

	# set dimensions in a list
    def setLabMinWidth(self, lblist):
        for widget in lblist:
            widget.setMinimumWidth(70)

    #impose certain restrictions to btn sizes
    def setBtnMinDimensions(self,btnlist):
        for widget in btnlist:
            widget.setMinimumHeight(50)
            widget.setMaximumWidth(100)

    #function for copy data to the clipboard
    def copyDataButton(self, who):
        
        clipboard = self.app.clipboard()

        value = ""
        if(who=="one"):
            clipboard.setText(self.ch1.text())
        elif (who=="two"):
            clipboard.setText(self.ch2.text())
        elif (who=="three"):
            clipboard.setText(self.ch3.text())
        elif (who=="four"):
            clipboard.setText(self.ch4.text())
        elif (who=="one mean+std"):
            clipboard.setText(self.ch1mean.text()+" +/- "+self.ch1std.text())
        elif (who=="two mean+std"):
            clipboard.setText(self.ch2mean.text()+" +/- "+self.ch2std.text())
        elif (who=="three mean+std"):
            clipboard.setText(self.ch3mean.text()+" +/- "+self.ch3std.text())
        elif (who=="four mean+std"):
            clipboard.setText(self.ch4mean.text()+" +/- "+self.ch4std.text())

    #check validity of file choosed for experiment (not existing or existing, but not dir or link)
    def checkFile(self, fn):
        #normal check for correct file name
        bcorrect = False
        fi = QFileInfo(fn)
        if(not fi.exists() or fi.isFile()):
            bcorrect = True

        #additional test - read test
        try:
            fi = QFile(fn)
            if(not fi.open(QIODevice.Append)):
                raise IOError, unicode(fi.errorString())
        except IOError, error:
            self.showShortMessage("Error"+str(error))
            bcorrect = False

        return bcorrect

    def showShortMessage(self, msg):
        self.status.showMessage(msg, 3000)

    def showLongMessage(self, msg):
        self.status.showMessage(msg, 10000)

    #btns processing

    #start measurements button - switches start - stop
    def btnstart_clicked(self):
        if(self.thMeas.isRunning()):  #case the measurements are kind of running
            self.thMeas.stop()
            self.thMeas.wait()
            self.btnstart.setText(BTNSTARTM1)
            self.showShortMessage("Measurement thread has stopped..")
        else:

            # check settings for temperature readings
            self.checkSensorSettings()

            # setup and start measurement thread
            self.thMeas = ThreadMeasure(self.tango, self.thWrite)
            self.setWidgetDisabled(self.btnstartonce, self.btnsetup, self.btnkicktango,
                               self.ch1track, self.ch2track, self.ch3track, self.ch4track, self.cbunits, self.cbsensor)
            self.prepareSignals()
            self.btnstart.setText(BTNSTARTM2)
            self.showShortMessage("Measurement thread has started.. TC type (%s); Units (%s)" % (self.tango.thermocouple(), self.tango.units()))
            self.thMeas.start()
        return

    # measures tango object once
    def btnstartonce_clicked(self):
        if(self.thMeas.isRunning()):  #case the measurements are kind of running
            self.thMeas.stop()
            self.thMeas.wait()
            self.btnstart.setText(BTNSTARTM1)

        # check settings for temperature readings
        self.checkSensorSettings()

        # setup and start measurement thread
        self.thMeas = ThreadMeasure(self.tango, self.thWrite)
        self.thMeas.setOneShot()      #SET one shot thread
        self.prepareSignals()
        self.setWidgetDisabled(self.btnstart, self.btnsetup, self.btnstartwrite, self.btnkicktango, self.btnstartonce,
                               self.ch1track, self.ch2track, self.ch3track, self.ch4track, self.cbunits, self.cbsensor)
        self.showShortMessage("Measurement thread has started.. TC type (%s); Units (%s)" % (self.tango.thermocouple(), self.tango.units()))
        self.thMeas.start()
        return

    #starts - stops writing
    def btnstartwrite_clicked(self):
        if(self.thWrite.isRunning()):  #case the writing thread is kind of running - stop it
            self.thWrite.stop()
            self.btnstartwrite.setText(BTNSTARTW1)
            self.showShortMessage("Writing thread has stopped..")
            self.setWriteControlsDisabled()
        else:                           #case we start the writing thread
            # check if we can write to the file
            (di, fn) = (self.tlfilepath.text(), self.tlfilename.text())
            fn = QDir(di).filePath(fn)
            if(not self.checkFile(fn)):
                self.showLongMessage("Error: please check file name and file path fields")
                return

            #start thread responsible for writing
            self.thWrite.start(fn)
            self.btnstartwrite.setText(BTNSTARTW2)
            self.showShortMessage("Writing thread has started..")
            self.setWriteControlsDisabled()
        return

    #use as test - otherwise will fo to the setting up Keithley through a tango device, check operation
    def btnsetup_clicked(self):
        if(self.thCheck.isFinished()):
            self.thCheck = ThreadCheck(self.tango, (self.btnstartonce, self.btnstart, self.btnstartwrite, self.btnsetup, self.cbunits, self.cbsensor), self)
            self.prepareSignals()

        # check settings for temperature readings
        self.checkSensorSettings()
        self.thCheck.start()
        return

    #use to restart tango server
    def btnkicktango_clicked(self):
        if(self.thKickTango.isFinished()):
            self.thKickTango= ThreadKickTango(self.tango, (self.btnstartonce, self.btnstart, self.btnstartwrite, self.btnsetup, self.btnkicktango), self)
            self.prepareSignals()

        reply = QMessageBox.question(self, "Restart adm tango server?","This should be done if you see no response from the device - no temperature measurement or '0.000' as a response from a measurement from all channels  (thermocouples connected or disconnected).\n\nBefore you press 'YES'\nmake sure you have checked the following: \n (1) Keithley3706 is connected to the network \n (2) You have restarted Keithley3706\n (3) You have waited long enough for device Keithley3706 to start up ", QMessageBox.Yes|QMessageBox.Cancel)
        if(reply == QMessageBox.Yes):
            self.thKickTango.start()
        return

    # sets state of tracking - cleaning up database with values if needed
    def cbTrackChanged(self, *ref):
        (key, checkbox, wdmean, wdstd) = ref
        checkstate = checkbox.checkState()
        with(QMutexLocker(self.datasetlock)):
            self.dataset[key+"track"] = checkstate
            if(checkstate == Qt.Unchecked):
                self.dataset[key] = []
                self.dataset[key+"mean"] = 0
                self.dataset[key+"sum"] = 0
                self.dataset[key+"std"] = 0
                wdmean.setText("0.0")
                wdstd.setText("0.0")
        return

    # check current temperature set parameters
    def checkSensorSettings(self):
        # sensor type
        v = int(self.cbsensor.itemData(self.cbsensor.currentIndex()).toInt()[0])
        self.tango.thermocouple(v)

        # reading type
        v = int(self.cbunits.itemData(self.cbunits.currentIndex()).toInt()[0])
        self.tango.units(v)

#
# Destructor related functions - close main window ovveride
#
    def closeEvent(self, event):
        # cleaning up threads
        # measuring thread
        if(self.thMeas.isRunning()):
            self.thMeas.stop()
            self.thMeas.wait()

        # writing thread - wrapper take care for thread wait() call
        if(self.thWrite.isRunning()):
            self.thWrite.stop()

        # device adn adm server check thread
        if(self.thCheck.isRunning()):
            self.thCheck.stop()
            self.thCheck.wait()

        print("Bye Bye!")
        event.accept()

###-------------------
### End of Main Window object
###-------------------

    ###
    ###
### Tango Object - device communication through Tango server
    ###
    ###
class TangoObject(QObject):
    def __init__(self, devname, admname, parent=None):
        super(TangoObject, self).__init__(parent)
        self.initDeviceName(devname, admname)
        self.parent = parent

        # flag to insure that we initialized device units correctly
        self.bunitsInitialized = False
    
    # save device names
    def initDeviceName(self, devname, admname):
        (self.ch1, self.ch2, self.ch3, self.ch4) = (0,0,0,0)
        #setup device and its admin object name
        self.devname = devname
        self.admname = admname

        self.unitset = None
        self.tcset = None
        
        # device Proxy - one for thread
        self.dev = None

    # get set units
    def units(self, unit=None):
        if(unit != None):
            self.unitset = unit
            self.bunitsInitialized = False
        return self.unitset

    # get set thermocouples
    def thermocouple(self, tc=None):
        if(tc != None):
            self.tcset = tc
            self.bunitsInitialized = False
        return self.tcset
    
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
            QMessageBox().about("A problem was encountered. In order to solve it: \n (1) Please make a manual restart of Keithley 3706.\n (2) Wait until it powers up. \n (3) Press Ok button below.")
            self.parent.showLongMessage("Working - please wait..")
            (admstate, devstate) = self.restartDevice(self.admname, self.devname) # should come to life
            self.parent.showShortMessage("Finished")

        return (admstate, devstate)
    
    # one device proxy per thread
    def initOneDevice(self):
        if(self.dev==None):
            self.dev = DeviceProxy(self.devname)
        
        return self.dev
    
    # close previous connection
    def flushOneDevice(self):
        self.dev = None
        # just in case - reinitialize device every time
        self.bunitsInitialized = False

    # Dummy function for testing
    def initDummy(self):
        return 0
    
    # Dummy function for testing
    def measDummy(self):
        return gauss(20, 0.1)
    
    # Measuring function
    def measDevice(self):
        return  self.measureKeithley3706()
        
    # Main Initializing function
    def initMeasurement(self):
        return self.initDevice()
    
    # Main Measuring function
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
        (oldunits, oldtc) = (dev.read_attribute("Units").value, dev.read_attribute("Thermocouple").value)
        
        (settc, setunits) = (self.tcset, self.unitset)
        
        # final setup 
        dev.write_attribute("Thermocouple", settc)
        while(dev.state()==DevState.MOVING):
            continue
        
        dev.command_inout("SetMeasurement")
        while(dev.state()==DevState.MOVING):
            continue
        
        dev.write_attribute("Units", setunits)
        while(dev.state()==DevState.MOVING):
            continue
        
        dev.command_inout("SetMeasurement")
        while(dev.state()==DevState.MOVING):
            continue
            
        (newunits, tc) = (dev.read_attribute("Units").value, dev.read_attribute("Thermocouple").value)
        
        # check settings - if different from settc and setunits - probably we need to restart the device
        # device behaves stupid, unless I do good trouble shooting - suggest that we have the proper connection to the device
        state = True
        self.bunitsInitialized = True
        return state

    # measuring is less protected than check procedure
    # check device state - simple check, function returns flag to discriminate error state
    # o give a hint to the user
    def measureKeithley3706(self):
        # try to make sure - which units we measure
        # one shot only
        if(not self.bunitsInitialized):
            self.setupKeithley3706()
        

        #check device state
        state = self.getTangoState(self.devname)
        if(not state):
            return (True, 0, 0, 0, 0)
        
        dev = self.initOneDevice()
        dev.command_inout("StartMeasurement")
        
        #simple loop, can make a timeout loop
        while(dev.state()== DevState.MOVING):
            continue
        
        ch1 = dev.read_attribute("ValueCh1").value
        ch2 = dev.read_attribute("ValueCh2").value
        ch3 = dev.read_attribute("ValueCh3").value
        ch4 = dev.read_attribute("ValueCh4").value
        
        result = (False, ch1, ch2, ch3, ch4)
        dev = None
        return result

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
                dev = DeviceProxy(self.devname)
                devstate = dev.state()    #throws exceptions unless the device is alive
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

    # brute force restart known adm server
    def restartAdmDevice(self):
        state = self.restartDevice(self.admname, self.devname)
        self.setupKeithley3706() 
        return state

###-------------------
### End of TangoObject
###-------------------

    ###
    ###
### ThreadMeasure Object - measure data from Keithley, pass to ThreadWriter
    ###
    ###
class ThreadMeasure(QThread):
    def __init__(self, tango, thwriter, parent=None): #pass tango object to use for measuring and writer thread object used for writing
        super(ThreadMeasure, self).__init__(parent)
        #controls thread run
        self.stopped = False
        self.stopmutex = QMutex()

        #tango object used in measurements
        self.tango = tango

        #writer thread to pass data to
        self.writer = thwriter

        #parameter for one shot - one measurement
        self.oneshot = False

    # stop function to simplify operation
    def stop(self):
        if(not self.stopped):
            with(QMutexLocker(self.stopmutex)):
                self.stopped = True

    # main thread procedure
    def run(self):
        # close previous connection with Tango for device
        self.tango.flushOneDevice()
        while(not self.stopped):
            # first value is the error flag if something bad happens during the measurements
            # measure values using one device proxy instance for convenience
            # but chech device state every time
            (bError, ch1, ch2, ch3, ch4) = self.measure()
            (ch1, ch2, ch3, ch4) = self.checkMeasOverflow((ch1, ch2, ch3, ch4))

            # report measured values to main program thread
            self.emit(SIGNAL("report"), (bError, ch1, ch2, ch3, ch4))

            #one shot measurement
            if(self.oneshot):
                break

            # for debugging
            # self.msleep(500)
            continue
        self.stop()

    # measurement
    def measure(self):
        return self.tango.makeMeasurement()

    # control thread - set it to one shot measurement
    def setOneShot(self):
        self.oneshot = True

    # check channel measured values - if too large - set to -1
    # by default Keithley reports 9E37 for disconnected channel
    def checkMeasOverflow(self, values):
        tlist = []
        for v in values:
            if(v>3000.0 or v<-300.0):   # educated guess - we should not go beyond 3000 Kelvin and -300 Celsius
                v = None
            else:
                v = float(v)
            tlist.append(v)
        return tlist

###-------------------
### End of ThreadMeasure Object
###-------------------

    ###
    ###
### Thread Writer Object - write data to a file
    ###
    ###
class ThreadWriter(QThread):
    def __init__(self, parent=None):
        super(ThreadWriter, self).__init__(parent)
        #controls thread run
        self.stopped = False
        self.stopmutex = QMutex()

        #file params - QFile + QTextStream
        self.file = None
        self.filestream = None

        # data which should be used for writing - multiple thread access
        self.data = QString("")
        self.datalock = QMutex()


    # stop thread - make stop flag - close the file, simplify procedure
    def stop(self):
        if(not self.stopped):
            with(QMutexLocker(self.stopmutex)):
                self.stopped = True

    # main thread for data saving
    def run(self):
        while(not self.stopped):
            if(self.data.length()>0):
                self.writeFile()
            continue

        # finish file operations
        if(self.file and self.file.isOpen()):
            # finish writing data
            if(len(self.data)):
                self.writeFile()
            self.file.close()
        self.stop()

    # sets filename
    # does not need mutex - because file is set before the thread is run
    def setFileName(self, fn):
        self.file = QFile(fn);
        try:
            if not self.file.open(QIODevice.Append|QIODevice.Text):
                raise IOError, unicode(self.file.errorString())
        except IOError, error:
            print(error)
        self.filestream = QTextStream(self.file)

    # adds prepared data for saving queue
    def addData(self, data):
        with(QMutexLocker(self.datalock)):
            self.data = self.data + data

    # saving data to the file
    # make sure data is saved carefully - with data lock and interprocess operations - all text symbols like \n must be included
    def writeFile(self):
        data = QString("")
        with(QMutexLocker(self.datalock)): #just memory copy to a new QString Object
            data = data+self.data
            self.data = QString("")

        self.filestream<<data
        self.filestream.flush()         # necessary, otherwise no immeadiate save

###-------------------
### End of ThreadWriter Object
###-------------------

    ###
    ###
### Thread Writer Wrapper Object - write data to a file
### for ease of renewing thread references and objects
    ###
    ###
class ThreadWriteWrapper(QObject):
    def __init__(self, parent=None):
        super(ThreadWriteWrapper, self).__init__(parent)
        #controls thread modification
        self.threadmutex = QMutex()
        self._thread = None
        self._counter = 0

        self.initialize()


    # initialize thread, could make to pass arguments
    def initialize(self):
        #use mutex to change it's value
        with(QMutexLocker(self.threadmutex)):
            self._thread = ThreadWriter()

    def getThread(self):
        #use mutex to forbid reading of the thread instance while it is been changed
        with(QMutexLocker(self.threadmutex)):
            self._thread 

    # start or restart a thread wrapper - make use of the mutex
    def start(self, filename):
        #do nothing unless the the wrapped thread has been initialized
        if(self._thread == None):
            return
        #clean up if it is running
        if(self.isRunning()):
            self.stop()
        
        if(self.isFinished()):
            self.initialize()

        #date header - put it into the file on start
        self.timeHeader("Start")
        self.dataHeader()

        #final preparation - pass filename to thread
        self.setFileName(filename)
        self._thread.start()

    #check finished state
    def isFinished(self):
        if(self._thread == None):
            return True
        return self._thread.isFinished()

    #check running state
    def isRunning(self):
        if(self._thread == None):
            return False
        return self._thread.isRunning()

    # make thread stop
    def stop(self):
        if(self._thread == None):
            return

        if(self.isRunning()):
            self.timeHeader("Stop")
            self._thread.stop()
            self._thread.wait()

    #thread wrapping - add data
    def addData(self, data):
        self._thread.addData(data)

    #thread wrapping - add 
    def setFileName(self, fn):
        self._thread.setFileName(fn)

    #dummy to avoid confusion during development
    def wait(self):
        return

    #time message - header - footer - before and after the writing
    def timeHeader(self, msg):
        datetime = QDateTimeM().currentDateTime()
        date = datetime.date()
        time = datetime.time()
        string = QString("### %s\tat\t%04i-%02i-%02i\t%02i:%02i:%02i\n"%(msg, date.year(), date.month(), date.day(),time.hour(), time.minute(), time.second()))
        self.addData(string)

    #header data
    def dataHeader(self):
        string = QString("#Timestamp\tDate\tTime\tCh1\tCh2\tCh3\tCh4\tCh1_mean\tCh1_std\tCh2_mean\tCh2_std\tCh3_mean\tCh3_std\tCh4_mean\tCh4_std\n")
        self.addData(string)

###-------------------
### End of ThreadWriteWrapper Object
###-------------------

    ###
    ###
### QDateTimeM object 
### to bring new PyQt functionality absent in the current control machine version
### made a wrapper for immediate currentDateTime access
    ###
    ###
class QDateTimeM(QDateTime):
    def __init__(self, parent=None):
        super(QDateTimeM, self).__init__(QDateTime().currentDateTime())

    # PyQT function ebsent in the current library version
    def toMSecsSinceEpoch(self):
            time = self.time()
            return int((float(self.toTime_t())+float(time.msec())/1000)*1000)
    
    def currentDateTime(self):
	    return self

###-------------------
### End of QDateTimeM Object
###-------------------

    ###
    ###
### TCGraph object - graph window
    ###
    ###
class TCGraph(QMainWindow):
    
    def __init__(self, title, parent=None):
        super(TCGraph, self).__init__(parent)    
        
        self.title = title

        # set point
        self.setpoint = 292.0

        # init user interface
        self.p = None
        self.initUI()

        # counter for unaware user
        self.closecounter = 0
        
    def initUI(self):
        self.resize(600,400)
        #background - color
        pal = QPalette()
        self.setAutoFillBackground(True)
        pal.setColor(QPalette.Window, QColor('orange').light())
        self.setPalette(pal)
        
           
        #prepare channel curves : getCurve(self, label, symb, penc, pens, brushc):
        c1 = self.getCurve('TC ch1', Circle, Black, 2, Black)
        c2 = self.getCurve('TC ch2', Circle, Green, 2, Green)
        c3 = self.getCurve('TC ch3', Circle, Red, 2, Red)
        c4 = self.getCurve('TC ch4', Circle, Blue, 2, Blue)

        #create a plot widget
        self.p = MPlot(
            c1, c2, c3, c4,
            '', self)

        # set autoplot
        self.p.autoplot = True

        self.p.setMinimumHeight(380)

        self.qmark = QwtPlotMarker()
        self.qmark.setLineStyle(1)
        self.qmark.setYValue(11)
        pen = QPen(Qt.DashLine)
        pen.setColor(QColor(100, 100, 100, 150))
        pen.setWidth(3)
        pen.setDashOffset(self.setpoint)
        self.qmark.setLinePen(pen)
        self.qmark.attach(self.p)

        #tweak initial properties of the plot
        self.p.setAxisScaleDraw(QwtPlot.xBottom, TimeScaleDraw())
        self.p.setAxisLabelRotation(QwtPlot.xBottom, 0)
        self.p.legend().setFont(QFont("Arial", 12))

        #tweak output of information at the cursor
        self.p.zoomers[0].setTrackerMode(QwtPicker.AlwaysOn)
        self.p.zoomers[0].trackerText = self.modYScaleText
       
        # finalize layout
        
        # main widget
        temp = QWidget()
        templay = QGridLayout(temp)
        
        
        wdgt = QGroupBox("Graph Parameters")
        wdgt.setFlat(True)
        wdgtlay = QGridLayout(wdgt)
        self.lesetpoint = QLineEdit(str(self.setpoint))
        #self.lesetpoint.setMinimumHeight(22)
        #self.lesetpoint.setMaximumWidth(150)
        self.lesetpoint.setToolTip("Controls the position for the horizontal eye guide")
        templabel = QLabel("Horizontal eye guide:")
        wdgtlay.addWidget(templabel, 0, 0)
        wdgtlay.addWidget(self.lesetpoint, 0, 1)
        
        # add widgets for vertical axis scaling yi (y min) ya (y max)
        self.leya = QLineEdit("%.2f"%PLOTYMAX)
        self.leyi = QLineEdit("%.2f"%PLOTYMIN)
        self.cbyautoscale = QCheckBox("set Autoscale for y axis")
        
        self.cbyautoscale.setCheckState(Qt.Checked)
        
        self.leya.setValidator(QDoubleValidator(self.leya))
        self.leyi.setValidator(QDoubleValidator(self.leyi))
        
        wdgtlay.addWidget(self.cbyautoscale, 2, 4)
        wdgtlay.addWidget(QLabel("max y:"), 0, 3)
        wdgtlay.addWidget(QLabel("min y:"), 1, 3)
        wdgtlay.addWidget(self.leya, 0, 4)
        wdgtlay.addWidget(self.leyi, 1, 4)
        wdgtlay.setColumnStretch(5, 50)
        
        self.processRescale(self.cbyautoscale.checkState())
        
        templay.addWidget(wdgt, 0, 0)
        templay.addWidget(self.p, 1, 0)
        templay.setRowStretch(1, 50)
        templay.setColumnStretch(0, 50)

        self.setCentralWidget(temp)
        self.setWindowTitle(self.title)

        #line edit - set point
        self.connect(self.lesetpoint, SIGNAL("editingFinished()"), self.newSetPoint)
        
        # sets resets autoscale:
        self.connect(self.cbyautoscale, SIGNAL("stateChanged(int)"), self.processRescale)
        
        self.connect(self.leya, SIGNAL("editingFinished()"), self.processRescale)
        self.connect(self.leya, SIGNAL("returnPressed()"), self.processRescale)
        self.connect(self.leyi, SIGNAL("editingFinished()"), self.processRescale)
        self.connect(self.leyi, SIGNAL("returnPressed()"), self.processRescale)
    
    #exit from window - not main window
    def closeEvent(self, event):
        self.closecounter += 1
        if(self.closecounter<10):
            QMessageBox.about(self, QString("Graph window"), QString("You can close this window through the main application window.\nPlease use the corresponding checkbox"))
        event.ignore()
        
    #visual update - reset zoom
    def updateUi(self):
        #checks zoom event - to prevent certain bugs
        if(self.p.zoomers[0].zoomRectIndex()==1):
            self.p.replot()
        else:
           self.p.clearZoomStack()
        return
       
    #utility functions:
    #prepare curves
    def getCurve(self, label, symb, penc, pens, brushc):
        s = Symbol(symb, brushc)
        s.setSize(10)
        s.setPen(Pen(penc, 2))
        return Curve([], [], Pen(penc,3), s, label)

    #modify text at cursor position - show only vertical coordinate
    def modYScaleText(self, qs):
        qsm = self.p.canvasMap(QwtPlot.yLeft) #QwtScaleMap to convert values between canvas and real coordinates
        text = QwtText("y: %0.02f"%(qsm.invTransform(qs.y())))
        text.setFont(QFont("Arial", 12, QFont.DemiBold))
        text.setBackgroundBrush(Qt.white)
        return text

    #prepare data which will be shown in the Graph
    def showData(self, tdict):
        #split dictionary with data into lists
        x = sorted(tdict.keys())
        xch1 = [k for k in x if tdict[k][0]!=None]
        ch1 = [tdict[k][0] for k in xch1]

        xch2 = [k for k in x if tdict[k][1]!=None]
        ch2 = [tdict[k][1] for k in xch2]

        xch3 = [k for k in x if tdict[k][2]!=None]
        ch3 = [tdict[k][2] for k in xch3]

        xch4 = [k for k in x if tdict[k][3]!=None]
        ch4 = [tdict[k][3] for k in xch4]

        visobj = self.p.itemList()   #curves, grid + marker

        #setting values for the curves
        visobj[1].setData(xch1, ch1)
        visobj[2].setData(xch2, ch2)
        visobj[3].setData(xch3, ch3)
        visobj[4].setData(xch4, ch4)

        #update graph
        self.updateUi()

    # make sure we have simultaneous movements
    def moveEvent(self, event):
        parent = self.parentWidget()
        (pos, oldpos) = (event.pos(), event.oldPos())

        if(self.isActiveWindow()):
            rect = self.frameGeometry() 
            prect = parent.frameGeometry()
            parent.move(QPoint(rect.x()-prect.width(), rect.y()))

    # line edit finished
    def newSetPoint(self):
        v = float(self.lesetpoint.text())
        self.qmark.setYValue(v)
        self.updateUi()
    
    # process rescaling of the graph - autoscale or manual scale for y axis
    def processRescale(self, value=None):
        (ya, yi) = (self.leya.text(), self.leyi.text())
        
        try:
            ya = float(ya)
            yi = float(yi)
        except ValueError:
            return
       
        (ya, yi) = (max(ya, yi), min(ya, yi))
        
        
        value = self.cbyautoscale.checkState()
        # change autoscaling to the user preferences if needed
        if(value==Qt.Checked):
            self.setWidgetDisabled(True, self.leya, self.leyi)
            self.p.autoplot = True              # change of the autoplot has immediate effect on the autoscaling
            self.p.replot()
        elif(value==Qt.Unchecked):
            self.setWidgetDisabled(False, self.leya, self.leyi)
            self.p.autoplot = False             # change of the autoplot should have immediate effect on the autoscaling
            self.p.setAxisScale(QwtPlot.yLeft, yi, ya)
            self.p.replot()
        return

    #disable list of controls
    def setWidgetDisabled(self, value, *tlist):
        temp = tlist
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            temp = tlist[0]
        for w in temp:
            w.setDisabled(value)
        

###-------------------
### End of TCGraph Object
###-------------------

    ###
    ###
### TimeScaleDraw object - for custom labels in the graph window
    ###
    ###
class TimeScaleDraw(QwtScaleDraw):
    def __init__(self):
        super(TimeScaleDraw, self).__init__()
        self.font = QFont("Arial", 9, QFont.DemiBold)

    def label(self, v):
        msecs = int(v/1000)
        dt = QDateTime().fromTime_t(msecs);
        time = dt.time()

        #res = QwtText("%02i:%02i:%02i"%(time.hour(), time.minute(), time.second()))
        res = QwtText("%02i:%02i"%(time.minute(), time.second()))
        res.setFont(self.font)

        return res

###-------------------
### End of TimeScaleDraw Object
###-------------------

    ###
    ###
### ThreadCheck object - for fast inobstrusive check of the device and adm server state
    ###
    ###
class ThreadCheck(QThread):
    def __init__(self, tango, controls, parent=None): #pass tango object to use for measuring and writer thread object used for writing
        super(ThreadCheck, self).__init__(parent)
        self.tango = tango
        self.controls = controls
        self.parent = parent

        # stop function
        self.stopped = False
        self.stopmutex = QMutex()

    def run(self):
        self.parent.setWidgetDisabled(self.controls)
        self.emit(SIGNAL("report"), "Testing..")

        res = self.tango.initMeasurement()

        string = "Server is operating normal: (%s); Device is operating normal: (%s);" % res
        self.emit(SIGNAL("report"), string)

        self.parent.setWidgetEnabled(self.controls)
        self.stop()

    # stop function to simplify operation
    def stop(self):
        if(not self.stopped):
            with(QMutexLocker(self.stopmutex)):
                self.stopped = True

###-------------------
### End of ThreadCheck Object
###-------------------

    ###
    ###
### ThreadKickTango object - brute force approach to reboot device adm tango server
    ###
    ###
class ThreadKickTango(QThread):
    def __init__(self, tango, controls, parent=None): #pass tango object to use for measuring and writer thread object used for writing
        super(ThreadKickTango, self).__init__(parent)
        self.tango = tango
        self.controls = controls
        self.parent = parent

        # stop function
        self.stopped = False
        self.stopmutex = QMutex()

    def run(self):
        self.parent.setWidgetDisabled(self.controls)
        self.emit(SIGNAL("report"), "Rebooting device control Tango server. Please wait..")

        res = self.tango.restartAdmDevice()

        string = "Tango server has been successfuly rebooted. Server - %s; Device - %s;" % res
        self.emit(SIGNAL("report"), string)

        self.parent.setWidgetEnabled(self.controls)
        self.stop()

    # stop function to simplify thread operation
    def stop(self):
        if(not self.stopped):
            with(QMutexLocker(self.stopmutex)):
                self.stopped = True

###-------------------
### End of ThreadKickTango Object
###-------------------


    ###
    ###
### MPlot object - override typical qplt.Plot autoplot behavior
    ###
    ###

class MPlot(Plot):
    def __init__(self, *tlist):
        self._bautoplot = True
        super(MPlot, self).__init__(*tlist)


    # autoplot setter/getter
    @property
    def autoplot(self):
        return self._bautoplot

    @autoplot.setter
    def autoplot(self, value):
        self._bautoplot = value
        self.replot()
        return self._bautoplot

    # override clear zoom stack of qplt.plot
    def clearZoomStack(self):
        if(self.autoplot):
            self.setAxisAutoScale(Y1)
            self.setAxisAutoScale(Y2)

        self.setAxisAutoScale(X1)
        self.setAxisAutoScale(X2)
        self.replot()
        for zoomer in self.zoomers:
            zoomer.setZoomBase()

###-------------------
### End of MPlot object
###-------------------

#
# Application startup
#
if __name__ == '__main__':
    print(DISCLAMER)
    app = QApplication(sys.argv)
    form = Form(None, app)
    form.show()
    app.exec_()

