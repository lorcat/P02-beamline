#!/usr/local/Python26/bin/python

##############
###
### Qt is licensed under a commercial and open source license (GNU Lesser General Public License version 2.1)
### This programs is licensed under a commercial and open source license (GNU Lesser General Public License version 2.1)
###
###
### latest coding - Konstantin Glazyrin for the needs of P02.2 beamline PETRAIII - DESY (coded under Python 2.7, PyQt version 4.10, Qt version 4.8.4)

# check http://stackoverflow.com/questions/7140596/qt-how-to-set-the-background-color-of-qpushbutton-to-system-color

from PyQt4.QtCore import *
from PyQt4.QtGui import *
import os
import sys
import time

from PyTango import *

#qwt import
from PyQt4.Qwt5.qplt import *

DISCLAMER = """-- gui for measurements - specific for Mercury iTC --
-- LGPL licence applies - as we use QT library for free --

version 0.3
0.3 improvement - on device reset Temperature SetPoint is not affected
0.2 improvement - real life test, conclusions, QTimer updated to QThread, enhanced gui performance.
                  explicit test for values read from Tango - in a separate tab (Program Reports)
0.1 improvement - basic gui
coding by Konstantin Glazyrin
contact lorcat@gmail.com for questions, comments and suggestions 
"""

# Tango device specifice addresses
    # administrative device to restart
TANGOSTARTER = "tango://haspp02oh1.desy.de:10000/tango/admin/haspp02eh2b"
    # Mercury Tango server inner reference
TANGOMERCPROC = "MercuryiTCTempCtrl/EH2B"
    # main device - accepts WriteReadRaw commands
TANGODEVICE = {"nick": "Mercury iTC controller", "link":"tango://haspp02oh1:10000/p02/mercuryitctempctrl/eh2b.01"}
    # sensor 1 MB0/MB1 binding - "sample" - DIODE
TANGOSENSE1 = {"nick": "DIODE (sample)", "link": "tango://haspp02oh1:10000/p02/mercuryitctempsensor/eh2b.01"}
    # sensor 2 DB1/DB6 binding - "cold finger" - DB6.T1 PTC sensor
TANGOSENSE2 = {"nick": "DB6.T1 (cold finger)", "link": "tango://haspp02oh1:10000/p02/mercuryitctempsensor/eh2b.02"}

# main control buttons captions
(BTNSTART, BTNSTOP) = ("Start Meas.", "Stop Meas.")
(BTNSTARTWRITE, BTNSTOPWRITE) = ("Start Save", "Stop Save")
BTNINSERTLABEL = "Insert Label"

BTNINIT = "Device Reset"
BTNKICKTANGO = "Kick\nTango"

# Inter object communication signals
(SIGNALREPORT, SIGNALFAILED, SIGNALSUCCESS, SIGNALCOMMAND, SIGNALDEBUGMEASUREMENT, SIGNALHOLDMAINTHREAD, SIGNALTANGOREBOOT) = ("reportChange", "reportFailed", "successDeviceOnline", "commandReadWrite", "reportProgramDebug", "holdMainThread", "rebootTangoServer")

# SCPI test commands
SCPITEST = "*IDN?"
SCPITESTRESPONSE = "MERCURY"

# raw commands
CMDWRRAW = "WriteReadOnlyOnce"
CMDREAD = "ReadAllAttributes"

# error messages for Tango object
ERRTANGOOFF = "Tango server is off, please check it"


# settings for switches - ON/OFF
(SETTINGON, SETTINGOFF) = (0., 1.)
(OFF, ON) = ("OFF", "ON")

# default heater settings PID off, Auto mode is off, temperature setpoint 300K, heater power 0%
(DEFAULTHEATPID, DEFAULTHEATAUTO, DEFAULTHEATSETTEMP, DEFAULTHEATSETPOWER) = (SETTINGON, SETTINGON, 305., 0)

# main timer for update in ms 
MAINTIMERINTERVAL = 500
DEBUGTIMERINTERVAL = 1500
PREVENTUSEROFTENRESETINTERVAL = 2000    # prevents user from pushing resetDevice button too often

# TANGO attributes names
    # for read/write operation
(ATTRSETHEADPID, ATTRSETHEATAUTO, ATTRSETHEATPOWER, ATTRSETTEMPPOINT) = ("SetHeatPID", "SetHeatAuto", "SetHeatPower", "SetTempPoint")
    # for read operation
(ATTRGETTEMP, ATTRGETHEATCURRENT, ATTRGETHEATPOWER, ATTRGETHEATPOWERPERC) = ("Temperature", "HeatCurrent", "HeatPower", "HeatPowerPerc")


# Tango dict for sensor values initialization
TANGOREADTEMPLATE = {ATTRGETTEMP:0., ATTRGETHEATCURRENT:0., ATTRGETHEATPOWER:0., ATTRGETHEATPOWERPERC:0., ATTRSETHEATAUTO:0., ATTRSETHEADPID:0., ATTRSETHEATPOWER:0., ATTRSETTEMPPOINT:0.}

# Tango sensor descriminator
(SENSE1, SENSE2) = ("sensor1", "sensor2")

# PARAMETER LIMITS 
MAXTEMP = 400   # temperature to 400 K
MINTEMP = 0     # minimal temperature to 0K
TEMPSTEP = 1  # temperature set point increase step

MAXPOW = 100    # same for the power
MINPOW = 0
POWSTEP = 0.1 

# Writing thread constants
(WRITESTART, WRITESTOP) = ("Start", "Stop")
WRITEDATAHEADER = "#_Timestamp\tDate\tTime\tTempSense1\tPowerHeat1\tTempSense2\tPowerHeat2\n"
DEFAULTFILENAME = "experiment.dat"

# graph 
    # default values for graph y axis scalng
(PLOTYMIN, PLOTYMAX) = (250., 400.)


# QMessageBox captions and messages
MSGBOXMAINTHREADTITLE = "Attention!"
MSGBOXMAINTHREADCAPTION = "Main thread is running. It is unwise to reboot Tango server while being communicating with.\nPlease stop it (%s - button) and try again." % BTNSTOP

