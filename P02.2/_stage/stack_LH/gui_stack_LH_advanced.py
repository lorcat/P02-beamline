#!/usr/bin/env python

import sys
# add modules to the list
sys.path.append("/home/p02user/scripts/")
sys.path.append("/home/p02user/scripts/modules")
# change current working directory to make images available
import os
os.chdir(os.path.dirname(os.path.realpath(__file__)))

from  PyTango import *
import pylab
import numpy
import p3cntr
reload(p3cntr)

from PyQt4.QtCore import *
from PyQt4.QtGui import *

# beamline module - General Purpose table
from gui_beamline_LH import *
from gui_starter_module_LH import *
from gui_counter_module import *
from gui_savepos_module import *


DISCLAMER = """-- full gui for general purpose table --
-- LGPL licence applies - as we use QT library for free --

version 0.2
0.2 improvement - lot's of functionality, only minor debugging
0.1 improvement - basic gui, controls
coding by Konstantin Glazyrin
contact lorcat@gmail.com for questions, comments and suggestions 
"""

# window title
MAINWINDOWTITLE = "Sample stack - Laser Heating Table"

# Global variables, data parameter - thickness, x, y for grid layout
SPSDEVICE = "tango://haspp02oh1:10000/p02/spseh2/eh2a.01"
SPSVALVEDATA = {"GPValve1":[0, 0, 0], "GPValve2":[25, 0, 1], "GPValve3":[25, 1, 1], "GPValve4":[50, 2, 1], 
                "GPValve5":[125, 3, 1], "GPValve6":[0, 1, 2], "GPValve7":[0, 2, 2], "GPValve8":[0, 0, 2]}
(SPSIN, SPSOUT) = (1, 0)

### Motors - easier to edit if needed
  # DETECTOR
(DETECTORX, DETECTORY) = ("haspp02oh1:10000/p02/motor/eh2a.11", "haspp02oh1:10000/p02/motor/eh2a.12")
  # SAMPLE 
(SAMPLEX, SAMPLEY, SAMPLEZ, SAMPLEOMEGA) = ("haspp02oh1:10000/p02/motor/eh2a.09", "haspp02oh1:10000/p02/motor/eh2a.10", "haspp02oh1:10000/p02/motor/eh2a.05", "haspp02oh1:10000/p02/motor/eh2a.06")
  # PINHOLE
(PINHOLEY, PINHOLEZ) = ("haspp02oh1:10000/p02/motor/eh2a.07", "haspp02oh1:10000/p02/motor/eh2a.08")
  # HFM mirror
(HFMCURV, HFMELL, HFMTILT, HFMZ) = ("haspp02oh1:10000/p02/attributemotor/hcurvature", "haspp02oh1:10000/p02/attributemotor/hellipticity", "haspp02oh1:10000/p02/attributemotor/htilt", "haspp02oh1:10000/p02/attributemotor/hzpos")
  # VFM mirror
(VFMCURV, VFMELL, VFMTILT, VFMZ) = ("haspp02oh1:10000/p02/attributemotor/vcurvature", "haspp02oh1:10000/p02/attributemotor/vellipticity", "haspp02oh1:10000/p02/attributemotor/vtilt", "haspp02oh1:10000/p02/attributemotor/vzpos")

### Tab names - may control widget color
(TABSAMPLE, TABDETECTOR, TABPINHOLE, TABSPS, TABHFM, TABVFM, TABGUI) = ("Sample stage", "Detector stage", "Pinhole stack", "SPS (filters, etc.)", "KB Mirror (HFM)", "KB Mirror (VFM)", "Tools (gnuplot, online)")

# colors used in TAB:
(PINHOLECOLOR, SPSCOLOR, HFMCOLOR, VFMCOLOR) = (QColor('pink'), QColor(255,255,200), QColor(170, 255, 170), QColor(100, 255, 100))

#TIMER for SPS
TIMERSPS = 200

# debugging signals
DEVSIGNALERR = "reportError"

# icons used for menu
(ICONBEAMLINE, ICONCOUNTERS, ICONEXPERT, ICONPOSITIONS) = ("beamline_images\\beam.png", "beamline_images\\counter.png", "beamline_images\\expert_mode.png", "beamline_images\\positions.png")

