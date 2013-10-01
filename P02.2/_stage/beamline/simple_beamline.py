
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from PyTango import *

import sys

# my mouse overload has nothing to do with the thing
# need to implement clicks - check if I can set the cheked state

DISCLAMER = "TEST"


# images - windows format - conversion to linux is done during initialization of individual widgets
(ISHUTTERIN, ISHUTTEROUT) = ( "beamline_images\\shutter_closed.png", "beamline_images\\shutter_open.png")
(IIONCHAMBEROUT, IOPTICSOUT, ISTAGEOUT, IPINHOLEOUT, IDETECTORIN, IXRAYIN) = ( "beamline_images\\ion_chamber.png", "beamline_images\\optics.png", "beamline_images\\stage.png", "beamline_images\\pinhole.png", "beamline_images\\detector.png", "beamline_images\\x-ray.png")
(ISPSIN, ISPSOUT) = ( "beamline_images\\sps_closed.png", "beamline_images\\sps_open.png")
(IDIODEIN, IDIODEOUT) = ( "beamline_images\\diode_closed.png", "beamline_images\\diode_open.png")
(IMICROIN, IMICROOUT) = ( "beamline_images\\microscope_closed.png", "beamline_images\\microscope_open.png")

# identifiers for signals coming beamline widgets
(BEAMLSIGNALTOGGLE, BEAMLSIGNALCLICK) = ("BeamLine toggle", "BeamLine click")
(BEAMLDETECTOR, BEAMLDIODE, BEAMLMICROSCOPE, BEAMLSAMPLESTAGE,
    BEAMLPINHOLE,  BEAMLOPTICS,  BEAMLSHUTTER,  BEAMLION2,  BEAMLION1,  BEAMLSPS, BEAMLXRAY)=( "Detector", "Diode", "Microscope","Sample stage", 
    "Pinhole", "Beamline optics (mirrors)", "Hatch shutter", "Second Ion. Chamber", "First Ion. Chamber", "SPS registers (Pt foil filters)", "X-ray beam")

# devices - register (shutter) and sps (diode) - nick, tango link, property
(NICKSHUTTER, NICKDIODE, NICKMICROSCOPE,
NICKSPSFILTER1, NICKSPSFILTER2, NICKSPSFILTER3, NICKSPSFILTER4) = ("shutter", "diode", "ruby microscope",
                                            "filter1", "filter2", "filter3", "filter4")
DEVICES = {
            NICKSHUTTER: {"nick": BEAMLSHUTTER, "link": "tango://haspp02oh1:10000/p02/register/eh2a.out01", "property": "Value", "in":1, "out":0}, 
            NICKDIODE: {"nick": BEAMLDIODE, "link": "tango://haspp02oh1:10000/p02/spseh2/eh2a.01", "property": "LHValve1", "in": 1, "out": 0},
            NICKMICROSCOPE: {"nick": BEAMLMICROSCOPE, "link": "haspp02oh1:10000/p02/motor/eh2b.47", "property": "Position", "in": -40.0, "out": -80.0},
            NICKSPSFILTER1: {"nick": BEAMLMICROSCOPE, "link": "tango://haspp02oh1:10000/p02/spseh2/eh2a.01", "property": "GPValve2", "in": 1, "out": 0},
            NICKSPSFILTER2: {"nick": BEAMLMICROSCOPE, "link": "tango://haspp02oh1:10000/p02/spseh2/eh2a.01", "property": "GPValve3", "in": 1, "out": 0},
            NICKSPSFILTER3: {"nick": BEAMLMICROSCOPE, "link": "tango://haspp02oh1:10000/p02/spseh2/eh2a.01", "property": "GPValve4", "in": 1, "out": 0},
            NICKSPSFILTER4: {"nick": BEAMLMICROSCOPE, "link": "tango://haspp02oh1:10000/p02/spseh2/eh2a.01", "property": "GPValve5", "in": 1, "out": 0}
          }

# device states
(DEVSHUTTERIN, DEVSHUTTEROUT) = (1, 0)

# timer for beamline widget
TIMERTIMEOUT = 200

# debugging signals
DEVSIGNALERR = "reportError"

