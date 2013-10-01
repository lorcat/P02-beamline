#!/usr/bin/env python
from __future__ import division
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import os
import sys
import time

from random import gauss

from PyQt4.Qwt5.qplt import *
from PyTango import *


DISCLAMER = """-- gui for measurements - counters --
-- GPL licence applies - as we use QT library for free --

version 0.2
0.2 improvement - assigned nicks for GP table (got my hands to the beamline) 
0.1 improvement - basic gui, tango obejct communication
coding by Konstantin Glazyrin
contact lorcat@gmail.com for questions, comments and suggestions 
"""


BTNSTART = "Start"
BTNSTOP = "Stop"

# in ms - maximal time for which we keep data and show it in the graph screen
TIMELIMIT = 60000

# counters desctiption
counters = [
        {"id": "001", "table": "LH", "timer": "p02/timer/eh2a.01", "vfc": "p02/vfc/eh2a.01", "nick":""},
        {"id": "002", "table": "LH", "timer": "p02/timer/eh2a.01", "vfc": "p02/vfc/eh2a.02", "nick":""},
        {"id": "003", "table": "LH", "timer": "p02/timer/eh2a.01", "vfc": "p02/vfc/eh2a.03", "nick":""},
        {"id": "004", "table": "LH", "timer": "p02/timer/eh2a.01", "vfc": "p02/vfc/eh2a.04", "nick":""},

        {"id": "005", "table": "GP", "timer": "p02/timer/eh2b.01", "vfc": "p02/vfc/eh2b.01", "nick":"ION1"},
        {"id": "006", "table": "GP", "timer": "p02/timer/eh2b.01", "vfc": "p02/vfc/eh2b.02", "nick":"ION2"},
        {"id": "007", "table": "GP", "timer": "p02/timer/eh2b.01", "vfc": "p02/vfc/eh2b.03", "nick":""},
        {"id": "008", "table": "GP", "timer": "p02/timer/eh2b.01", "vfc": "p02/vfc/eh2b.04", "nick":"DIODE"}
    ]

##
## Main window
##