###
##  CryoControl - main window
###
class CryoControl(QMainWindow):
    def __init__(self, app, parent=None):
        super(CryoControl, self).__init__(parent)

        # init variables
        self.initVars(app)

        # init interface
        self.initSelf()

        # init signals and slots
        self.initEvents()

    # initialize variables
    def initVars(self, app):
        # application
        self._app = app

        # status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

            # adjust style
        self._status.setAutoFillBackground(True)
        self._status.setPalette(QPalette(QColor(200, 200, 255)))

        self._status.setStyleSheet("QStatusBar::item { border: 0px;} QStatusBar {border-top: 2px solid rgb(50, 50, 170); background-color: rgb(200, 200, 250);}")

        # tango device
        self.tango = TangoObject(self)
        
        # worker thread - for simple one time jobs
        self._worker = None

        # go from timer update to a thread update
        self._mainThread = None

        # thread to write data
        self.thWrite = ThreadWriteWrapper()

        # graph window
        self.graph = TCGraph("Track cryostat temperatures", self)
            # set of data for visualizing in the graph - just visualizing 
            # data format timestamps: (sense1, sense2)
        self.datagraph = {}
        self.datagraphmutext = QMutex()


    # initialize interface
    def initSelf(self):
            #background - color
        pal = QPalette()
        self.setAutoFillBackground(True)
        color = QColor('blue').light()
        pal.setColor(QPalette.Window, color)

        self.setPalette(pal)

            # window size
        self.resize(300,300)

        # central widget
        wdgt = self.createCentralWidget()

        # create widget to track tango reboot process
        self.wtangoreboot = self.createTangoRebootWidget()

        # initialize disabled controls
        self.setWidgetsDisable(True, self.btnInit, self.btnStartStop, self.tab)

        self.setCentralWidget(wdgt)

        # icon
        self.setCryoIcon(color)

        # visualize
        self.show()
        return

    # initialise signals
    def initEvents(self):
        # report short messages - errors and not
            # simple report
        self.connect(self.tango, SIGNAL(SIGNALREPORT), self.showLongMsg)
            # fail error
        self.connect(self.tango, SIGNAL(SIGNALFAILED), self.showLongMsg)

        # signle device command read write
        self.connect(self.tango, SIGNAL(SIGNALCOMMAND), self.processDeviceCommandResponse)

        # act on failure
        self.connect(self.tango, SIGNAL(SIGNALFAILED), self.actOnFail)

        # act to hold main thread if running 
        self.connect(self.tango, SIGNAL(SIGNALHOLDMAINTHREAD), self.processHoldMainThread)

        # select device, probe it
        self.connect(self.cmbdevice, SIGNAL("currentIndexChanged(int)"), self.checkDeviceOnlineStatus)

        # restart responsible TangoServer to reestablish connection to the device
        self.connect(self.btnKickTango, SIGNAL("clicked()"), self.processKickTango)

        # initialize device - stop heating, set point to 0
        self.connect(self.btnInit, SIGNAL("clicked()"), self.processInitCryoDevice)

        # start stop _mainThread - timer alternative sucks as it jams gui performance sometimes
        self.connect(self.btnStartStop, SIGNAL("clicked()"), self.processStartStopMeasurement)

        # events from gui elements - update device parameters using tango, value is passed as a first parameter
            # sensor 1
        func_callback = lambda v="", sense=SENSE1, attr=ATTRSETTEMPPOINT: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.sbsett1, SIGNAL("returnPressed(double)"), func_callback)

        func_callback = lambda v="", sense=SENSE1, attr=ATTRSETHEATPOWER: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.sbsetp1, SIGNAL("returnPressed(double)"), func_callback)

        func_callback = lambda v="", sense=SENSE1, attr=ATTRSETHEADPID: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.cbpidh1, SIGNAL("stateChanged(int)"), func_callback)

        func_callback = lambda v="", sense=SENSE1, attr=ATTRSETHEATAUTO: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.cbautoh1, SIGNAL("stateChanged(int)"), func_callback)

            # sensor 2
        func_callback = lambda v="", sense=SENSE2, attr=ATTRSETTEMPPOINT: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.sbsett2, SIGNAL("returnPressed(double)"), func_callback)

        func_callback = lambda v="", sense=SENSE2, attr=ATTRSETHEATPOWER: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.sbsetp2, SIGNAL("returnPressed(double)"), func_callback)

        func_callback = lambda v="", sense=SENSE2, attr=ATTRSETHEADPID: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.cbpidh2, SIGNAL("stateChanged(int)"), func_callback)

        func_callback = lambda v="", sense=SENSE2, attr=ATTRSETHEATAUTO: self.processAttributeUpdate(v, sense, attr)
        self.connect(self.cbautoh2, SIGNAL("stateChanged(int)"), func_callback)

            # events from command line talking with the device
        self.connect(self.ledevcommand, SIGNAL("returnPressed()"), self.processDeviceCommand)

            # events from file browse dialog
        self.connect(self.btnfbrowse, SIGNAL("clicked()"), self.openFileDialog)

            # events from data saving procedures or related
        self.connect(self.btnStartStopWrite, SIGNAL("clicked()"), self.processStartStopWrite)
        self.connect(self.lefname, SIGNAL("textChanged(const QString&)"), self.lefnamecopy, SLOT("setText(QString)"))
        self.connect(self.lefnamecopy, SIGNAL("textChanged(const QString&)"), self.lefname, SLOT("setText(QString)"))
            # insert label to the data file
        self.connect(self.btnLabelWrite, SIGNAL("clicked()"), self.processLabelInsertion)

            # hide show graph window
        self.connect(self.cbshowgraph, SIGNAL("stateChanged(int)"), self.processShowHideGraph)

        #graphWindow - sending data to the graph Window
        self.connect(self, SIGNAL("plotGraph"), self.graph.showData)
        self.connect(self, SIGNAL("plotSetPoints"), self.graph.updateSetPoints)

        # tango reboot signals - show/hide progress bar
        self.connect(self.tango, SIGNAL(SIGNALTANGOREBOOT), self.trackTangoReboot)

        # threading events
        self.renewThreadEvents()
        return

    def test(self, *tlist):
        print(tlist)

    # renew threads and their messages
    def renewThreadEvents(self):
        if(self._mainThread is not None):
            # programDebug reports
            self.connect(self._mainThread, SIGNAL(SIGNALDEBUGMEASUREMENT), self.makeShortTextReport)

    # create main widge
    def createCentralWidget(self):
        title = "Mercury iTC control"
        self.setWindowTitle(title)
        # main widget - upper area for main controls
        # lower aread - for cryostat controls
        wdgt = QWidget()
        grid = QGridLayout()
        wdgt.setLayout(grid)

        self.cmbdevice = QComboBox()
        self.createDeviceComboBox()
        self.btnStartStop = QPushButton(BTNSTART)
        self.btnInit = QPushButton(BTNINIT)
        self.setWidgetsDisable(False, self.btnStartStop)
        self.btnKickTango = QPushButton(BTNKICKTANGO)

        # create tabbed interface
        self.tab = QTabWidget()
        self.tab.setTabBar(TabBar())                # set custom tabs style for better view - defined below
        self.tab.setTabPosition(QTabWidget.South)

        grid.addWidget(self.btnKickTango, 0, 0)
        grid.addWidget(self.cmbdevice, 0, 1)
        grid.addWidget(self.btnInit, 0, 2)
        grid.addWidget(self.btnStartStop, 0, 3)
        grid.addWidget(self.tab, 1,0, 1, 4)
        grid.setColumnStretch(1, 50)

        # adjust control widgets
        font = QFont("Arial", 12)
        self.setWidgetsFont(font, self.cmbdevice)
        font = QFont("Arial", 11)
        self.setWidgetsFont(font, self.btnStartStop, self.btnInit, self.btnKickTango)
        self.setWidgetsMinHeight(40, self.cmbdevice, self.btnStartStop, self.btnInit)
        self.setWidgetsMinWidth(100, self.btnInit, self.btnStartStop)

        # create a specific palette for tabs widget background
        # avoid using style sheets because of child widget inheritance
        tabcolor = QColor(250, 250, 250)
        tabpal = QPalette()
        tabpal.setColor(QPalette.Window, tabcolor)

        # setting specific tabs
        self.createReadTab(self.tab, tabpal)
        self.createSetTab(self.tab, tabpal)
        self.createSaveTab(self.tab, tabpal)
        self.createReportTab(self.tab, tabpal)
        self.createExpertTab(self.tab, tabpal)
        # self.tab.setStyleSheet("background-color: rgb(255,255,255)")

        # adjust style
            # tooltips
        self.setWidgetsTooltips((self.btnInit, "Resets Mercury iTC settings: full stop of the heating devices, temperature set-point is set to 300K"),
                                (self.btnStartStop, "Starts/Stops measurement of temperature and other Mercury iTC parameters"),
                                (self.cmbdevice, "Device selection, test of Tango and Device connection"))

        return wdgt


    # create tab for setting values
    def createReadTab(self, tab, pal):
        title = "Read Temperature"

        wdgt = QWidget()
        grid = QGridLayout()
        wdgt.setLayout(grid)
        grid.setSpacing(10)
        
        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # layout through the grid
        (tlabel, hlabel ) = (QLabel("Temperature (K):"), QLabel("Heater readings:"))
        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(tlabel, 0, 1)
        grid.addWidget(hlabel, 0, 2)

        lsensor1 = QLabel("Sensor1")
        lsensor1.setStyleSheet("background-color: rgb(255,230,230)")
        lsensor2 = QLabel("Sensor2")
        lsensor2.setStyleSheet("background-color: rgb(230,230,255)")

        self.ltemp1 = QLabel("100")
        self.ltemp1.setStyleSheet("background-color: rgb(255,150,150)")
        self.ltemp2 = QLabel("100")
        self.ltemp2.setStyleSheet("background-color: rgb(200,200,255)")

        self.lheatpow1 = QLabel("1W")
        self.lheatpow2 = QLabel("1W")
        self.lheatpc1 = QLabel("1%")
        self.lheatpc2 = QLabel("1%")
        self.lheatcurr1 = QLabel("1A")
        self.lheatcurr2 = QLabel("1A")
        
        grid.addWidget(lsensor1, 1, 0)
        grid.addWidget(lsensor2, 2, 0)

        grid.addWidget(self.ltemp1, 1, 1)
        grid.addWidget(self.ltemp2, 2, 1)

        # right top field - heater 1 output
        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.lheatpow1, 0, 0)
        tgrid.addWidget(self.lheatpc1, 1, 0)
        tgrid.addWidget(self.lheatcurr1, 2, 0)
        grid.addWidget(twdgt, 1, 2)

        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.lheatpow2, 0, 0)
        tgrid.addWidget(self.lheatpc2, 1, 0)
        tgrid.addWidget(self.lheatcurr2, 2, 0)
        grid.addWidget(twdgt, 2, 2)

        # button to start/stop writing
        self.btnStartStopWrite = QPushButton(BTNSTARTWRITE)
        grid.addWidget(self.btnStartStopWrite, 2, 5)

        # button to insert a custom label inside the data file
        self.btnLabelWrite = QPushButton(BTNINSERTLABEL)
        grid.addWidget(self.btnLabelWrite, 2, 6)

        # additions for filename and label controls
        fwlabel = QLabel("File and Plot controls:")
        twdgt = QWidget()
        tgrid = QGridLayout(twdgt)
        tgrid.addWidget(QLabel("Filename:"), 0, 0)
        tgrid.addWidget(QLabel("Custom Label:"), 1, 0)
        self.lefnamecopy = QLineEdit(DEFAULTFILENAME)
        self.lelabel = QLineEdit("")
        self.cbshowgraph = QCheckBox("Show Graph")
        tgrid.addWidget(self.lefnamecopy, 0, 1)
        tgrid.addWidget(self.lelabel, 1, 1)
        tgrid.addWidget(self.cbshowgraph, 2, 1)
        tgrid.setColumnStretch(1, 100)

        self.setWidgetsStyleSheet("border: 2 solid #000;", self.lefnamecopy, self.lelabel)
        self.setWidgetsMinHeight(30, self.lefnamecopy, self.lelabel)

        grid.addWidget(fwlabel, 0, 5, 1, 2)
        grid.addWidget(twdgt, 1, 5, 1, 2)

        grid.setColumnStretch(4, 100)
        grid.setRowStretch(3, 100)

        # adjust style
            # Headers
        font = QFont("Tahoma", 9, QFont.DemiBold)
        self.setWidgetsFont(font, tlabel, hlabel, fwlabel)
            # Sensor Labels
        font = QFont("Arial", 12)
        self.setWidgetsFont(font, lsensor1, lsensor2)
            # temperature readings
        font = QFont("Arial", 20, QFont.DemiBold)
        self.setWidgetsFont(font, self.ltemp1, self.ltemp2)
            # power readings
        font = QFont("Arial", 10, QFont.DemiBold)
        self.setWidgetsFont(font, self.lheatpow1, self.lheatpow2, self.lheatpc1, self.lheatpc2, self.lheatcurr1, self.lheatcurr2)
            # adjust width
        self.setWidgetsMinWidth(100, lsensor2, lsensor1, self.btnStartStopWrite, self.btnLabelWrite)
        self.setWidgetsMinWidth(150, self.ltemp1, self.ltemp2)
            # adjust text alignment
        self.setWidgetsAlignment(Qt.AlignHCenter|Qt.AlignVCenter,  self.ltemp1, self.ltemp2, lsensor1, lsensor2, tlabel, hlabel, self.lheatpow1, self.lheatpow2, self.lheatpc1, self.lheatpc2, self.lheatcurr1, self.lheatcurr2)
        self.setWidgetsAlignment(Qt.AlignVCenter|Qt.AlignRight, self.lheatpow1, self.lheatpow2, self.lheatpc1, self.lheatpc2, self.lheatcurr1, self.lheatcurr2)
            # adjust height
        self.setWidgetsMinHeight(85, lsensor1, lsensor2, self.btnStartStopWrite, self.btnLabelWrite)

            #set tooltips
        self.setWidgetsTooltips((self.ltemp1, "Current temperature (Sensor1)"), (self.ltemp2, "Current temperature (Sensor2)"), 
                                (self.lheatpow1, "Current power output (Sensor1, Watts)"), (self.lheatpow2, "Current power output (Sensor2, Watts)"),
                                (self.lheatcurr1, "Current power output (Sensor1, Amps)"), (self.lheatcurr2, "Current power output (Sensor2, Amps)"),
                                (self.lheatpc1, "Current power output (Sensor1, %)"), (self.lheatpc2, "Current power output (Sensor2, %)"))

            # disable certain widgets by default
        self.setWidgetsDisable(True, self.btnLabelWrite)

        tab.addTab(wdgt, title)
        return

    # create tab for setting set points - I am lazy to write a quick style wrapper for twdgt control, maybe later
    def createSetTab(self, tab, pal):
        title = "Control Heater"

        wdgt = QWidget()
        grid = QGridLayout()
        wdgt.setLayout(grid)
        grid.setSpacing(10)
        
        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        (tlabel, plabel, hlabel) = (QLabel("Temperature set-point (K):"), QLabel("Power set-point (%):"), QLabel("Heater control (ON/OFF):"))

        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(tlabel, 0, 1)
        grid.addWidget(plabel, 0, 2)
        grid.addWidget(hlabel, 0, 3)

        lheater1 = QLabel("Heater1")
        lheater2 = QLabel("Heater2")
        lheater1.setStyleSheet("background-color: rgb(255,230,230)")
        lheater2.setStyleSheet("background-color: rgb(230,230,255)")

        # set temperature spin box
        self.sbsett1 = MQDoubleSpinBox()
        self.sbsett2 = MQDoubleSpinBox()

        self.sbsett1.setRange(MINTEMP, MAXTEMP)
        self.sbsett1.setDecimals(0)
        self.sbsett2.setRange(MINTEMP, MAXTEMP)
        self.sbsett2.setDecimals(0)
        self.sbsett1.setSingleStep(TEMPSTEP)
        self.sbsett2.setSingleStep(TEMPSTEP)

        # set power spin box
        self.sbsetp1 = MQDoubleSpinBox()
        self.sbsetp2 = MQDoubleSpinBox()

        self.sbsetp1.setRange(MINPOW, MAXPOW)
        self.sbsetp2.setRange(MINPOW, MAXPOW)
        self.sbsetp1.setSingleStep(POWSTEP)
        self.sbsetp2.setSingleStep(POWSTEP)

        # checkboxes for heater control
        self.cbautoh1 = QCheckBox("Heater On (Auto mode)")
        self.cbautoh2 = QCheckBox("Heater On (Auto mode)")
        self.cbpidh1 = QCheckBox("PID On")
        self.cbpidh2 = QCheckBox("PID On")

        grid.setColumnStretch(4, 100)
        grid.setRowStretch(3, 100)

        grid.addWidget(lheater1, 1, 0)
        grid.addWidget(lheater2, 2, 0)

        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.sbsett1, 0, 0)
        grid.addWidget(twdgt, 1, 1)

        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.sbsett2, 0, 0)
        grid.addWidget(twdgt, 2, 1)

        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.sbsetp1, 0, 0)
        grid.addWidget(twdgt, 1, 2)

        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.sbsetp2, 0, 0)
        grid.addWidget(twdgt, 2, 2)

        # right fields - heater 1 control
        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.cbautoh1, 0, 0)
        tgrid.addWidget(self.cbpidh1, 1, 0)
        grid.addWidget(twdgt, 1, 3)

        # right fields - heater 2 control
        twdgt = QWidget()
        twdgt.setStyleSheet("background-color: rgb(200,200,200)")
        tgrid = QGridLayout()
        twdgt.setLayout(tgrid)
        tgrid.addWidget(self.cbautoh2, 0, 0)
        tgrid.addWidget(self.cbpidh2, 1, 0)
        grid.addWidget(twdgt, 2, 3)

        # adjust style
            # Headers
        font = QFont("Tahoma", 9, QFont.DemiBold)
        self.setWidgetsFont(font, tlabel, plabel, hlabel)
            # power readings
        font = QFont("Arial", 10, QFont.DemiBold)
        self.setWidgetsFont(font, self.cbautoh1, self.cbautoh2, self.cbpidh1, self.cbpidh2)
            # heater Labels
        font = QFont("Arial", 12)
        self.setWidgetsFont(font, lheater1, lheater2)
            # power and temperature settings
        font = QFont("Arial", 14, QFont.Bold)
        self.setWidgetsFont(font, self.sbsett1, self.sbsett2, self.sbsetp1, self.sbsetp2)
            # adjust width
        self.setWidgetsMinWidth(100, lheater1, lheater2)
        self.setWidgetsMinWidth(150, self.sbsett1, self.sbsett2, self.sbsetp1, self.sbsetp2)
            # adjust text alignment
        self.setWidgetsAlignment(Qt.AlignHCenter|Qt.AlignVCenter,  self.sbsett1, self.sbsett2, self.sbsetp1, self.sbsetp2, lheater1, lheater2, tlabel, hlabel, plabel)
            # adjust backgound color
        self.setWidgetsStyleSheet("background-color: rgb(245,245,245)", self.sbsett1, self.sbsett2,  self.sbsetp1,  self.sbsetp2)
            # adjust widget height
        self.setWidgetsMinHeight(85, lheater1, lheater2)

            # tooltips
        self.setWidgetsTooltips((self.sbsett1, "Temperature set-point (Sensor1)"), (self.sbsett2, "Temperature set-point (Sensor2)"),
                                (self.sbsetp1, "Power manual set-point (Sensor1 - auto mode should be OFF)"), (self.sbsetp2, "Power manual set-point (Sensor2 - Auto mode should be OFF)"),
                                (self.cbautoh1, "Set Auto mode of the heater (Sensor1)"), (self.cbautoh2, "Set Auto mode of the heater (Sensor2)"),
                                (self.cbpidh1, "Set PID mode of the heater (Sensor1)"), (self.cbpidh2, "Set PID mode of the heater (Sensor2)")
                                )

        tab.addTab(wdgt, title)
        return

    # create saving tab to control saving parameters
    def createSaveTab(self, tab, pal):
        title = "Control data saving"

        wdgt = QWidget()
        grid = QGridLayout()
        wdgt.setLayout(grid)
        grid.setSpacing(10)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)


        # spacer
        grid.addWidget(QLabel(""), 0, 0)

        grid.addWidget(QLabel("File directory: "), 1, 0)
        self.lefdir = QLineEdit(QDir.currentPath())
        grid.addWidget(self.lefdir, 1, 1)

        self.btnfbrowse = QToolButton()
        grid.addWidget(self.btnfbrowse, 1, 2)
        grid.addWidget(QLabel("File name: "), 2, 0)
        self.lefname = QLineEdit(DEFAULTFILENAME)
        grid.addWidget(self.lefname, 2, 1)

        self.setWidgetsStyleSheet("border: 2 solid #000;", self.lefname, self.lefdir)
        self.setWidgetsMinWidth(350, self.lefname, self.lefdir)
        self.setWidgetsMinHeight(30, self.lefname, self.lefdir)
        self.lefdir.setReadOnly(True)

        grid.setColumnStretch(3, 50)
        grid.setRowStretch(3, 50)

        w = self.btnfbrowse
        pal = QLineEdit().styleSheet()
        w.setStyleSheet("")

        tab.addTab(wdgt, title)
        return

    # create expert tab for device communication
    def createExpertTab(self, tab, pal):
        title = "Expert mode"

        wdgt = QWidget()
        grid = QGridLayout()
        wdgt.setLayout(grid)
        grid.setSpacing(10)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # most important interface parts
        self.ledevcommand = QLineEdit(SCPITEST)
        self.ledevcommand.setStyleSheet("background-color: rgb(240, 240, 240); border: 2 solid #000;")
        self.teresponse = QTextEdit("")
        self.teresponse.setStyleSheet("background-color: rgb(240, 240, 240); border: 2 solid #000;")
        self.teresponse.setReadOnly(True)

        self.setWidgetsMinHeight(30, self.ledevcommand)

        grid.addWidget(QLabel("Device command: "), 0, 0)
        grid.addWidget(self.ledevcommand, 0, 1)
        grid.addWidget(QLabel("Device response: "), 1, 0)
        grid.addWidget(self.teresponse, 1, 1)

        grid.setRowStretch(1, 50)
        grid.setColumnStretch(1, 50)

        tab.addTab(wdgt, title)
        return

    # create expert tab for device communication
    def createReportTab(self, tab, pal):
        title = "Program Reports"

        wdgt = QWidget()
        grid = QGridLayout()
        wdgt.setLayout(grid)
        grid.setSpacing(10)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # most important interface parts
        self.tereport = QTextEdit(DISCLAMER)
        self.tereport.setStyleSheet("background-color: rgb(240, 240, 240); border: 2 solid #000;")
        self.tereport.setReadOnly(True)

        grid.addWidget(QLabel("Debugging and measurement reports: "), 0, 0)
        grid.addWidget(self.tereport, 1, 0)

        grid.setRowStretch(1, 50)
        grid.setColumnStretch(0, 50)

        tab.addTab(wdgt, title)
        return

    # creates widget to track tango reboot process
    def createTangoRebootWidget(self):
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(QPalette(QColor(200, 200, 255)))

        self.pbreboot = QProgressBar()
        self.pbreboot.setRange(0, 100)

        grid.addWidget(QLabel("Rebooting Tango Server: "), 0, 0)
        grid.addWidget(self.pbreboot, 0, 2)
        grid.setColumnMinimumWidth(1, 20)
        grid.setColumnStretch(2, 50)
        grid.setSpacing(0)

        self._status.setMinimumHeight(41)
        return wdgt

    # setup combobox for device
    def createDeviceComboBox(self):
        string = "   %s - %s"%(TANGODEVICE["nick"], TANGODEVICE["link"])
        self.cmbdevice.addItem("   Try Tango and Device Connection", "")
        self.cmbdevice.addItem(string, TANGODEVICE)

    # disable/enable widgets in a sequence - for simplicity 
    def setWidgetsDisable(self, flag, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setDisabled(flag)

    # sets font to a seq. of widgets
    def setWidgetsFont(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setFont(value)

    # sets min dimentions to a seq. of widgets
    def setWidgetsMinHeight(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setMinimumHeight(value)


    # sets min dimentions to a seq. of widgets
    def setWidgetsMinWidth(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setMinimumWidth(value)


    # sets text alignment to a seq. of widgets
    def setWidgetsAlignment(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setAlignment(value)

    # sets widgets stylesheet alignment to a seq. of widgets
    def setWidgetsStyleSheet(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setStyleSheet(value)

    # sets tooltips for widgets in a sequence
    def setWidgetsTooltips(self, *tlist):
        for member in tlist:
            (wdgt, tooltip) = member
            wdgt.setToolTip(tooltip)

    # window icon
    def setCryoIcon(self, color):
        (w, h) = (32, 32)
        pixmap = QPixmap(w, h)
        pixmap.fill(color)

        painter = QPainter()
        painter.begin(pixmap)

        color = QColor(255,255,255)
        pen = QPen(color)
        pen.setWidth(2)

        painter.setPen(pen)

        s = 2
        snowflake = (
                        (s, s, w-s, h-s),
                        (s, h-s, w-s, s),
                        (s, h/2, w-s, h/2),
                        (w/2, s, w/2, h-s)
                    )
        
        for line in snowflake:
            (x1, y1, x2, y2) = line
            painter.drawLine(x1,y1,x2,y2)

        painter.end()

        icon = QIcon(pixmap)
        self.setWindowIcon(QIcon(pixmap))
        return icon

    # resize event for later use
    def resizeEvent(self, event):
        string = "Action: resize to (%i:%i)"%(event.size().width(), event.size().height())
        self.showShortMsg(string)
        event.accept()
        return

    # status bar related
        # status bar messages - 10s
    def showLongMsg(self, msg, error=False):
        duration = 10000
        format = "%s"
        if(error):
            format = "Error: %s"
        self.showMessage(format%msg, duration)

    # status bar messages - 3s
    def showShortMsg(self, msg, error=False):
        duration = 3000
        format = "%s"
        if(error):
            format = "Error: %s"
        self.showMessage(format%msg, duration)

    # show message
    def showMessage(self, msg, duration):
        # show message
        self._status.showMessage(msg, duration)


    # child controls related effects
    def checkDeviceOnlineStatus(self, switch):
        if(switch>0):
            # check response from tango - in case of success open access to the other window controls
            res = self.tango.checkDeviceOnlineStatus()
            if(res):
                self.setWidgetsDisable(False, self.btnInit, self.btnStartStop, self.tab)
                self.setWidgetsDisable(True, self.cmbdevice)
            else:
                self.cmbdevice.setCurrentIndex(0)
        return

    # init cryocooler - set all neccesary values - QPushButton
    def processInitCryoDevice(self):
        # create a special worker thread
        self._worker = WorkerThread(self.tango.initCryoDevice, (self.btnInit, self.btnStartStop), self)
        # set sleep interval to prevent user pushing this button too often
        self._worker.setSleepInterval(PREVENTUSEROFTENRESETINTERVAL)
        self._worker.start()

    # process start/stop measurement commands - QPushButton
    def processStartStopMeasurement(self):
        if(self._mainThread is not None and self._mainThread.isRunning()):     # measurement thread is running - stop it
            self._mainThread.stop()
            self._mainThread.wait()
            self.btnStartStop.setText(BTNSTART)
        else:                               # thread is not running - start it
            self.btnStartStop.setText(BTNSTOP)
            self._mainThread = WorkerThread(self.processMainUpdate, (), self)
            self._mainThread.setSleepInterval(DEBUGTIMERINTERVAL)
            self._mainThread.setRepeating(True)
            # update thread events
            self.renewThreadEvents()
            self._mainThread.start()
        return

    # main work - reading TangoServer, updating gui - works in the thread
    def processMainUpdate(self):
        # first check if we can read - tango readmutex is not locked - other process accesses this mutex
        if(not self.tango.isReadAllowed()):
            return
        else:
            # read attributes from tango
            (sense1, sense2, bsuccess) = self.tango.readController()

            # make short text report with measured values
            self._mainThread.emit(SIGNAL(SIGNALDEBUGMEASUREMENT), bsuccess, sense1, sense2)
            
            # update gui only if bsuccess has been received
            if(bsuccess):

                # update interface with measured values - pass widgets by argument
                self.fillUISense(sense1, self.ltemp1, self.lheatpow1, self.lheatcurr1, self.lheatpc1, self.cbpidh1, self.cbautoh1, self.sbsett1, self.sbsetp1)
                self.fillUISense(sense2, self.ltemp2, self.lheatpow2, self.lheatcurr2, self.lheatpc2, self.cbpidh2, self.cbautoh2, self.sbsett2, self.sbsetp2)

                # check data and time functions
                # date and time functions - to generate timestamp
                datetime = QDateTimeM().currentDateTime()
                date = datetime.date()
                time = datetime.time()
                timestamp = datetime.toMSecsSinceEpoch()

                # prepare values for file and gui, adjust text values a little
                (stemp1, sheatpow1, stemp2,  sheatpow2) = (self.ltemp1.text(), self.lheatpow1.text().replace(" W", ""), self.ltemp2.text(), self.lheatpow2.text().replace(" W", ""))

                # check if writer thread is running, prepare values and pass them for writing
                if(self.thWrite is not None and self.thWrite.isRunning()):
                    time = "%i\t%04i-%02i-%02i\t%02i:%02i:%02i:%03i"%(timestamp, date.year(), date.month(), date.day(),time.hour(), time.minute(), time.second(), time.msec())
                    string = QString("%s\t%s\t%s\t%s\t%s\n"%(time, stemp1, sheatpow1, stemp2,  sheatpow2))
                    self.thWrite.addData(string)

                # save measured data into special dict
                # data for graph - what we show - separate data stream +1 timestamp, +2 channels
                with(QMutexLocker(self.datagraphmutext)):
                    self.datagraph[timestamp] = (float(stemp1), float(stemp2))
                
                # forward data to the graph window
                self.emit(SIGNAL("plotGraph"), self.datagraph)

                # forward set point data to the graph
                (setp1, setp2) = (self.sbsett1.value(), self.sbsett2.value())
                self.emit(SIGNAL("plotSetPoints"), setp1, setp2)

                # clean data graph storage object to save memory
                with(QMutexLocker(self.datagraphmutext)):
                    self.datagraph = {}
            
        return

    # make some representation of measured values for 'PEOPLE'
    def makeShortTextReport(self, bsuccess, sense1, sense2):
        (outsense1, outsense2) = (["Sensor: Sense1"], ["Sensor: Sense2"])

        # prep values from first sensor, consider that there could be an error
        if(type(sense1) is dict):
            for k in sense1:
                outsense1.append("%s: %.04f" %(k, sense1[k]))
        else:
            outsense1.append(str(sense1))

        # prep values from second sensor, consider that there could be an error
        if(type(sense1) is dict):
            for k in sense2:
                outsense2.append("%s: %.04f" %(k, sense2[k]))
        else:
            outsense2.append(str(sense2))

        temp = "True"
        if(not bsuccess):
            temp = "False"

        output = "Reading result: %s\n" % temp
        # join these values
        for i in range(len(outsense1)):
            output = output + "%s\t\t%s\n" %(outsense1[i], outsense2[i])

        self.tereport.setText(QString(output))
        return

    # fill user interface with values
    def fillUISense(self, sense, *widgets):
        # assign widgets to their roles
        (wtemp, wheatpow, wheatcurrent, wheatpowpc, wpid, wauto, wsett, wsetp) = widgets

        for k in sense:
            # assign widget to a specific attribute, modify value if needed
            (wdgt, value, format) = (None, sense[k], "%.2f")
            if(k==ATTRGETTEMP):
                wdgt = wtemp
            elif(k==ATTRGETHEATPOWER):
                wdgt = wheatpow
                format += " W"
            elif(k==ATTRGETHEATCURRENT):
                wdgt = wheatcurrent
                format += " A"
            elif(k==ATTRGETHEATPOWERPERC):
                wdgt = wheatpowpc
            # set attributes
            elif(k==ATTRSETHEADPID):
                wdgt = wpid
            elif(k==ATTRSETHEATAUTO):
                wdgt = wauto
            elif(k==ATTRSETTEMPPOINT):
                wdgt = wsett
            elif(k==ATTRSETHEATPOWER):
                wdgt = wsetp

            # convert value, update UI by type
            t = type(wdgt)
            if(t is QLabel):                # QLabel type
                value = format % value

                if(k==ATTRGETHEATPOWERPERC):    # to avoid % symbol in the format
                    value += " %"
                wdgt.setText(value)
            elif(t is QCheckBox):           # QCheckBox type - set checked or not
                state = False
                if(value > 0.):
                    state = True
                wdgt.setChecked(state)
            elif((t is QDoubleSpinBox or t is MQDoubleSpinBox) and not wdgt.hasFocus()):      # QDouble spinbox type - sets value - should not update if the window is being edited
                wdgt.setValue(value)
        return

    # format values we show in the interface
    def formatMeasurement(self, *args):
        tlist = []
        if(len(args)):
            for arg in args:
                if(arg != None):
                    tlist.append("%.2f" % float(arg))
                else:
                    tlist.append("n.a.")
        return tlist

    # process attribute update - write to the device using tango
    def processAttributeUpdate(self, *tlist):
        # split values
        (attrvalue, sense, attrname) = tlist

        string = "Sensor (%s); Attribute: (%s); New value: (%.0f);"%(sense, attrname, float(attrvalue))
        self.showShortMsg(string)

        # stop _worker if necessary, if running, wait for it
        # should be one action after another
        if(self._worker is not None and self._worker.isRunning()):
            self._worker.stop()
            self._worker.wait()

        # make thread wrapper
        func_callback = lambda s=sense, a=attrname, v=attrvalue: self.makeAttributeUpdate(s, a, v)
        self._worker = WorkerThread(func_callback, (self.btnInit))
        self._worker.start()
        return

    # function passed to the worker thread for device parameter updating
    def makeAttributeUpdate(self, sense, attrname, attrvalue):
        brestart = False

        # shoould put updates from _mainThread on hold - empty loop running
        if(self._mainThread is not None and self._mainThread.isRunning()):
            self._mainThread.putOnHold()
            brestart = True

        # write tango attributes
        self.tango.writeController(sense, attrname, attrvalue)

        # check if we need to restart _mainThread after writing, actually, release hold - make thread do something useful
        if(brestart):
            self._mainThread.putOnHold(False)
        return

    # operations applied for gui in case of error - FAIL reported by TangoObject
    def actOnFail(self):
        # stop threads
        # clean up worker thread
        if(self._worker is not None and not self._worker.isFinished()):
            self._worker.stop()
            self._worker.wait()

        # writing thread - wrapper take care for thread wait() call
        if(self.thWrite is not None and self.thWrite.isRunning()):
            self.thWrite.stop()
        
        # stop _mainThread if it is running
        if(self._mainThread is not None and self._mainThread.isRunning()):
            self._mainThread.stop()
            self._mainThread.wait()
        
        # update widgets
            # adjust text
        self.btnStartStopWrite.setText(BTNSTARTWRITE)
        self.btnStartStop.setText(BTNSTART)

            # adjust disabled status
        self.setWidgetsDisable(True, self.btnInit, self.btnStartStop, self.tab)
        self.setWidgetsDisable(False, self.cmbdevice)
        self.cmbdevice.setCurrentIndex(0)

        return

    # event - get device command, proccess it with tango and a worker thread
    def processDeviceCommand(self):
        cmd = self.ledevcommand.text()
        
        func_callback = lambda arg=cmd: self.tango.execSingleCommand(arg)

        # stop _worker if necessary
        if(self._worker is not None and self._worker.isRunning()):
            self._worker.stop()
            self._worker.wait()

        # setup worker thread for the task
        self.showShortMsg("Sending command to the device: %s" % cmd)
        self._worker = WorkerThread(func_callback, (self.ledevcommand))
        self._worker.start()

    # on signal from tango object that device command was processed
    def processDeviceCommandResponse(self, cmd, res):
        output = QString("CMD > %s \nDEV < %s\n"%(cmd, res))
        self.teresponse.append(output)
        self.teresponse.moveCursor(QTextCursor.End)
        self.teresponse.ensureCursorVisible()

        self.ledevcommand.setFocus()

    #use file dialog to select filenames for saving data
    def openFileDialog(self):
        fdir = self.lefdir.text()
        fname = self.lefname.text()

        currdir = QDir(fdir)
        currpath = currdir.filePath(fname)

        fdialog = QFileDialog.getSaveFileName(self, "Select File Name", fdir, "Any files: (*.*);; Ascii files (*.txt *.dat *.xy)")

        while(not self.checkFile(fdialog) and not self.checkFile(currpath)):
            fdialog = QFileDialog.getSaveFileName(self, "Select File Name", fdir, "Any files: (*.*);; Ascii files (*.txt *.dat *.xy)")

        path = fdialog
        if(fdialog): #filename is correct from the dialog
            finfo = QFileInfo(fdialog)
            self.lefdir.setText(finfo.path())
            self.lefname.setText(finfo.fileName())
        else:        #cancel was pressed
            path = currpath
        
        self.showShortMsg("Using file: "+path)

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
            fi.close()
        except IOError:
            self.showShortMsg("Error: cannot write to a file (%s)" % fn)
            bcorrect = False

        return bcorrect

        #starts - stops writing
    def processStartStopWrite(self):
        if(self.thWrite is not None and self.thWrite.isRunning()):  #case the writing thread is kind of running - stop it
            self.thWrite.stop()
            self.btnStartStopWrite.setText(BTNSTARTWRITE)
            self.showShortMsg("Writing thread has stopped..")

            # enable necessary widgets and disable other
            self.setWidgetsDisable(False, self.btnfbrowse, self.lefname, self.lefnamecopy)
            self.setWidgetsDisable(True, self.btnLabelWrite)
        else:                           #case we start the writing thread
            # check if we can write to the file
            (di, fn) = (self.lefdir.text(), self.lefname.text())
            fn = QDir(di).filePath(fn)
            if(not self.checkFile(fn)):
                self.showLongMsg("Error: please check file name and file path fields")
                return

            #start thread responsible for writing
            self.thWrite.start(fn)
            self.btnStartStopWrite.setText(BTNSTOPWRITE)
            self.showShortMsg("Writing thread has started..")

            # disable widgets responsible for file change and enable ones responsible for label addition
            self.setWidgetsDisable(True, self.btnfbrowse, self.lefname)
            self.setWidgetsDisable(False, self.btnLabelWrite)

        return

    # add custom user defined data header to the text
    def processLabelInsertion(self):
        text = self.lelabel.text()
        if(text.length()==0):
            self.showShortMsg("No label given, aborting label saving", True)
            return

        self.thWrite.timeHeader(text)
        return

    # process show hid of the graph window event
    def processShowHideGraph(self, state):
        if(state==Qt.Checked):
            rect = self.frameGeometry() 
            self.graph.show()
            self.graph.move(QPoint(rect.x()+rect.width(), rect.y()))
        else:
            self.graph.hide()
        return

    # hold main thread on external request, from one of the threads for instance
    def processHoldMainThread(self, flag=False):
        if(self._mainThread is not None and self._mainThread.isRunning()):
            self._mainThread.putOnHold(flag)

    # kick responsible tango server to reestablish a connection to the device
    def processKickTango(self):
        # check if main thread is running - bad, ask user to stop it and then start again
        if(self._mainThread is not None and self._mainThread.isRunning()):
            QMessageBox.critical(self, MSGBOXMAINTHREADTITLE, MSGBOXMAINTHREADCAPTION)
            return

        # stop _worker if necessary and wait for previous command completition
        if(self._worker is not None and self._worker.isRunning()):
            self._worker.stop()
            self._worker.wait()

        # start new worker
        self._worker = WorkerThread(self.tango.restartMercuryServer, (self.btnKickTango), self)
        self._worker.start()
        return

    # visually track tango server reboot
    def trackTangoReboot(self, value):
        if(value==0):
            self._status.addPermanentWidget(self.wtangoreboot)
            self.wtangoreboot.show()
        elif(value==100):
            self.wtangoreboot.hide()
            self._status.removeWidget(self.wtangoreboot)

        self.pbreboot.setValue(value)
        return

    # movement of the main window + simultaneous movement of the child graph window
    def moveEvent(self, event):
        (pos, oldpos) = (event.pos(), event.oldPos())

        if(self.isActiveWindow()):
            rect = self.frameGeometry() 
            self.graph.move(QPoint(rect.x()+rect.width(), rect.y()))
            
    # executed on window close - program end
    def closeEvent(self, event):
        # cleaning up threads
            # clean up worker thread
        if(self._worker is not None and not self._worker.isFinished()):
            self._worker.stop()
            self._worker.wait()

        # writing thread - wrapper take care for thread wait() call
        if(self.thWrite is not None and self.thWrite.isRunning()):
            self.thWrite.stop()
        
        # stop _mainThread if it is running
        if(self._mainThread is not None and self._mainThread.isRunning()):
            self._mainThread.stop()
            self._mainThread.wait()

        # close graph window
        event.accept()
        return


        
###
##  class CryoControl END
###


###
##  class TangoObject - controls communication with Tango device - reports values to gui
##                      values are reported through Qt signal propagation
###
class TangoObject(QObject):
    def __init__(self, parent=None):
        super(TangoObject, self).__init__(parent)

        self._mainTango = TANGODEVICE
        self._sense1 = TANGOSENSE1
        self._sense2 = TANGOSENSE2

        self.dev = None

        # need mutex to control reading - if mutex is busy, do not read
        self._readmutex = QMutex()

        # dicts to store sensor data
        self._sense1data = TANGOREADTEMPLATE.copy()
        self._sense2data = TANGOREADTEMPLATE.copy()

        # link to the administrative device - to restart in case of necessity
        self._starterlink = TANGOSTARTER
        self._mercuryserver = TANGOMERCPROC

    # should read value one by one and send their value to the gui
    # update - read all attributes first from device to tango attributes, then read them from tango one by one
    # used also to write attributes if passed to it, pass sensor, attribute and value
    def readController(self):
        bsuccess = True

        # use mutex to block external timer events for device access
        with(QMutexLocker(self._readmutex)):
            # fill data with zeros first, for a case of device timeout
            self._sense1data = TANGOREADTEMPLATE.copy()
            self._sense2data = TANGOREADTEMPLATE.copy()

            # test first device
            (dev, bsuccess) = self.tryDevice(self._sense1["link"])
            if(bsuccess):
                # reading attributes from the physical device to the tango
                dev.command_inout(CMDREAD)
                self.waitForResponse(dev)

                # reading attributes from tango - one by one
                for k in self._sense1data:
                    (v, bsuccess) = self.tryGetAttribute(dev, k)    # all values if read are float
                    if(not bsuccess):
                            break
                    else:
                        self._sense1data[k] = v.value

            # checking second sensor only if there was no problem reading the first one
            if(bsuccess):
                (dev, bsuccess) = self.tryDevice(self._sense2["link"])
                if(bsuccess):
                    # reading attributes from the physical device to the tango
                    dev.command_inout(CMDREAD)
                    self.waitForResponse(dev)

                    # reading attributes from tango - one by one
                    for k in self._sense2data:
                        (v, bsuccess) = self.tryGetAttribute(dev, k)    # all values if read are float
                        if(not bsuccess):
                            break
                        else:
                            self._sense2data[k] = v.value
        return (self._sense1data, self._sense2data, bsuccess)

    #  procedure for writing data to the device, a little complecated, but should
    def writeController(self, sense, attr, attrvalue):
        bsuccess = False
        dev = None

        with(QMutexLocker(self._readmutex)):
            # check type of the device - sensor1 or sensor2
            if(sense == SENSE1):
                dev = self._sense1
            elif(sense == SENSE2):
                dev = self._sense2

            # check if the device is our normal device
            if(dev is not None):
                # try to obtain reference to the device
                (dev, bsuccess) = self.tryDevice(dev["link"])

                # device connection was established
                if(bsuccess):
                    bsuccess = self.trySetAttribute(dev, attr, attrvalue)
        return bsuccess

    # check if we can read data and eventually write it, to prevent blocking of tango server
    def isReadAllowed(self):
        bres = self._readmutex.tryLock()
        if(bres):
            self._readmutex.unlock()
        return bres

    # should check communication with the device - returns true or false
    def checkDeviceOnlineStatus(self):
        bsuccess = True

        # typical error message
        errormsg = ERRTANGOOFF

        # check device connection trough try except approach and mainTango
        dev = None
        (dev, bsuccess) = self.tryDevice(self._mainTango["link"])

        # check device response
        res = ""
        if(bsuccess):
            # send a test command
            (res, bsuccess) = self.tryDeviceRWCommand(dev, CMDWRRAW, SCPITEST)

            # check device responsw
            if(bsuccess and QString(res).indexOf(SCPITESTRESPONSE)<0):
                errormsg = "Error: '%s' produces response '%s'; Check: Mercury iTC (Ethernet?+Remote mode?); Tango (online?, restarted?);"%(SCPITEST, res)
                bsuccess = False
        
        # provide response message // error messages are reported durin self.try* functions
        if(bsuccess):
            self.report("Device is online and reports correct values: (%s)"%res)
        else:
            self.reportFail(errormsg)

        return bsuccess

    # init cryo device - set necessary fields - returns False if an error was discovered
    def initCryoDevice(self):
        bsuccess = True

        # device used
        dev = None

        # put main thread on hold, prevent updating
        self.emit(SIGNAL(SIGNALHOLDMAINTHREAD), True)

        # adress first sensor and its heater, reset heater
        (dev, bsuccess) = self.tryDevice(self._sense1["link"])
        bsuccess = self.resetHeater(dev)

        # address second sensor and its heater, reset heater
        if(bsuccess):
            (dev, bsuccess) = self.tryDevice(self._sense2["link"])
            bsuccess = self.resetHeater(dev)

        # provide error message if needed, errors are reported in self.try* functions
        if(bsuccess):
            self.report("Device initialization was successful.")

        self.emit(SIGNAL(SIGNALHOLDMAINTHREAD), False)
        return bsuccess

    # reset heater set point and operation for a specific sensor - device
        # sets manual heater mode, heater power to 0, temperature set point - 300K
    def resetHeater(self, dev):
        bsuccess = True
        
        # last variable in the functions is the default and is value necessary for reset conditions
        if(bsuccess):
            bsuccess = self.devSetHeaterPID(dev, DEFAULTHEATPID)
        if(bsuccess):
            bsuccess = self.devSetHeaterAuto(dev, DEFAULTHEATAUTO)
        # let's not affect heater setpoint
        #if(bsuccess):
        #    bsuccess = self.devSetTempPoint(dev, DEFAULTHEATSETTEMP)
        if(bsuccess):
            bsuccess = self.devSetHeaterPower(dev, DEFAULTHEATSETPOWER)
        return bsuccess

    # device try functions - communication and error reporting
        # try device - create DeviceProxy, test it for exceptions, return state
    def tryDevice(self, link):
        (dev, bsuccess) = (None, True)

        errormsg = ERRTANGOOFF

        try: 
            dev = DeviceProxy(link)
        except DevFailed:
            bsuccess = False
            errormsg = errormsg+"; Error: DevError"
        except DevError:
            bsuccess = False
            errormsg = errormsg+"; Error: DevError"

        if(not bsuccess):
            self.reportFail(errormsg+" trying device online connectivity")

        return (dev, bsuccess)

        # try command to read write from tango device, return state
    def tryDeviceRWCommand(self, dev, cmd, strwrite):
        (res, bsuccess) = ("", True)

        errormsg = ERRTANGOOFF

        try: 
            res = dev.command_inout(cmd, strwrite)
        except DevFailed:
            bsuccess = False
            errormsg = errormsg+"; Error: DevFailed"
        except DevError:
            bsuccess = False
            errormsg = errormsg+"; Error: DevError"

        if(not bsuccess):
            self.reportFail(errormsg+" command_inout() call")

        return (res, bsuccess)

        # general function to try to set attribute, return state
    def trySetAttribute(self, dev, attrname, attrvalue):
        bsuccess = True

        errormsg = ERRTANGOOFF
        
        try:
            dev.write_attribute(attrname, attrvalue)
        except DevFailed:
            bsuccess = False
            errormsg = errormsg+"; Error: DevFailed"
        except DevError:
            bsuccess = False
            errormsg = errormsg+"; Error: DevError"

        if(not bsuccess):
            self.reportFail(errormsg+" write_attribute() call")
        else:
            self.waitForResponse(dev)

        return bsuccess

        # general fucntion to read attributes from the device
    def tryGetAttribute(self, dev, attrname):
        bsuccess = True
        res = ""

        errormsg = ERRTANGOOFF
        
        try:
            res = dev.read_attribute(attrname)
        except DevFailed:
            bsuccess = False
            errormsg = errormsg+"; Error: DevFailed"
        except DevError:
            bsuccess = False
            errormsg = errormsg+"; Error: DevError"

        if(not bsuccess):
            self.reportFail(errormsg+"; read_attribute() call")

        return (res, bsuccess)

    # functions to simplify operation with attributes - setting specific attributes
        # set heater PID mode - ON/OFF (ON-1, OFF-0)
    def devSetHeaterPID(self, dev, value=DEFAULTHEATPID):
        attrname = ATTRSETHEADPID

        # check string type values, transform them
        # in casse of int or float types - value must be 1 (ON) or 0 (OFF)
        if(type(value) is QString or type(value) is str):
            if(QString(value)==QString(OFF)):
                value = SETTINGOFF
            elif(QString(value)==QString(ON)):
                value = SETTINGON
        elif(value!=SETTINGOFF and value!=SETTINGON):
            value = DEFAULTHEATPID

        return self.trySetAttribute(dev, attrname, value)

        # set heater Auto mode - ON/OFF (ON-1, OFF-0)
    def devSetHeaterAuto(self, dev, value=DEFAULTHEATAUTO):
        attrname = ATTRSETHEATAUTO

        # check string type values, transform them
        # in casse of int or float types - value must be 1 (ON) or 0 (OFF)
        if(type(value) is QString or type(value) is str):
            if(QString(value)==QString(OFF)):
                value = SETTINGOFF
            elif(QString(value)==QString(ON)):
                value = SETTINGON
        elif(value!=SETTINGOFF and value!=SETTINGON):
            value = DEFAULTHEATAUTO

        return self.trySetAttribute(dev, attrname, value)

        # set heater power for manual mode
    def devSetHeaterPower(self, dev, value=DEFAULTHEATSETPOWER):
        attrname = ATTRSETHEATPOWER

        # check string type values, transform them, default value is 0% power
        if(type(value) is QString or type(value) is str):
            try:
                value = float(value)
            except ValueError:
                value = DEFAULTHEATSETPOWER
        return self.trySetAttribute(dev, attrname, value)

        # set heater temp setpoint
    def devSetTempPoint(self, dev, value=DEFAULTHEATSETTEMP):
        attrname = ATTRSETTEMPPOINT

        # check string type values, transform them, default value is 300K
        if(type(value) is QString or type(value) is str):
            try:
                value = float(value)
            except ValueError:
                value = DEFAULTHEATSETTEMP
        return self.trySetAttribute(dev, attrname, value)

    # functions for reporting 
        # general function
    def report(self, msg, berror=False):
        if(not berror):
            self.emit(SIGNAL(SIGNALREPORT), msg, berror)
        else:
            self.emit(SIGNAL(SIGNALFAILED), msg)

    # fail function
    def reportFail(self, msg):
        # report error - set Error flag
        self.report(msg, True)

    # implement a wait for device moving
    def waitForResponse(self, dev):
        while(dev.state()==DevState.MOVING):
            continue

    # implement a wait TangoDevice to reboot and become online
    def waitForZombie(self, dev):
        bsuccess = False
        while(not bsuccess):
            try:
                # exception
                dev.state()
                # online
                bsuccess = True
            except DevError:
                pass
            except DevFailed:
                pass


    # single device command read write
    def execSingleCommand(self, cmd):
        bsuccess = True

        # typical error message
        errormsg = ERRTANGOOFF

        # check device connection trough try except approach and mainTango
        dev = None
        (dev, bsuccess) = self.tryDevice(self._mainTango["link"])

        # check device response
        res = ""
        if(bsuccess):
            # send a test command
            cmd = str(cmd).upper()
            (res, bsuccess) = self.tryDeviceRWCommand(dev, CMDWRRAW, cmd)

            # check device responsw
            if(bsuccess):
                self.emit(SIGNAL(SIGNALCOMMAND), cmd, res)
        
        # provide response message // error messages are reported durin self.try* functions
        if(bsuccess):
            self.report("Device has responded: %s" % res)

        return bsuccess

    # restarts mercury service using Tango Starter service, waits for it to become available, don't treat errors here
    def restartMercuryServer(self):
        bsuccess = True
        dev = None

        # see if starter device is there - should be always there
        (dev, bsuccess) = self.tryDevice(self._starterlink)
        # check if Mercury Server is On or off, checks are not required, presume starter object is always there, running, watching
        if(bsuccess):
            self.emit(SIGNAL(SIGNALTANGOREBOOT), 0)
            # get list of running services
            res = dev.command_inout("DevGetRunningServers", True)
            # check if Mercury service is online or not
            bon = self.findRunningTangoServer(res, self._mercuryserver)
            
            # Mercury service is online, first stop the server, and wait untill it becomes offline
            # cannot use starter for status, does not treat restart process well
            if(bon):
                # initialte stop
                dev.command_inout("DevStop", self._mercuryserver)

                # wait untill starter marks the server as stopped
                res = dev.command_inout("DevGetRunningServers", True)
                while(self.findRunningTangoServer(res, self._mercuryserver)):
                    res = dev.command_inout("DevGetRunningServers", True)

            self.emit(SIGNAL(SIGNALTANGOREBOOT), 30)

            # start Mercury server anew
            # while loop makes sure that we really get stop
            bstarted = False
            while(not bstarted):
                try:
                    dev.command_inout("DevStart", self._mercuryserver)
                    bstarted = True
                except DevFailed:
                    pass
                except DevError:
                    pass

            self.emit(SIGNAL(SIGNALTANGOREBOOT), 60)
            
            # waiting for the server to start up in real life using _mainTango link
            brunning = False
            tdev = DeviceProxy(self._mainTango["link"])
            while(not brunning):
                try:
                    tdev.state()
                    brunning = True
                except DevError:
                    pass
                except DevFailed:
                    pass

            self.emit(SIGNAL(SIGNALTANGOREBOOT), 80)

            # final check that device is online using starter
            while(not self.findRunningTangoServer(dev.command_inout("DevGetRunningServers", True), self._mercuryserver)):
                pass
            self.emit(SIGNAL(SIGNALTANGOREBOOT), 100)
        return

    # test if server is in the list of running obtained by Tango Starter object
    def findRunningTangoServer(self, tlist, tserver):
        bon = False
        for server in tlist:
            if(server==tserver):
                bon = True
                break
        return bon

###
##  class TangoObject END
###


###
## class TabBar - for QTabWidget tab bar customization
## found in http://stackoverflow.com/questions/12901095/change-background-color-of-tabs-in-pyqt4
###
class TabBar(QTabBar):
    def paintEvent(self, event):

        painter = QStylePainter(self)
        option = QStyleOptionTab()

        for index in range(self.count()):
            self.initStyleOption(option, index)
            bgcolor = QColor(250,250,250)
            option.palette.setColor(QPalette.Window, bgcolor)
            painter.drawControl(QStyle.CE_TabBarTabShape, option)
            painter.drawControl(QStyle.CE_TabBarTabLabel, option)
###
## class TabBar END
## 
###

###
## class WorkerThread - to separate gui and time consuming operations, make gui more responsible
## gets function to execute and widgets to disable before execution and to reenable after execution
###
class WorkerThread(QThread):
    def __init__(self, operation, wdgtcontrol=None, parent=None):
        super(WorkerThread, self).__init__(parent)
        
        # operation to perform
        self._func = operation
        # widgets to disable
        self._wdgts = wdgtcontrol
        
        # flag to stop process
        self._bstop = False
        self._bstopmutex = QMutex() 

        # flag to control - one shot process or repeating
        self._brepeat = False

        # sleep timeout if needed for loop operation mode
        self._sleep = 0

        # flag to put thread on hold flag - for empty loop operation
        self._bhold = False
        return

    # main thread function
    def run(self):
        # disable widgets
        if(self._wdgts is not None):
            self.setWidgetsDisabled(True, self._wdgts)

        # execute main function
        while(not self._bstop):
            # do main task unless put on hold
            if(not self._bhold):
                self._func()

            # control repeating - stop if one shot command should be executed
            if(not self._brepeat):
                self.stop()

            # sleep in a loop if desired
            if(self._sleep>0):
                self.msleep(self._sleep)
        
        # enable widgets
        if(self._wdgts is not None):
            self.setWidgetsDisabled(False, self._wdgts)
        
        # confirm stop
        self.stop()
        return
    
    # useless function for now, but could be used in the future
    def stop(self):
        with(QMutexLocker(self._bstopmutex)):
            self._bstop = True
        
    # enable or disable list of widgets - handle if obkects were given as a list or tuple
    def setWidgetsDisabled(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]
        
        for w in tlist:
            w.setDisabled(value)

    # sets repeating protocol (thread loop)
    def setRepeating(self, flag=False):
        self._brepeat = flag
        return

    # sets sleep interval for certain cases, sleep before next loop
    def setSleepInterval(self, value=0):
        self._sleep = value
        return

    # sets the thread on hold, do looping without payload
    def putOnHold(self, flag=True):
        self._bhold = flag

###
## class WorkerThread END
## 
###

###
## Thread Writer Object - a thread to write data to a file
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

###
## End of ThreadWriter Object
###

###
##
## Thread Writer Wrapper Object - write data to a file
## for ease of renewing thread instances
##
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
        self.timeHeader(WRITESTART)
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
            self.timeHeader(WRITESTOP)
            self._thread.stop()
            self._thread.wait()

    #thread wrapping - add data
    def addData(self, data):
        self._thread.addData(data)
        return

    #thread wrapping - add 
    def setFileName(self, fn):
        self._thread.setFileName(fn)
        return

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
        return

    #header data
    def dataHeader(self):
        string = QString(WRITEDATAHEADER)
        self.addData(string)
        return
###
## End of ThreadWriteWrapper Object
###

###
## QDateTimeM object - to bring new PyQt functionality absent in the current control machine version; made a wrapper for immediate currentDateTime access
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
###
## End of QDateTimeM Object
###


#################################################################################### Plot Graph related objects
###
## TCGraph object - graph window
##
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

        # adjustable time limit
        self._timelimit = 1800000

        # storage 
        self.data = {}
        self.datamutex = QMutex()
        
    def initUI(self):
        self.resize(600,400)
        #background - color
        pal = QPalette()
        self.setAutoFillBackground(True)
        pal.setColor(QPalette.Window, QColor('blue').light())
        self.setPalette(pal)
        
           
        #prepare channel curves : getCurve(self, label, symb, penc, pens, brushc):
        c1 = self.getCurve('Sense1', Circle, Black, 2, Black)
        c2 = self.getCurve('Sense2', Circle, Red, 2, Red)

        #create a plot widget
        self.p = MPlot(
            c1, c2,
            '', self)

        # set autoplot
        self.p.autoplot = True

        self.p.setMinimumHeight(380)

        # plot marker for sense1 - balck
        self.qmark1 = QwtPlotMarker()
        self.qmark1.setLineStyle(1)
        self.qmark1.setYValue(11)
        pen = QPen(Qt.DashLine)
        pen.setColor(QColor(0, 0, 0, 150))
        pen.setWidth(3)
        pen.setDashOffset(self.setpoint)
        self.qmark1.setLinePen(pen)
        self.qmark1.attach(self.p)

        # plot marker for sense2 - red
        self.qmark2 = QwtPlotMarker()
        self.qmark2.setLineStyle(1)
        self.qmark2.setYValue(11)
        pen = QPen(Qt.DashLine)
        pen.setColor(QColor(255, 0, 0, 150))
        pen.setWidth(3)
        pen.setDashOffset(self.setpoint)
        self.qmark2.setLinePen(pen)
        self.qmark2.attach(self.p)

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
    
        # add widgets for vertical axis scaling yi (y min) ya (y max)
        self.leya = QLineEdit("%.2f"%PLOTYMAX)
        self.leyi = QLineEdit("%.2f"%PLOTYMIN)

        self.leya.setValidator(QDoubleValidator(self.leya))
        self.leyi.setValidator(QDoubleValidator(self.leyi))

        # checkbox for autoscale
        self.cbyautoscale = QCheckBox("set Autoscale for y axis")
        self.cbyautoscale.setCheckState(Qt.Checked)

        # add a button to clear Graph
        self.btncleargraph = QPushButton("Clear graph")
        

            #adjust styles
        self.btncleargraph.setMinimumHeight(70)
        self.setWidgetsMinHeight(30, self.leya, self.leyi)
        self.setWidgetsStyleSheet("border: 2 solid #000;", self.leya, self.leyi)

        # additng widgets to the graph
        wdgtlay.addWidget(QLabel("max y:"), 0, 0)
        wdgtlay.addWidget(QLabel("min y:"), 1, 0)
        wdgtlay.addWidget(self.leya, 0, 1)
        wdgtlay.addWidget(self.leyi, 1, 1)
        wdgtlay.addWidget(self.cbyautoscale, 2, 1)
        wdgtlay.addWidget(self.btncleargraph, 0, 3, 2, 1)
        wdgtlay.setColumnStretch(4, 50)
        
        # process autoscale initialization
        self.processYRescale(self.cbyautoscale.checkState())
        
        # finalize window layout
        templay.addWidget(wdgt, 0, 0)
        templay.addWidget(self.p, 1, 0)
        templay.setRowStretch(1, 50)
        templay.setColumnStretch(0, 50)

        self.setCentralWidget(temp)
        self.setWindowTitle(self.title)

        # sets resets autoscale of Y axis
            # by checkbox
        self.connect(self.cbyautoscale, SIGNAL("stateChanged(int)"), self.processYRescale)
            # manual scale 
        self.connect(self.leya, SIGNAL("editingFinished()"), self.processYRescale)
        self.connect(self.leya, SIGNAL("returnPressed()"), self.processYRescale)
        self.connect(self.leyi, SIGNAL("editingFinished()"), self.processYRescale)
        self.connect(self.leyi, SIGNAL("returnPressed()"), self.processYRescale)

        # clear graph from data points
        self.connect(self.btncleargraph, SIGNAL("clicked()"), self.processClearGraph)
    
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

    #prepare data which will be shown in the Graph 2 channels
    def showData(self, tdict):
        # parse the data for the time limit
        # we need no data older than TIMELIMIT
        with(QMutexLocker(self.datamutex)):
                # add new values - line by line - main storage is in this file
            self.data.update(tdict)
            self.data = dict((k,v) for (k,v) in self.data.iteritems() if k>self._timelimit)

        #split dictionary with data into lists for x and y values
        x = sorted(self.data.keys())

        # remove None values if needed
        xch1 = [k for k in x if self.data[k][0]!=None]
        ch1 = [self.data[k][0] for k in xch1]

        # remove None values if needed
        xch2 = [k for k in x if self.data[k][1]!=None]
        ch2 = [self.data[k][1] for k in xch2]

        visobj = self.p.itemList()   #curves, grid + markers

        #setting values for the curves (0 - grid, 1 & 2 = data)
        visobj[1].setData(xch1, ch1)
        visobj[2].setData(xch2, ch2)

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

    # process rescaling of the graph - autoscale or manual scale for y axis
    def processYRescale(self, value=None):
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

    # clear graph from data points
    def processClearGraph(self):
        visobj = self.p.itemList()   #curves, grid + markers

        #setting values for the curves (0 - grid, 1 & 2 = data)
        visobj[1].setData((), ())
        visobj[2].setData((), ())

        with(QMutexLocker(self.datamutex)):
            self.data = {}

        self.updateUi()
        return

    # update change of set temperature points
    def updateSetPoints(self, *tlist):
        (sense1, sense2) = tlist
        self.qmark1.setYValue(sense1)
        self.qmark2.setYValue(sense2)
        self.updateUi()
        return

    # disable list of controls
    def setWidgetDisabled(self, value, *tlist):
        temp = tlist
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            temp = tlist[0]
        for w in temp:
            w.setDisabled(value)

    # sets widgets stylesheet alignment to a seq. of widgets
    def setWidgetsStyleSheet(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setStyleSheet(value)

    # sets min dimentions to a seq. of widgets
    def setWidgetsMinHeight(self, value, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setMinimumHeight(value)
        

###
## End of TCGraph Object
###

###
## TimeScaleDraw object - for custom labels in the graph window
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

###
## End of TimeScaleDraw Object
###


###
## MPlot object - override typical qplt.Plot autoplot behavior
##
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

###
## End of MPlot Object
###

############################################################################## End of Graph related objects

###
## MQDoubleSpinBox class - overriding default keypress actions
###
class MQDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super(MQDoubleSpinBox, self).__init__(parent)

    def keyPressEvent(self, event):
        if(event.key()==Qt.Key_Return):
            self.emit(SIGNAL("returnPressed(double)"), float(self.value()))
            
        return super(MQDoubleSpinBox, self).keyPressEvent(event)
        

###
## End Of MQDoubleSpinBox
###

###
### Main program loop
###
if __name__ == '__main__':
    print(DISCLAMER)
    app = QApplication(sys.argv)
    form = CryoControl(app)
    app.exec_()