# main test form
class MainForm(QMainWindow):
    def __init__(self, app, parent=None):
        super(MainForm, self).__init__(parent)

        self.initVars()
        self.initUI()
        

    def initVars(self):
        self._oldSize = None
        self._wdgt = None
        self._grid = None
        return

    def initUI(self):
        # main widget
        wdgt = QWidget()
        grid = QGridLayout(wdgt)
        grid.setSpacing(0)
        
        # status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self.w = MBeamLineGP()
        grid.addWidget(self.w, 0, 0)

        print(self.w.size())

        # add widget as main
        self.setCentralWidget(wdgt)

        self.show()

        self.connect(self.w, SIGNAL(BEAMLSIGNALTOGGLE), self.showMessage)
        self.connect(self.w, SIGNAL(BEAMLSIGNALCLICK), self.showMessage)


    def showMessage(self, *tmsg):

        (msg, w, state) = (0, 0, 0)

        try:
            (msg, w, state) = tmsg
        except ValueError:
            (msg, w) = tmsg

        checked = w.isChecked()

        print(w.isChecked(), w.isDown())

        msg = "Message: (%s); Checked State: (%i)" %(msg, state)

        print(msg, type(msg))

        if(type(msg) is str or type(msg) is QString or type(msg)==unicode):
            self._status.showMessage(msg, 5000)
        return

    def resizeEvent(self, event):
        event.accept()