# Application related values
MAPPLICATION = "BeamlineStack"
MDOMAIN = "desy.de"
MORG = "DESY"
MAPPCONFIG = "config/%s.ini" % MAPPLICATION

# configuration file related values


###
# StackForm class - main window of the stack
#
###
class StackForm(QMainWindow):
    def __init__(self, app, parent=None):
        super(StackForm, self).__init__(parent)
        
        self.initVars(app)
        self.initSelf()
        self.initDock()
        self.initToolbar()
        self.initEvents()
    
    # init variables 
    def initVars(self, app):
        # main application
        self._app = app
        self._stype = self._app.style()
        
        # stack widget used for the main movement
        self.stack_widget = None        # p3cntr set of widgets
        self.wsample = None                # tabwidget
        # detector widget
        self.detector_widget = None        # p3cntr set of widgets
        self.wdetector = None            # tabwidget

        # tools widget
        self.gui_widget = None        # p3cntr set of widgets
        self.wgui = None            # tabwidget

        # pinhole widget
        self.pinhole_widget = None        # p3cntr set of widgets
        self.wpinhole = None            # tabwidget
        
        # SPS stack
        self.sps_widgets = SPSVALVEDATA.copy()    # set of widgets, positions, properties for SPS
        self.sps_widget = None            # tabwidget
            # timer for SPS stack
        self._timersps = QTimer()
        self._timersps.setInterval(TIMERSPS)

        # HFM mirror stack
        self.hfm_widget = None          # p3cntr set of widgets
        self.whfm = None                # tabwidget

        # VFM mirror stack
        self.vfm_widget = None          # p3cntr set of widgets
        self.wvfm = None                # tabwidget

        # msavepos module

        return
    
    # init visual
    def initSelf(self):
        # status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self.setWindowTitle(MAINWINDOWTITLE)
        
        # colors
        color = QColor('orange').light()
        pal = QPalette(color)
        self.setPalette(pal)
        
        # icon - icons for windows related to movement are same as the color of the background
        self.createIcon(color)

        # wrapper for tab widget
        self.maintwidget = QWidget()
        tempg = QGridLayout(self.maintwidget)
        
        tab = QTabWidget()
        self._tab = tab

        tempg.addWidget(tab, 1, 0)
        tempg.setRowMinimumHeight(0, 10)    # control spacing above tab widget
        
        # tabs palette
        tabcolor = color
        tabpal = QPalette(tabcolor)
        tabbar = TabBar(tabcolor)
        tab.setTabBar(tabbar) 
        
        # tab with sample stack - updates itself
        self.createSampleStackTab(tab, tabpal)
        
        # tab with detector stack - updates itself
        self.createDetectorStackTab(tab, tabpal)

        # tab with pinhole stack
        tabpal = QPalette(PINHOLECOLOR)
        self.createPinHoleStackTab(tab, tabpal) 
        
        # tab with SPS control stack - updates here
        tabpal = QPalette(SPSCOLOR)
        self.createSPSStackTab(tab, tabpal)

        # tab with gui tools control
        self.createGuiStackTab(tab, tabpal)

        # tab with HFM mirror control
        tabpal = QPalette(HFMCOLOR)
        self.createHFMStackTab(tab, tabpal)

        # tab with VFM mirror control
        tabpal = QPalette(VFMCOLOR)
        self.createVFMStackTab(tab, tabpal)
        
        # show tab as widget
        self.setCentralWidget(self.maintwidget)
        self.show()
        return

    # init special events
    def initEvents(self):
        # update SPS
        self.connect(self._timersps, SIGNAL("timeout()"), self.processUpdateSPS)
        self._timersps.start()

        # assign SPS actions - widget is the last for list in dict of valves
        for k in self.sps_widgets:
            w = self.sps_widgets[k][-1]

            func_callback = lambda dummy="", valv=k: self.processSetSPS(dummy, valv)
            self.connect(w, SIGNAL("toggled(bool)"), func_callback)


        # initialize toolbar actions
            # show / hide beamline
        self.connect(self.ashowbeamline, SIGNAL("toggled(bool)"), self.processShowHideBeamline)
            # show / hide counters
        self.connect(self.ashowcounter, SIGNAL("toggled(bool)"), self.processShowHideCounters)
            # show hide expert mode
        self.connect(self.ashowexpert, SIGNAL("toggled(bool)"), self.processShowHideExpert)
            # show hide positions
        self.connect(self.ashowpositions, SIGNAL("toggled(bool)"), self.processShowHidePositions)

        # check signals emitted by beamline, process them
        self.connect(self.dockbeamwdgt, SIGNAL(BEAMLSIGNALCLICK), self.processBeamLineClick)

        # dock/undock counters widget
        self.connect(self.dockcount, SIGNAL("topLevelChanged(bool)"), self.processCountersFloat)
        # dock/undock positions
        self.connect(self.dockpositions, SIGNAL("topLevelChanged(bool)"), self.processPositionsFloat)

        # update size of main window upon switching between different tabs
        self.connect(self._tab, SIGNAL("currentChanged(int)"), self.processTabSwitch)
        
        # collect reports from positions
        self.connect(self.dockpositionswdgt, SIGNAL(SIGNALMSAVEPOSEXPORT), self.processSavedPosition)
        
        # save current position pass them into positions widget
        self.connect(self.stack_widget, SIGNAL("motorPosition"), self.processSavePosition)
        return

    # initialize menu
    def initToolbar(self):
        tb = QToolBar(self)

        # set pallete, adjust style
        label = QLabel("")
        label.setMinimumWidth(1)
        tb.addWidget(label)
        tb.addWidget(QLabel("Show/hide beamline:  "))
        tb.setAutoFillBackground(True)
        tb.setPalette(QPalette(QColor('orange').light()))
        tb.setFloatable(False)
        tb.setMovable(False)

        # show beamline button
        imgpath = self.checkPath(ICONBEAMLINE)
        self.ashowbeamline = QAction(QIcon(imgpath), "    Show beamline overview", self)
        self.ashowbeamline.setCheckable(True)
        self.ashowbeamline.setChecked(True)
        tb.addAction(self.ashowbeamline)

        # show counters button
        label = QLabel("")
        label.setMinimumWidth(7)
        tb.addWidget(label)
        tb.addWidget(QLabel("Show/hide counters:  "))
        imgpath = self.checkPath(ICONCOUNTERS)
        self.ashowcounter = QAction(QIcon(imgpath), "    Show counters", self)
        tb.addAction(self.ashowcounter)
        self.ashowcounter.setCheckable(True)
        self.ashowcounter.setChecked(False)

        # save positions button
        label = QLabel("")
        label.setMinimumWidth(7)
        tb.addWidget(label)
        tb.addWidget(QLabel("Positions:  "))
        imgpath = self.checkPath(ICONPOSITIONS)
        self.ashowpositions = QAction(QIcon(imgpath), "Show saved positions", self)
        tb.addAction(self.ashowpositions)
        self.ashowpositions.setCheckable(True)
        self.ashowpositions.setChecked(False)
        self.processShowHidePositions(self.ashowpositions.isChecked())

        # expert mode button
        label = QLabel("")
        label.setMinimumWidth(50)
        tb.addWidget(label)
        tb.addWidget(QLabel("Expert mode:  "))
        imgpath = self.checkPath(ICONEXPERT)
        self.ashowexpert = QAction(QIcon(imgpath), "Turn ON/OFF the expert mode", self)
        tb.addAction(self.ashowexpert)
        self.ashowexpert.setCheckable(True)
        self.ashowexpert.setChecked(False)
        self.processShowHideExpert(self.ashowexpert.isChecked())

        self.addToolBar(tb)
        return

    # init toolbar with beamline and counters buttons
    def initDock(self):
        # dock bar with beamline
        self.dockbeamwdgt = MBeamLineGP(self)
        self.dockbeam = QDockWidget(MANBEAMLINE, self)

        w = self.dockbeam
        w.setAutoFillBackground(True)
        w.setPalette(QPalette(QColor(230, 230, 230)))

        w.setAllowedAreas(Qt.TopDockWidgetArea)
        w.setWidget(self.dockbeamwdgt)
        w.setFeatures(QDockWidget.DockWidgetMovable)

        self.addDockWidget(Qt.TopDockWidgetArea, self.dockbeam)

        # dockbar with counters
        self.dockcountwdgt = MCounters(self)
        self.dockcountwdgt.setMinimumHeight(500)
        self.dockcount = QDockWidget(MANCOUNTER, self)

        w = self.dockcount
        w.setAutoFillBackground(True)
        w.setPalette(QPalette(QColor(230, 230, 230)))

        w.setAllowedAreas(Qt.BottomDockWidgetArea)
        w.setWidget(self.dockcountwdgt)
        w.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetVerticalTitleBar)
        w.setFloating(False)
        w.move(self.x()+self.width(), self.y())
        w.hide()

        self.addDockWidget(Qt.BottomDockWidgetArea, self.dockcount)

        # dockbar with positions - initilize
        self.dockpositionswdgt = MSavePos(self._app, MAPPCONFIG)
        self.dockpositions = QDockWidget(MANPOSITIONS, self)
            # adjust style
        w = self.dockpositions
        w.setAutoFillBackground(True)
        w.setPalette(QPalette(QColor(230, 230, 230)))
        w.setAllowedAreas(Qt.TopDockWidgetArea)
        w.setWidget(self.dockpositionswdgt)
        w.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetVerticalTitleBar | QDockWidget.DockWidgetFloatable)
        w.hide()

        self.addDockWidget(Qt.TopDockWidgetArea, self.dockpositions)

        return
    
    # detector stack
    def createDetectorStackTab(self, tab, pal):
        title = TABDETECTOR
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # motors
        det_x = p3cntr.Motor("Detector X LH",
            "detector X LH",
            DETECTORX)

        det_y = p3cntr.Motor("Detector Y LH",
                    "detector Y LH",
                    DETECTORY)
           
        self.detector_widget = p3cntr.ui.MotorWidgetAdvanced([det_x,det_y])
        self.detector_widget.setWindowTitle(TABDETECTOR)

        self.detector_widget.setAutoFillBackground(True)
        self.detector_widget.setPalette(pal)

        grid.addWidget(self.detector_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.wdetector = wdgt

        # update cmb boxes for good steps
        self.detector_widget.setMotorStepsByName("Detector X LH", ["step", 10, 20, 50, 100, 150, 200, 300])
        self.detector_widget.setMotorStepsByName("Detector Y LH", ["step", 10, 20, 50, 100, 150, 200, 300])

        tab.addTab(wdgt, title)
        return

    # tab to start useful things - online+gnuplot 
    def createGuiStackTab(self, tab, pal):
        title = TABGUI
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        self.gui_widget = MGnuplotStarter(self)
        grid.addWidget(self.gui_widget, 0, 0)
        grid.setRowStretch(1, 50)
        grid.setColumnStretch(1, 50)

        self.wgui = wdgt

        tab.addTab(wdgt, title)
        return

    # pinhole stack tab
    def createPinHoleStackTab(self, tab, pal):
        title = TABPINHOLE
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # motors
        pin_y = p3cntr.Motor("Pinhole Y LH",
            "Pinhole Y LH",
            PINHOLEY)

        pin_z = p3cntr.Motor("Pinhole Z LH",
                    "Pinhole Z LH",
                    PINHOLEZ)
           
        self.pinhole_widget = p3cntr.ui.MotorWidgetAdvanced([pin_y, pin_z])

        self.pinhole_widget.setAutoFillBackground(True)
        self.pinhole_widget.setPalette(pal)

        grid.addWidget(self.pinhole_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.wpinhole = wdgt

        tab.addTab(wdgt, title)
        return

    # HFM mirror stack tab
    def createHFMStackTab(self, tab, pal):
        title = TABHFM
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # motors
        hfm_curv = p3cntr.Motor("HFM Curvature LH",
                    "HFM Curvature LH",
                    HFMCURV)
        hfm_ell = p3cntr.Motor("HFM Ellipticity LH",
                    "HFM Ellipticity LH",
                    HFMELL)
        hfm_tilt = p3cntr.Motor("HFM Tilt LH",
                    "HFM Tilt LH",
                    HFMTILT)
        hfm_z = p3cntr.Motor("HFM Z LH",
                    "HFM Z LH",
                    HFMZ)
           
        self.hfm_widget = p3cntr.ui.MotorWidgetAdvanced([hfm_curv, hfm_ell, hfm_tilt, hfm_z])

        self.hfm_widget.setAutoFillBackground(True)
        self.hfm_widget.setPalette(pal)

        grid.addWidget(self.hfm_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.whfm = wdgt

        # update cmb boxes for good steps
        self.hfm_widget.setMotorStepsByName("HFM Curvature LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])
        self.hfm_widget.setMotorStepsByName("HFM Ellipticity LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])
        self.hfm_widget.setMotorStepsByName("HFM Tilt LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])
        self.hfm_widget.setMotorStepsByName("HFM Z LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])

        tab.addTab(wdgt, title)
        return

    # VFM mirror stack tab
    def createVFMStackTab(self, tab, pal):
        title = TABVFM
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # motors
        vfm_cur = p3cntr.Motor("VFM Curvature LH",
                    "VFM Curvature LH",
                    VFMCURV)
        vfm_ell = p3cntr.Motor("VFM Ellipticity LH",
                    "VFM Ellipticity LH",
                    VFMELL)
        vfm_tilt = p3cntr.Motor("VFM Tilt LH",
                    "VFM Tilt LH",
                    VFMTILT)
        vfm_z = p3cntr.Motor("VFM Z LH",
                    "VFM Z LH",
                    VFMZ)
           
        self.vfm_widget = p3cntr.ui.MotorWidgetAdvanced([vfm_cur, vfm_ell, vfm_tilt, vfm_z])

        self.vfm_widget.setAutoFillBackground(True)
        self.vfm_widget.setPalette(pal)

        grid.addWidget(self.vfm_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.wvfm = wdgt

        # update cmb boxes for good steps
        self.vfm_widget.setMotorStepsByName("VFM Curvature LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])
        self.vfm_widget.setMotorStepsByName("VFM Ellipticity LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])
        self.vfm_widget.setMotorStepsByName("VFM Tilt LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])
        self.vfm_widget.setMotorStepsByName("VFM Z LH", ["step", 1, 10, 20, 50, 100, 150, 200, 300, 500])

        tab.addTab(wdgt, title)
        return
    
    # sample stack
    def createSampleStackTab(self, tab, pal):
        title = TABSAMPLE
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # motors
        cenxGP = p3cntr.Motor("CenX LH",
                    "Center X",
                    SAMPLEX)
        cenyGP = p3cntr.Motor("CenY LH",
                    "Center Y",
                    SAMPLEY)
        SamzGP = p3cntr.Motor("SamZ LH",
                    "Sample Z LH",
                    SAMPLEZ)
        omegaGP = p3cntr.Motor("Omega LH",
                "Omega LH",
                SAMPLEOMEGA)
           
        self.stack_widget = p3cntr.ui.MotorWidgetAdvanced([cenxGP,cenyGP,SamzGP,omegaGP])
        self.stack_widget.setWindowTitle(TABSAMPLE)
        self.stack_widget.showBtnSavePos()

        self.stack_widget.setAutoFillBackground(True)
        self.stack_widget.setPalette(pal)

        grid.addWidget(self.stack_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.wsample = wdgt

        tab.addTab(wdgt, title)
        return
    
    def createSPSStackTab(self, tab, pal):
        title = TABSPS
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # fill valve types       
        for k in self.sps_widgets:
           (thickness, tx, ty) = self.sps_widgets[k]
           tw = QWidget()
           tg = QGridLayout(tw)
           
           # fill widget
           thick = ""
           if(thickness!=0):
               thick = " - (%ium)" % thickness
           tcb = QCheckBox("%s%s"%(k, thick))
           tg.addWidget(tcb)
           
           # add widget plus signal
           self.sps_widgets[k].append(tcb)
           
           # add widget to its position
           grid.addWidget(tw, tx, ty)

        #grid.addWidget(QLabel(""), 4, 0)
        grid.setRowStretch(4, 100)
        grid.setColumnStretch(2, 50)

        self.sps_widget = wdgt

        tab.addTab(wdgt, title)
        return
    
    # creates an icon with specific color
    def createIcon(self, color, w=16, h=16):
        pixmap = QPixmap(w, h)
        pixmap.fill(color)
        
        self.setWindowIcon(QIcon(pixmap))
        return

    # update SPS - read list of valves, update gui checkboxes and tab name
    def processUpdateSPS(self):
        devlink = SPSDEVICE

        thickness = 0.0
        for k in SPSVALVEDATA:
            res = self.readWriteDevice(devlink, k)
            res = bool(res)

            w = self.sps_widgets[k][-1]
            if(res != w.isChecked()):
                w.setChecked(res)

            # calculate how thick is the total filter
            if(w.isChecked()):
                thickness += self.sps_widgets[k][0]

        # set tab text reflecting thickness of filter
        string = TABSPS
        if(thickness>0):
            string = "%s - filter (%.0fum)" % (string, thickness)
        index = self._tab.indexOf(self.sps_widget)
        self._tab.setTabText(index, string)
        return

    # process gui actions - clicks on SPS related checkboxes
    def processSetSPS(self, *tlist):
        # stop timer to avoid interference
        self._timersps.stop()

        # set the valve value
        (state, valve) = tlist

        devlink = SPSDEVICE

        state = int(state)
        self.readWriteDevice(devlink, valve, state)
        # restart timer 
        self._timersps.start()

    # check device, it's property, gets value
    def readWriteDevice(self, link, prop, value = None):
        (bsuccess, res) = (True, None)

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

    # process show - hide beamline
    def processShowHideBeamline(self, state):
        if(not state):
            self.dockbeam.hide()
        else:
            if(not self.dockpositions.isHidden()):
                self.ashowpositions.toggle()
            self.dockbeam.show()
        self.maintwidget.adjustSize()
        self.adjustSize()
        return

    # process show - hide beamline
    def processShowHideCounters(self, state):
        if(not state):
            self.dockcount.hide()
        else:
            self.dockcount.show()
        self.maintwidget.adjustSize()
        self.adjustSize()
        return

    # process show - hide expert mode
    def processShowHideExpert(self, state):
        tab = self._tab
        if(not state):
            # remove pinhole tab
            index = tab.indexOf(self.wpinhole)
            if(index>-1):
                tab.removeTab(index)
            # remove HFM mirror tab
            index = tab.indexOf(self.whfm)
            if(index>-1):
                tab.removeTab(index)
            # remove VFM mirror tab
            if(index>-1):
                index = tab.indexOf(self.wvfm)
            tab.removeTab(index)

            # switch to the sample
            index = tab.indexOf(self.wsample)
            if(index>-1):
                tab.setCurrentIndex(index)
        else:
            # show pinhole tab
            index = tab.count()
            tab.insertTab(index, self.wpinhole, TABPINHOLE)
            # show HFM mirror tab
            index = tab.count()
            tab.insertTab(index, self.whfm, TABHFM)
            # show VFM mirror tab
            index = tab.count()
            tab.insertTab(index, self.wvfm, TABVFM)

        # set expert mode for positions widget
        self.dockpositionswdgt.setExpertMode(state)
        # control expert mode in gui tab
        self.gui_widget.setExpertMode(state)
        return

    # process show - hide positions widget
    def processShowHidePositions(self, state):
        if(not state):
            self.dockpositions.hide()
        else:
            if(not self.dockbeam.isHidden()):
                self.ashowbeamline.toggle()
            self.dockpositions.show()

        self.maintwidget.adjustSize()
        self.adjustSize()
        return


    # process click on the element of the beamline, select right tabs or not
    def processBeamLineClick(self, *tlist):
        (string, w) = tlist
        string = QString(string)
        # clicked on detector
        tab = self._tab
        if(string.indexOf(BEAMLDETECTOR)>-1):       # clicked on detector
            index = tab.indexOf(self.wdetector)
            tab.setCurrentIndex(index)
        elif(string.indexOf(BEAMLSAMPLESTAGE)>-1):  # clicked on stage
            index = tab.indexOf(self.wsample)
            tab.setCurrentIndex(index)
        elif(string.indexOf(BEAMLPINHOLE)>-1):      # clicked on pinhole
            index = tab.indexOf(self.wpinhole)
            tab.setCurrentIndex(index)
        elif(string.indexOf(BEAMLSPS)>-1):      # clicked on pinhole
            index = tab.indexOf(self.sps_widget)
            tab.setCurrentIndex(index)
        elif(string.indexOf(BEAMLION1)>-1 or string.indexOf(BEAMLION2)>-1):      # clicked on pinhole
            self.ashowcounter.toggle()
        elif(string.indexOf(BEAMLOPTICS)>-1):
            index = tab.indexOf(self.whfm)
            tab.setCurrentIndex(index)
        return

    # process counters float - adjust window sizes
    def processCountersFloat(self, state):
        self.maintwidget.adjustSize()
        self.adjustSize()

        size = self.size()
        pos = self.pos()

        self.dockcount.resize(400, 500)
        self.dockcount.move(self.x()+size.width(), self.y())

    # process positions float - adjust window sizes
    def processPositionsFloat(self, state):
        self.maintwidget.adjustSize()
        self.adjustSize()

        size = self.size()
        pos = self.pos()

        self.dockcount.resize(180, 400)
        self.dockcount.move(self.x()+size.width(), self.y())

    # process tab switching
    def processTabSwitch(self, index):
        self.maintwidget.adjustSize()
        self.adjustSize()
       
    # process saved position
    def processSavedPosition(self, group, data):
        if(group=="Cells" or group==TABSAMPLE):
            tlist = ("CenX", "CenY", "SamZ", "Omega")
            for name in tlist:
                self.stack_widget.setMotorPositionByName(name, self.checkPositionByName(name, data))
        return
    
    # save current position from sample stack
    def processSavePosition(self, group, positions):
        self.dockpositionswdgt.addExternalData(group, positions)
        return
        
    # process list with values reported by position widget, select specific position
    def checkPositionByName(self, name, tlist):
        res = 0.0
        for i in range(len(tlist)/2):
            label = tlist[2*i]
            value = tlist[2*i+1]
            if(label.find(name)>=0):
                res = value
        return res

    # update combobox with steps
    def updateStepCmb(self, wdgt, *tlist):
        if(type(wdgt) is not QComboBox):
            return
        # clean the QComboBox from other values, except 'step' string
        while(wdgt.count()>1):
            wdgt.removeItem(wdgt.count()-1)

        # add new values
        strlist = QStringList()
        for string in tlist:
            format = "%.3f"
            if(type(string) is str):
                format = "%s"
            string = format%string
            strlist.append(QString(string))
        wdgt.addItems(strlist)

    # check system settings for file paths, convert if on linux
    def checkPath(self, path):
        if(path is not None and sys.platform.find("linux")>-1):
            path = path.replace("\\", "/")
        return path

    # disable/enable widgets in a sequence - for simplicity 
    def setWidgetsDisable(self, flag, *tlist):
        if(type(tlist[0]) is tuple or type(tlist[0]) is list):
            tlist = tlist[0]

        for wdgt in tlist:
            wdgt.setDisabled(flag)
    
    # event on close
    def closeEvent(self, event):
        # stop SPS timer
        if(self._timersps.isActive()):
            self._timersps.stop()

        event.accept()

###
## StackForm END
##
###


###
## class TabBar - for QTabWidget QTabBar ctusomization
## found in http://stackoverflow.com/questions/12901095/change-background-color-of-tabs-in-pyqt4
###
class TabBar(QTabBar):
    def __init__(self, color, parent=None):
        super(TabBar, self).__init__(parent)
        self._color = color
        return

    def paintEvent(self, event):

        painter = QStylePainter(self)
        option = QStyleOptionTab()

        for index in range(self.count()):
            self.initStyleOption(option, index)

            # general color
            bgcolor = self._color

            # color for special tabs
            text = self.tabText(index)
                # SPS
            if(text.indexOf(TABSPS)>-1 or text.indexOf(TABGUI)>-1):
                bgcolor = SPSCOLOR
            elif(text==QString(TABPINHOLE)):        # Pinhole
                bgcolor = PINHOLECOLOR
            elif(text==QString(TABHFM)):        # HFM mirror
                bgcolor = HFMCOLOR
            elif(text==QString(TABVFM)):        # VFM mirror
                bgcolor = VFMCOLOR

            option.palette.setColor(QPalette.Window, bgcolor)
            painter.drawControl(QStyle.CE_TabBarTabShape, option)
            painter.drawControl(QStyle.CE_TabBarTabLabel, option)
###
## class TabBar END
## 
###


#####################################################  Application initialization
if(__name__=="__main__"):
    print(DISCLAMER)
    app = QApplication(sys.argv)

    # set application related features
    app.setOrganizationName(MORG);
    app.setOrganizationDomain(MDOMAIN);
    app.setApplicationName(MAPPLICATION);

    form = StackForm(app)
    app.exec_()
