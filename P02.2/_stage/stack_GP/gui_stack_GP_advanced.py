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
from gui_beamline_GP import *
from gui_starter_module import *
from gui_counter_module import *

DISCLAMER = """-- full gui for general purpose table --
-- LGPL licence applies - as we use QT library for free --

version 0.2
0.2 improvement - lot's of functionality, only minor debugging
0.1 improvement - basic gui, controls
coding by Konstantin Glazyrin
contact lorcat@gmail.com for questions, comments and suggestions 
"""

# window title
MAINWINDOWTITLE = "Sample stack - General purpose table"

# Global variables, data parameter - thickness, x, y for grid layout
SPSDEVICE = "tango://haspp02oh1:10000/p02/spseh2/eh2a.01"
SPSVALVEDATA = {"GPValve1":[0, 0, 0], "GPValve2":[25, 0, 1], "GPValve3":[25, 1, 1], "GPValve4":[50, 2, 1], 
                "GPValve5":[125, 3, 1], "GPValve6":[0, 1, 2], "GPValve7":[0, 2, 2], "GPValve8":[0, 0, 2]}
(SPSIN, SPSOUT) = (1, 0)

### Motors - easier to edit if needed
  # DETECTOR
(DETECTORX, DETECTORY) = ("haspp02oh1:10000/p02/motor/eh2b.39", "haspp02oh1:10000/p02/motor/eh2b.40")
  # SAMPLE 
(SAMPLEX, SAMPLEY, SAMPLEZ, SAMPLEOMEGA) = ("haspp02oh1:10000/p02/motor/eh2b.43", "haspp02oh1:10000/p02/motor/eh2b.42", "haspp02oh1:10000/p02/motor/eh2b.37", "haspp02oh1:10000/p02/motor/eh2b.38")
  # PINHOLE
(PINHOLEY, PINHOLEZ) = ("haspp02oh1:10000/p02/motor/eh2a.59", "haspp02oh1:10000/p02/motor/eh2a.60")
  # HFM mirror
(HFMCURV, HFMELL, HFMTILT, HFMZ) = ("haspp02oh1:10000/p02/attributemotor/hcurvature.gp", "haspp02oh1:10000/p02/attributemotor/hellipticity.gp", "haspp02oh1:10000/p02/attributemotor/htilt.gp", "haspp02oh1:10000/p02/attributemotor/hzpos.gp")
  # VFM mirror
(VFMCURV, VFMELL, VFMTILT, VFMZ) = ("haspp02oh1:10000/p02/attributemotor/vcurvature.gp", "haspp02oh1:10000/p02/attributemotor/vellipticity.gp", "haspp02oh1:10000/p02/attributemotor/vtilt.gp", "haspp02oh1:10000/p02/attributemotor/vzpos.gp")

### Tab names - may control widget color
(TABSAMPLE, TABDETECTOR, TABPINHOLE, TABSPS, TABHFM, TABVFM, TABGUI) = ("Sample stage", "Detector stage", "Pinhole stack", "SPS (filters, etc.)", "KB Mirror (HFM)", "KB Mirror (VFM)", "Tools (gnuplot, online)")

# colors used in TAB:
(PINHOLECOLOR, SPSCOLOR, HFMCOLOR, VFMCOLOR) = (QColor('pink'), QColor('orange').light(), QColor(170, 255, 170), QColor(100, 255, 100))

#TIMER for SPS
TIMERSPS = 200

# debugging signals
DEVSIGNALERR = "reportError"