###
##  MBeamLineGP class - widget for controlling beamline visualization
###
class MBeamLineGP(QWidget):
    def __init__(self, parent=None):
        super(MBeamLineGP, self).__init__(parent)

        # initialize object
        self.initVars()
        self.initUI()
        self.initEvents()

    # startup events initializer
    def initEvents(self):
        func_callback = lambda dummy="": self.setupBeam(dummy)
        self.connect(self.wsps, SIGNAL("toggled(bool)"), func_callback)
        self.connect(self.wshutter, SIGNAL("toggled(bool)"), func_callback)
        self.connect(self.wdiode, SIGNAL("toggled(bool)"), func_callback)
        self.connect(self.wmicroscope, SIGNAL("toggled(bool)"), func_callback)

        # setup reporting which element has been toggled
        self.setWidgetsReportSignalToggle(self.wdiode, self.wshutter)
        # setup reporting which element has been clicked
        self.setWidgetsReportSignalClicked(self.wdetector, self.wstage, self.wion1, self.wion2, self.wsps, self.woptics, self.wxray, self.wmicroscope, self.wpinhole)

        # catch signals from beamline widgets and process them
        self.connect(self, SIGNAL(BEAMLSIGNALTOGGLE), self.processToggle)

        # timer
        self.connect(self._timer, SIGNAL("timeout()"), self.updateBeamline)
        self._timer.start()
        return

    # startup init variables
    def initVars(self):
        #
        self._oldSize = None

        # 
        self._timer = QTimer(self)
        self._timer.setInterval(TIMERTIMEOUT)
        return

    # startup init UI
    def initUI(self):
        # main widget
        wdgt = self
        grid = QGridLayout(wdgt)
        grid.setSpacing(0)
    

        # beamline setup
        self.wshutter = MImageButton(ISHUTTEROUT, ISHUTTERIN)
        self.wion1 = MImageButton(IIONCHAMBEROUT)
        self.wion2 = MImageButton(IIONCHAMBEROUT)
        self.woptics = MImageButton(IOPTICSOUT)
        self.wsps = MImageButton(ISPSOUT, ISPSIN)
        self.wstage = MImageButton(ISTAGEOUT)
        self.wpinhole = MImageButton(IPINHOLEOUT)
        self.wdiode = MImageButton(IDIODEOUT, IDIODEIN)
        self.wdetector = MImageButton(None, IDETECTORIN)
        self.wxray = MImageButton(IXRAYIN)
        self.wmicroscope = MImageButton(IMICROOUT, IMICROIN)

        # small adjustments
            # force transparent
        self.wsps.forceTransparent()

            # disable user mouseevents
        self.wsps.enableMouseClick(False)
        self.wmicroscope.enableMouseClick(False)
        self.wsps.setChecked(True)

        # making layout
        self._beamline = [self.wdetector, self.wdiode, self.wmicroscope, self.wstage, self.wpinhole,self.woptics, self.wshutter, self.wion2, self.wion1, self.wsps, self.wxray]
        count = 0
        for w in self._beamline:
            w.isTransparent(True)
            grid.addWidget(w, 0, count)
            count += 1

        self._beamline.reverse()
        self.setupBeam(self._beamline)

        # set widgets tooltips
        self.setWidgetsTooltips(
            (self.wdetector, BEAMLDETECTOR),
            (self.wdiode, BEAMLDIODE),
            (self.wmicroscope, BEAMLMICROSCOPE), 
            (self.wstage, BEAMLSAMPLESTAGE),
            (self.wpinhole, BEAMLPINHOLE),
            (self.woptics, BEAMLOPTICS),
            (self.wshutter, BEAMLSHUTTER),
            (self.wion2, BEAMLION2),
            (self.wion1, BEAMLION1),
            (self.wsps, BEAMLSPS),
            (self.wxray, BEAMLXRAY)
            )

        grid.setColumnStretch(grid.columnCount()+1, 50)

        self.adjustSize()
        self.show()

    # sets relations between different objects and passing X-ray beam
    def setupBeam(self, *tlist):
        btransparent = True
        bbeam = True

        for w in self._beamline:
            bbeam = w.isTransparent(bbeam)

    # update view for the beamline
    def updateBeamline(self):

        # update shutter
        device = DEVICES[NICKSHUTTER]
        res = self.readWriteDevice(device)
        if(res==device["in"]):
            res = True
        elif(res==device["out"]):
            res = False
        self.controlShutter(res)

        # update diode
        device = DEVICES[NICKDIODE]
        res = self.readWriteDevice(device)
        if(res==device["in"]):
            res = True
        elif(res==device["out"]):
            res = False
        self.controlDiode(res)

        # update microscope
        device = DEVICES[NICKMICROSCOPE]
        res = self.readWriteDevice(device)
        print(self.wdiode.isEnabled())
        if(res>device["in"]):
            res = True
        elif(res<device["out"]):
            res = False
        self.controlMicroscope(res)

        # update SPS - filters - check 4 of them - put sps in if any filter is in
        device = DEVICES[NICKSPSFILTER1]
        res = self.readWriteDevice(device)
        tres = res
        if(res==device["in"]):
            tres = True
        elif(res==device["out"]):
            tres = False
        
        device = DEVICES[NICKSPSFILTER2]
        res = self.readWriteDevice(device)
        if(res==device["in"]):
            tres = True | tres
        elif(res==device["out"]):
            tres = False | tres

        device = DEVICES[NICKSPSFILTER3]
        res = self.readWriteDevice(device)
        if(res==device["in"]):
            tres = True | tres
        elif(res==device["out"]):
            tres = False | tres

        device = DEVICES[NICKSPSFILTER4]
        res = self.readWriteDevice(device)
        if(res==device["in"]):
            tres = True | tres
        elif(res==device["out"]):
            tres = False | tres

        self.controlSPS(tres)

        return

    # check device, it's property, gets value
    def readWriteDevice(self, devlist, value = None):
        (bsuccess, res) = (True, None)

        (nick, link, prop) = (devlist["nick"], devlist["link"], devlist["property"])

        try: 
            dev = DeviceProxy(link)
        except DevFailed:
            bsuccess = False
        except DevError:
            bsuccess = False

        # writing if needed
        if(bsuccess and value is not None):
            try:
                dev.write_attribute(prop, value)
            except DevFailed:
                bsuccess = False
            except DevError:
                bsuccess = False
        
        # reading
        if(bsuccess):                 
            try:
                res = dev.read_attribute(prop).value
            except DevFailed:
                bsuccess = False
            except DevError:
                bsuccess = False

        if(not bsuccess):
            self.emit(SIGNAL(DEVSIGNALERR), link)

        return res


    # set sequence of widgets to their tooltips
    def setWidgetsTooltips(self, *tlist):
        for (w,tooltip) in tlist:
            w.setToolTip(tooltip)

    # set sequence reporting which widget has been clicked
    def setWidgetsReportSignalToggle(self, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for w in tlist:
            tooltip = w.toolTip()
            func_callback = lambda dummy="", signal=BEAMLSIGNALTOGGLE, what=tooltip, widget=w: self.prepSignalToggle(dummy, signal, what, widget)
            self.connect(w, SIGNAL("toggled(bool)"), func_callback)
        return

    # set sequence reporting which widget has been clicked
    def setWidgetsReportSignalClicked(self, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for w in tlist:
            tooltip = w.toolTip()
            func_callback = lambda signal=BEAMLSIGNALCLICK, what=tooltip, widget=w: self.prepSignalClick(signal, what, widget)
            self.connect(w, SIGNAL("clicked()"), func_callback)
        return

    # prepare beamline widget signal for toggle
    def prepSignalToggle(self, *tlist):
        (state, signal, tooltip, wdgt) = tlist
        self.emit(SIGNAL(signal), tooltip, wdgt, state)
        return

    # prepare beamline widget signal for click
    def prepSignalClick(self, *tlist):
        (signal, tooltip, wdgt) = tlist
        self.emit(SIGNAL(signal), tooltip, wdgt)
        return

    # set widget to a state
    def controlWidget(self, w, value = None):
        if(value is not None and w.isChecked() != value):
            w.setChecked(value)
        w.update()
        return w.isChecked()

    # control shutter
    def controlShutter(self, value = None):
        return self.controlWidget(self.wshutter, value)

    # control diode
    def controlDiode(self, value = None):
        return self.controlWidget(self.wdiode, value)

    # control SPS
    def controlSPS(self, value = None):
        return self.controlWidget(self.wsps, value)

    # control Microscope
    def controlMicroscope(self, value = None):
        if(type(value) is bool and value==self.wdiode.isEnabled()):
            self.wdiode.setEnabled(not value)
        return self.controlWidget(self.wmicroscope, value)

    # process toggle events
    def processToggle(self, *tlist):
        (bmlnick, wdgt, state) = tlist

        # process shutter state change
        device = DEVICES[NICKSHUTTER]
        if(wdgt==self.wshutter):
            value = device["in"]
            if(not state):
                value = device["out"]
            res = self.readWriteDevice(device)
            if(res!=value):
                self.readWriteDevice(device, value)

        # process diode state change
        device = DEVICES[NICKDIODE]
        if(wdgt==self.wdiode):
            value = device["in"]
            if(not state):
                value = device["out"]
            res = self.readWriteDevice(device)
            if(res!=value):
                self.readWriteDevice(device, value)
        return

    # cleanup on close
    def closeEvent(self, event):
        if(self._timer.isActive()):
            self._timer.stop()
        event.accept()


### MImageButton specific constants
MISTATEIN = 1
MISTATEOUT = 2
MISTATEVARIABLE = MISTATEIN | MISTATEOUT

###
## MImageButton clas - Graphical 2 state button, initialization - checked or not checked, if there is only one image - always out of the beam
###
class MImageButton(QToolButton):
    def __init__(self, imgout=None, imgin=None ,parent=None):
        super(MImageButton, self).__init__(parent)

        # image path
        self._imginpath = self.checkPath(imgin)
        self._imgoutpath = self.checkPath(imgout)

        # images
        self._imgin = None
        self._imgout = None

        # stat options
        self._workstate = 0

        # set incoming beam flag
        self._setbeam = False

        # forcing transparent 
        self._transparent = False

        # enable - disable mouse events
        self._clickable = True

        # init basic things
        self.initSelf()
        # process images
        self.initImages()

    # establish basic properties
    def initSelf(self):
        # basic adjustment - make the button checkable by default 
        self.setAutoFillBackground(True)
        self.setPalette(QPalette(QColor('pink')))
        self.setAutoRaise(False)
        return

    # open files, load images
    def initImages(self):
        # check state, load image if needed
        if(self._imginpath is not None):
            self._imgin = QImage(self._imginpath)
            self._workstate = self._workstate | MISTATEIN

        # check state, load image in needed
        if(self._imgoutpath is not None):
            self._imgout = QImage(self._imgoutpath)
            self._workstate = self._workstate | MISTATEOUT

        if(self._workstate==MISTATEVARIABLE):
            self.setCheckable(True)
            self.setChecked(False)

        # set size of widget - non resizable, check which image is not None
        image = self._imgin
        if(self._imgin is None):
            image = self._imgout

        self.setMinimumSize(image.size())
        self.setMaximumSize(image.size())

        return

    # check system settings for file paths, convert if on linux
    def checkPath(self, path):
        if(path is not None and sys.platform.find("linux")>-1):
            path = path.replace("\\", "/")
        return path

    # paint event, paint device, paint beam
    def paintEvent(self, event):
        # check various things before painting
            # checked state
        instate = self.isChecked()
            # draw rect, size
        rect = self.rect()
        size = self.size()

            # image type - check class type and decide - in, out or in/out class
        image = self._imgout
        if(instate):
            image = self._imgin
        elif(image is None):
            image = self._imgin

        # decision how to draw the beam
        (pstart, pend) = (QPoint(0, size.height()/2), QPoint(size.width(), size.height()/2))
        (pen) = (QPen(QBrush(QColor(255, 0, 0)), 7))
        if(self._setbeam):
            if((instate or self._workstate==MISTATEIN) and not self._transparent):
                pstart.setX(size.width()/2)

        # quick drawing
        painter = QPainter()
        painter.begin(self)
        
        if(self._setbeam):
            painter.setPen(pen)
            painter.drawLine(pstart.x(), pstart.y(), pend.x(), pend.y())

        painter.drawImage(rect, image)

        painter.end()

    # check how transparent is the state
    def isTransparent(self, beamin=False):
        bstatus = True & beamin
        instate = self.isChecked()
        if(((self._workstate==MISTATEVARIABLE and instate) or self._workstate == MISTATEIN) and not self._transparent):   # can change state and it is checked (in) now and not forced as a tranparent
            bstatus = False

        self._setbeam = beamin
        self.update()

        return bstatus

    # force in state to be transparent for the beam
    def forceTransparent(self):
        self._transparent = True
        return

    # control mouse events to establish - which widget may change on mouse click and which not
    def mousePressEvent(self, event):
        if(self._clickable):    
            # enable click events by employing super class
            super(MImageButton, self).mousePressEvent(event)
            event.accept()
        else:
            event.ignore()

    # enable - disable mouse events
    def enableMouseClick(self, enable=True):
        self._clickable = enable
        return

###
## MImageButton end
###


###
### Main program loop
###
if __name__ == '__main__':
    print(DISCLAMER)
    app = QApplication(sys.argv)
    # form = MainForm(app)
    form = MBeamLineGP()
    app.exec_()