class FormCounters(QMainWindow):
    def __init__(self, app, parent=None):
        super(FormCounters, self).__init__(parent)
        self.app = app

        self.initUI()
        self.initVars()

    
    def initUI(self):
        #background - color
        pal = QPalette()
        self.setAutoFillBackground(True)
        pal.setColor(QPalette.Window, QColor('pink'))
        self.setPalette(pal)

        #size
        self.resize(550, 300)
        self.setWindowTitle("Counters (Adm. tasks)")
        
        #icon
        self.createWindowIcon()

        
        # making tab widget view = for future additions
        tab = QTabWidget(self)
        tab.setPalette(pal)

        # central widget for the counters
        qcntr = QWidget()
        qcntr_lay = QVBoxLayout()

        #top part - selectors
        top = QWidget()
        top_lay = QGridLayout()
        self.cbselcounter = QComboBox()
        self.cbselcounter.setToolTip("Available Counters")
        self.initComboBox()

        label = QLabel("Counter:")
        self.btnstart = QPushButton(BTNSTART)
        self.btnstart.setToolTip("Starts/Stops measurements")
        self.btnclear = QPushButton("Clear")
        self.btnstart.setToolTip("Clears plot from data points")
        
        self.sbtime = QDoubleSpinBox()
        self.sbtime.setRange(0.1, 4)
        self.sbtime.setSuffix("s")
        self.sbtime.setSingleStep(0.1)
        self.sbtime.setValue(.2)

        self.lintensity = QLabel("Intensity will go here")
        self.lintensity.setStyleSheet("border: 2 solid rgb(200,0,0); background-color: rgb(255,255,255)")


        self.initMinHeight((label, self.btnstart, self.cbselcounter, self.lintensity, self.btnclear, self.sbtime), 35)
        self.initMinWidth((self.cbselcounter), 200)

        top_lay.addWidget(label, 0, 0)
        top_lay.addWidget(self.cbselcounter, 0, 1)
        top_lay.addWidget(self.sbtime, 0, 2)
        top_lay.addWidget(self.btnstart, 0, 3)
        top_lay.addWidget(self.btnclear, 0, 4)
        top_lay.addWidget(self.lintensity, 1, 1, 1, 2)

        top_lay.setColumnStretch(1, 50)

        top.setLayout(top_lay)

        #bottom part - graph
        bottom = QWidget()
        bottom_lay = QGridLayout()
        bottom.setLayout(bottom_lay)

        # bottom plot
        self.plot = Plot('', self)
        c1 = self.getCurve('', Circle, Red, 2, Red)
        self.plot.plot(c1)

        self.plot.setAxisScaleDraw(QwtPlot.xBottom, TimeScaleDraw())
        self.plot.zoomers[0].setTrackerMode(QwtPicker.AlwaysOn)
        self.plot.zoomers[0].trackerText = self.modYScaleText


        # plot marker - used with maximum value
        """
        self.qmark = QwtPlotMarker()
        self.qmark.setLineStyle(1)
        self.qmark.setYValue(0)
        pen = QPen(Qt.DashLine)
        pen.setColor(QColor(100, 100, 100, 150))
        pen.setWidth(3)
        pen.setDashOffset(0)
        self.qmark.setLinePen(pen)
        self.qmark.attach(self.plot)"""

        bottom_lay.addWidget(self.plot)


        # setting different part on top of the central widget
        qcntr_lay.addWidget(top)
        qcntr_lay.addWidget(bottom)
        qcntr.setLayout(qcntr_lay)

        # final UI processing
        tab.addTab(qcntr, "Task: counters")
        self.setCentralWidget(tab)

        # status bar
        self.status = self.statusBar()
        self.status.setSizeGripEnabled(False)

        # signals and slots
        self.connect(self.btnstart, SIGNAL("clicked()"), self.btnstart_clicked)
        self.connect(self.btnclear, SIGNAL("clicked()"), self.btnclear_clicked)

        # show window
        self.show()
        return

    # init main window variables 
    def initVars(self):
        self.tango = TangoObject()
        self.thStart = ThreadCounter(self.tango)

        # thread signals
        self.prepareSignals()

        # data to plot
        self.data = {}

        # maximum measured data
        self.maxdata = 0.0
        return

    # prepare main signals - threads
    def prepareSignals(self):
        self.connect(self.thStart, SIGNAL("report"), self.reportData)
        return


    # adding counter items to the combobox
    def initComboBox(self):
        for i in range(0, len(counters)):
            # make string list - pass as data for future processing
            qsl = QStringList()
            qsl.append(counters[i]["timer"])
            qsl.append(counters[i]["vfc"])
            
            string = "%s" % counters[i]["id"]
            if(len(counters[i]["nick"])>0):
                string = "%s" % counters[i]["nick"]
            self.cbselcounter.addItem("          %s\t(%s)\t- %s" %(counters[i]["table"], string, counters[i]["vfc"]), QVariant(qsl))
        return

    # set common height for certain controls
    def initMinHeight(self, tlist, size):
        for w in tlist:
            w.setMinimumHeight(size)
            w.setFont(QFont("Arial",12))
    
    # set common width for certain controls
    def initMinWidth(self, tlist, size):
        temp = tlist
        if(type(tlist) is not list or type(tlist) is not tuple):
            temp = []
            temp.append(tlist)
        for w in temp:
            w.setMinimumWidth(size)

    #disable list of controls
    def setWidgetDisabled(self, *tlist):
        r = tlist
        if(type(tlist[0])==type([]) or type(tlist[0])==type(())):
            r = tlist[0]
        for w in r:
            w.setDisabled(True)

    #enable list of controls
    def setWidgetEnabled(self, *tlist):
        r = tlist
        if(type(tlist[0])==type([]) or type(tlist[0])==type(())):
            r = tlist[0]
        for w in r:
            w.setDisabled(False)

    # start/stop thread, measure
    def btnstart_clicked(self):
        # if thread is running - start state - stop it
        if(self.thStart.isRunning()):
            self.thStart.stop()
            self.thStart.wait()
            self.btnstart.setText(BTNSTART)
            self.setWidgetEnabled(self.cbselcounter)
            return

        self.btnstart.setText(BTNSTOP)
        self.setWidgetDisabled(self.cbselcounter)

        # reinit thread upon finishing as well as signals
        if(self.thStart.isFinished()):
            self.thStart = ThreadCounter(self.tango)
            self.prepareSignals()

        # check given counter - get values from it
        index = self.cbselcounter.currentIndex()
        qsl = self.cbselcounter.itemData(index).toStringList()
        (timer, vfc) = (qsl.first(), qsl.last())
        
        # check timestep
        timestep = self.sbtime.value()

        # run thread - set data in tango, start timer - timer
        self.tango.setData(timer, vfc, timestep)
        self.thStart.start()
        return

    # clearing data points in the graph
    def btnclear_clicked(self):
        self.data = {}
        visobj = self.plot.itemList() #curves, grid + marker

        # set data
        visobj[1].setData([], [])

        self.updateUi()
        return

    # report data from thread
    def reportData(self, string):

        # value read - process it
        strr = "Read value: (%s)"% string
        stri = "Intensity: (%s)"% string
        self.lintensity.setText(stri)

        # date and time functions - to generate timestamp
        datetime = QDateTimeM().currentDateTime()
        date = datetime.date()
        time = datetime.time()
        timestamp = datetime.toMSecsSinceEpoch()

        # set data, process it using timelimit
        value = float(string)
        self.data[timestamp] = value
        self.data = dict((k,v) for (k,v) in self.data.iteritems() if k>timestamp-TIMELIMIT)

        # plotting values 
        visobj = self.plot.itemList() #curves, grid + marker

        # prepare list with data
        x = sorted(self.data.keys())
        y = [self.data[k] for k in x]

        # set data
        visobj[1].setData(x, y)

        #
        if(value>self.maxdata):
            self.maxdata = value
            """self.qmark.setYValue(value)"""

        # update plot
        self.updateUi()

        return

    #visual update
    def updateUi(self):
        #checks zoom event - to prevent certain bugs
        if(self.plot.zoomers[0].zoomRectIndex()==1):
            self.plot.replot()
        else:
           self.plot.clearZoomStack()

    # work with status bar
    def showShortMessage(self, msg):
        self.status.showMessage(msg, 3000)

    # work with status bar
    def showLongMessage(self, msg):
        self.status.showMessage(msg, 10000)

    #prepare curves
    def getCurve(self, label, symb, penc, pens, brushc):
        s = Symbol(symb, brushc)
        s.setSize(10)
        s.setPen(Pen(penc, 2))
        return Curve([], [], Pen(penc,3), s, label)

    # modify text at cursor position - show only vertical coordinate
    def modYScaleText(self, qs):
        qsm = self.plot.canvasMap(QwtPlot.yLeft) #QwtScaleMap to convert values between canvas and real coordinates
        text = QwtText("y: %0.02f"%(qsm.invTransform(qs.y())))
        text.setFont(QFont("Arial", 12, QFont.DemiBold))
        text.setBackgroundBrush(Qt.white)
        return text
   
    # create window icon to distinguish between windows
    def createWindowIcon(self):
        # create pixmap
        pixmap = QPixmap(16,16)
        # fill it
        pixmap.fill(QColor(255,0,0))
        # create icon for window
        icon = QIcon(pixmap)
        # finally set window icon
        self.setWindowIcon(icon)

    # closing window
    def closeEvent(self, event):
        if(self.thStart.isRunning()):
            self.thStart.stop()
            self.thStart.wait()
        event.accept()
        return
     