# icons used for menu
(ICONBEAMLINE, ICONCOUNTERS, ICONEXPERT) = ("beamline_images\\beam.png", "beamline_images\\counter.png", "beamline_images\\expert_mode.png")

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
        self.gui_widget = None        # gui widget control tools child processes start
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

        return
    
    # init visual
    def initSelf(self):
        # status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self.setWindowTitle(MAINWINDOWTITLE)
        
        # colors
        color = QColor('blue').light()
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
        tabcolor = QColor(200, 200, 255)
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
        
        # check exit button and remove it if necessary
        self.removeExitButton(self.detector_widget)
        self.removeExitButton(self.stack_widget)
        self.removeExitButton(self.pinhole_widget)
        self.removeExitButton(self.hfm_widget)
        self.removeExitButton(self.vfm_widget)
        
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

        # check signals emitted by beamline, process them
        self.connect(self.dockbeamwdgt, SIGNAL(BEAMLSIGNALCLICK), self.processBeamLineClick)

        # dock/undock counters widget
        self.connect(self.dockcount, SIGNAL("topLevelChanged(bool)"), self.processCountersFloat)

        # update size of main window upon switching between different tabs
        self.connect(self._tab, SIGNAL("currentChanged(int)"), self.processTabSwitch)
        return

    # initialize menu
    def initToolbar(self):
        tb = QToolBar(self)

        # set pallete, adjust stule
        label = QLabel("")
        label.setMinimumWidth(1)
        tb.addWidget(label)
        tb.addWidget(QLabel("Show/hide beamline:  "))
        tb.setAutoFillBackground(True)
        tb.setPalette(QPalette(QColor(200, 200, 255)))
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
        return
    
    # detector stack
    def createDetectorStackTab(self, tab, pal):
        title = TABDETECTOR
        wdgt = QWidget()
        grid = QGridLayout(wdgt)

        wdgt.setAutoFillBackground(True)
        wdgt.setPalette(pal)

        # motors
        det_x_GP = p3cntr.Motor("Detector X GP",
            "detector X GP",
            DETECTORX)

        det_y_GP = p3cntr.Motor("Detector Y GP",
                    "detector Y GP",
                    DETECTORY)
           
        self.detector_widget = p3cntr.ui.MotorWidget([det_x_GP,det_y_GP])
        self.detector_widget.setWindowTitle('Sample stack GP')

        self.detector_widget.setAutoFillBackground(True)
        self.detector_widget.setPalette(pal)

        grid.addWidget(self.detector_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.wdetector = wdgt

        # update cmb boxes for good steps
        cmbdetx = self.findStepCmbInMotors(self.detector_widget.motordev_widget[0])
        self.updateStepCmb(cmbdetx, 10, 20, 50, 100, 150, 200, 300)

        cmbdety = self.findStepCmbInMotors(self.detector_widget.motordev_widget[1])
        self.updateStepCmb(cmbdety, 10, 20, 50, 100, 150, 200, 300)

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
        pin_y_GP = p3cntr.Motor("Pinhole Y GP",
            "Pinhole Y GP",
            PINHOLEY)

        pin_z_GP = p3cntr.Motor("Pinhole Z GP",
                    "Pinhole Z GP",
                    PINHOLEZ)
           
        self.pinhole_widget = p3cntr.ui.MotorWidget([pin_y_GP, pin_z_GP])

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
        hfm_curv = p3cntr.Motor("HFM Curvature GP",
                    "HFM Curvature GP",
                    HFMCURV)
        hfm_ell = p3cntr.Motor("HFM Ellipticity GP",
                    "HFM Ellipticity GP",
                    HFMELL)
        hfm_tilt = p3cntr.Motor("HFM Tilt GP",
                    "HFM Tilt GP",
                    HFMTILT)
        hfm_z = p3cntr.Motor("HFM Z GP",
                    "HFM Z GP",
                    HFMZ)
           
        self.hfm_widget = p3cntr.ui.MotorWidget([hfm_curv, hfm_ell, hfm_tilt, hfm_z])

        self.hfm_widget.setAutoFillBackground(True)
        self.hfm_widget.setPalette(pal)

        grid.addWidget(self.hfm_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.whfm = wdgt

        # update cmb boxes for good steps
        cmb = self.findStepCmbInMotors(self.hfm_widget.motordev_widget[0])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

        cmb = self.findStepCmbInMotors(self.hfm_widget.motordev_widget[1])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

        cmb = self.findStepCmbInMotors(self.hfm_widget.motordev_widget[2])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

        cmb = self.findStepCmbInMotors(self.hfm_widget.motordev_widget[3])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

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
        vfm_cur = p3cntr.Motor("VFM Curvature GP",
                    "VFM Curvature GP",
                    VFMCURV)
        vfm_ell = p3cntr.Motor("VFM Ellipticity GP",
                    "VFM Ellipticity GP",
                    VFMELL)
        vfm_tilt = p3cntr.Motor("VFM Tilt GP",
                    "VFM Tilt GP",
                    VFMTILT)
        vfm_z = p3cntr.Motor("VFM Z GP",
                    "VFM Z GP",
                    VFMZ)
           
        self.vfm_widget = p3cntr.ui.MotorWidget([vfm_cur, vfm_ell, vfm_tilt, vfm_z])

        self.vfm_widget.setAutoFillBackground(True)
        self.vfm_widget.setPalette(pal)

        grid.addWidget(self.vfm_widget, 0, 0)
        grid.setRowStretch(1, 50)

        self.wvfm = wdgt

        # update cmb boxes for good steps
        cmb = self.findStepCmbInMotors(self.vfm_widget.motordev_widget[0])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

        cmb = self.findStepCmbInMotors(self.vfm_widget.motordev_widget[1])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

        cmb = self.findStepCmbInMotors(self.vfm_widget.motordev_widget[2])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

        cmb = self.findStepCmbInMotors(self.vfm_widget.motordev_widget[3])
        self.updateStepCmb(cmb, 1, 10, 20, 50, 100, 150, 200, 300, 500)

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
        cenxGP = p3cntr.Motor("CenX GP",
                    "Center X",
                    SAMPLEX)
        cenyGP = p3cntr.Motor("CenY GP",
                    "Center Y",
                    SAMPLEY)
        SamzGP = p3cntr.Motor("SamZ GP",
                    "Sample Z GP",
                    SAMPLEZ)
        omegaGP = p3cntr.Motor("Omega GP",
                "Omega GP",
                SAMPLEOMEGA)
           
        self.stack_widget = p3cntr.ui.MotorWidget([cenxGP,cenyGP,SamzGP,omegaGP])
        self.stack_widget.setWindowTitle('Sample stack GP')

        self.stack_widget.setAutoFillBackground(True)
        self.stack_widget.setPalette(pal)

        grid.addWidget(self.stack_widget, 0, 0)

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
    
    # update interface - remove unnecessary exit button,update style for the QPushButton
    def removeExitButton(self, stack):
        for tlist in stack.motordev_widget:
            for w in tlist:
                if(type(w) is QPushButton and w.text().indexOf("Exit")>-1):
                    w.close()
                if(type(w) is not QLabel and type(w) is not QLineEdit):
                    pal = w.style().standardPalette()
                    w.setPalette(pal)
            
    
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

        # control expert mode in gui tab
        self.gui_widget.setExpertMode(state)
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

    # process tab switching
    def processTabSwitch(self, index):
        self.maintwidget.adjustSize()
        self.adjustSize()

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

    # finding cmb object in stack from p3cntr.ui.MotorWidget
    def findStepCmbInMotors(self, tlist):
        wdgt = None
        for w in tlist:
            if(type(w) is QComboBox):
                wdgt = w
        return wdgt

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
    form = StackForm(app)
    app.exec_()