###-------------------
### End of Main Window object
###-------------------


##
## ThreadCounter - tango communication + main thread
##
class ThreadCounter(QThread):
    def __init__(self, tango, parent=None):
        super(ThreadCounter, self).__init__(parent)
        self.tango = tango

        # stop function
        self.stopped = False
        self.stopmutex = QMutex()
        return

    # stop function to simplify operation
    def stop(self):
        if(not self.stopped):
            with(QMutexLocker(self.stopmutex)):
                self.stopped = True

    # main working loop
    def run(self):
        self.tango.initData()
        # self.tango.initDummy()
        while(not self.stopped):
            res = self.tango.runData()
            # res = self.tango.runDummy()
            self.emit(SIGNAL("report"), res)
            self.msleep(100)
            continue

        self.stop()
        return

###-------------------
### End of ThreadCounter object
###-------------------

##
## TangoObject - main thread
##

class TangoObject(QObject):
    def __init__(self, parent=None):
        super(TangoObject, self).__init__(parent)
        self.timer = None
        self.vfc = None
        self.timestep=None
    
    # set tango device names
    def setData(self, timer, vfc, timestep):
        (self.timer, self.vfc, self.timestep) = (str(timer), str(vfc), float(timestep))

    # setup timer
    def initData(self):
        dev = DeviceProxy(self.timer)
        dev.write_attribute("SampleTime", self.timestep)
        return

    # initDummy // for debugging in absence of access to the Tango device
    def initDummy(self):
        return

    # setup data, measure data
    def runData(self):
        # get devices
        devtimer = DeviceProxy(self.timer)
        devfc = DeviceProxy(self.vfc)

        # reset counter
        devfc.command_inout("Reset") 
        devtimer.command_inout("StartAndWaitForTimer")

        # get counts
        cnt = float(devfc.read_attribute("Counts").value)
        cnt_star =  (cnt-5100000)/10

        # some stupid output
        output = "%0f" % cnt
        for i in range(int(cnt_star)):
            output = output + "*"
        
        devtimer = None
        devfc = None
        return output

    # runDummy // for debugging in absence of access to the Tango device
    def runDummy(self):
        return "%0f"%gauss(20, 2)

###-------------------
### End of TangoObject object
###-------------------


### QDateTimeM object 
### to bring new PyQt functionality absent in the current control machine version
### made a wrapper for immediate currentDateTime access
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
### TimeScaleDraw object - for customization of x axis labels in the graph window
###
class TimeScaleDraw(QwtScaleDraw):
    def __init__(self):
        super(TimeScaleDraw, self).__init__()
        self.font = QFont("Arial", 9, QFont.DemiBold)

    def label(self, v):
        msecs = int(v/1000)
        dt = QDateTime().fromTime_t(msecs);
        time = dt.time()

        res = QwtText("%02i:%02i"%(time.minute(), time.second()))
        res.setFont(self.font)

        return res

###-------------------
### End of TimeScaleDraw Object
###-------------------


if __name__ == '__main__':
    print(DISCLAMER)
    app = QApplication(sys.argv)
    form = FormCounters(app)
    app.exec_()