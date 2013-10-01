#!/bin/env python

import sys
from PyQt4 import QtGui,QtCore
import PyTango
import matplotlib
import functools
import time

from copy import deepcopy

import p3cntr
reload(p3cntr)

#
DISCLAMER = """-- module to control motors (a rewrite of original MotorWidget for better control and expansibility) --
-- LGPL licence applies - as we use QT library for free --

version 0.2
0.2 improvement - complete rewrite to use python dictionary to access motors and widgets in a better way
0.1 improvement - better gui and control
coding by Konstantin Glazyrin
contact lorcat@gmail.com for questions, comments and suggestions 
"""

# template for motor dictionary - for correct copy - deep copy is required
MOTORWIDGETTEMPLATE = {"Template": 
                        {
                        "Number": 0,
                        "Motor": None, 
                        "Widgets": {"Label": None, "Position": None, "LSLeft": None, "SSLeft": None, "SSRight": None, "LSRight": None, "StepsLabel":None, "Step": None, "Steps": None}, 
                        "Position": 0.0001,
                        "Step": 0.0001,
                        "LowLimit": 0.,
                        "UpLimit": 0.,
                        "SStepMult": 1.,     # multiplier small step
                        "LStepMult": 10.     # multiplier large step
                        }
                       }

# MotorWidget timer update 
MOTORTIMER = 250

###
## Motor_QPushButton, Motor_QLineEditPosition, Motor_QLineEditStep, Motor_QComboBoxStep - override default sizes or styles
###
class Motor_QPushButton(QtGui.QPushButton):
    def sizeHint(self):
        return QtCore.QSize(30,24)

class Motor_QLineEditPosition(QtGui.QLineEdit):
    def sizeHint(self):
        return QtCore.QSize(150, 24)

class Motor_QLineEditStep(QtGui.QLineEdit):
    def sizeHint(self):
        return QtCore.QSize(70, 24)

class Motor_QComboBoxSteps(QtGui.QComboBox):
    def sizeHint(self):
        return QtCore.QSize(50, 24)
###
## End Of override for Motor_QPushButton, Motor_QLineEditPosition, Motor_QLineEditStep, Motor_QComboBoxStep
###

###
## MotorWidget - control widget with a set of motors
###

class MotorWidgetAdvanced(QtGui.QWidget):
    def __init__(self, device_list, parent=None, interval=200,
                 button_rel_actions=None, button_abs_actions=None):
        super(MotorWidgetAdvanced,self).__init__(parent)

        # init variables
        self.initVars(device_list, button_rel_actions, button_abs_actions)
        # init interface, init secondary events for each buttons, field etc.
        self.initSelf()
        # init main events
        self.initEvents()

        # start gui update
        self._mainTimer.start()
        return

    # init most important variables
    def initVars(self, device_list, button_rel_actions, button_abs_actions):
        
        # reference to motors passed for initialization
        self._motors = device_list

        # dictionary containing motors, widgets, values
        self._motorsdict = {}

        # create dictionary for each motor, fill the attributes of the dictionary
        # makes it easier for the next step - creation of widgets
        for i, m in enumerate(self._motors):
            # copy template
            template = MOTORWIDGETTEMPLATE["Template"]
            name = m.name

            # fill some motor information
            self._motorsdict[name] = deepcopy(template)         # deep copy is required for correct template creation
                # number of motor, used for future enumeration and sorting
            self._motorsdict[name]["Number"] = i
                # motor object reference
            self._motorsdict[name]["Motor"] = m             # reference to a motor itself
                # low limit, uplimit
            self._motorsdict[name]["LowLimit"] = m.lolim
            self._motorsdict[name]["UpLimit"] = m.uplim
                # from previous code - default step, should be adjusted by gui
            self._motorsdict[name]["Step"] = abs(m.lolim-m.uplim)/10000
                # position
            self._motorsdict[name]["Position"] = m.pos

        # timer to update ui
        self._mainTimer = QtCore.QTimer(self)
        self._mainTimer.setInterval(MOTORTIMER)
        return

    # init gui
    def initSelf(self):
        # grid layout
        grid = QtGui.QGridLayout(self)

        # enumerate entries to motor dict
        items = self._motorsdict.items()
        for row, m in enumerate(sorted(items, key=lambda k: k[1]["Number"])):
            (name, motor) = m

            # setup a list of widgets to be added
            tlist = self.createMotorWidget(name, motor)
            # place widgets on the grid
            self.gridAddWidgetList(grid, row, tlist)
            # init motor events
            self.initMotorEvents(name, motor)

        # add new widget
        self.btnStopMotors = QtGui.QPushButton("&Stop all Motors")
        tlist = [None, None, None, self.btnStopMotors]
        self.gridAddWidgetList(grid, grid.rowCount(), tlist)

        # set stretch
        grid.setRowStretch(grid.rowCount()+1, 50)
        grid.setColumnStretch(grid.columnCount()+1, 50)
        return

    # init basic events
    def initEvents(self):
        # stop all motors button
        self.connect(self.btnStopMotors, QtCore.SIGNAL("clicked()"), self.processStopMotors)
        # main timer
        self.connect(self._mainTimer, QtCore.SIGNAL("timeout()"), self.updateUI)
        return

    # init different button events for specific motor
    def initMotorEvents(self, name, motor):
        # buttons and steps cmb for each motor
        (wlsright, wssright, wlsleft, wssleft, wcmbsteps, wstep, wpos) = (
                                            self._motorsdict[name]["Widgets"]["LSRight"],
                                            self._motorsdict[name]["Widgets"]["SSRight"],
                                            self._motorsdict[name]["Widgets"]["LSLeft"],
                                            self._motorsdict[name]["Widgets"]["SSLeft"],
                                            self._motorsdict[name]["Widgets"]["Steps"],
                                            self._motorsdict[name]["Widgets"]["Step"],
                                            self._motorsdict[name]["Widgets"]["Position"]
                                            )

        # name, vector of movement, flag for large or small step
            # large left
        func_callback = lambda n=name, vector=-1, blargestep=True: self.relativeMovement(name, vector, blargestep)
        self.connect(wlsleft, QtCore.SIGNAL("clicked()"), func_callback)
            # small left
        func_callback = lambda n=name, vector=-1, blargestep=False: self.relativeMovement(name, vector, blargestep)
        self.connect(wssleft, QtCore.SIGNAL("clicked()"), func_callback)
            # small right
        func_callback = lambda n=name, vector=1, blargestep=False: self.relativeMovement(name, vector, blargestep)
        self.connect(wssright, QtCore.SIGNAL("clicked()"), func_callback)
            # large right
        func_callback = lambda n=name, vector=1, blargestep=True: self.relativeMovement(name, vector, blargestep)
        self.connect(wlsright, QtCore.SIGNAL("clicked()"), func_callback)

        # combobox with steps
        func_callback = lambda dummy="", n=name: self.processStepSelection(dummy, name)
        self.connect(wcmbsteps, QtCore.SIGNAL("currentIndexChanged(const QString&)"), func_callback)

        # edit boxes - change style (font weight) on editing
            # for step - editing
        func_callback = lambda dummy="", w=wstep, bbold=True: self.processTextEditing(dummy, w, bbold)
        self.connect(wstep, QtCore.SIGNAL("textEdited(const QString&)"), func_callback)
            # returnPressed or editingFinished reset the font weight for step
        func_callback = lambda dummy="", w=wstep, bbold=False: self.processTextEditing(dummy, w, bbold)
        self.connect(wstep, QtCore.SIGNAL("returnPressed()"), func_callback)
        self.connect(wstep, QtCore.SIGNAL("editingFinished()"), func_callback)
            # for position - editing
        func_callback = lambda dummy="", w=wpos, bbold=True: self.processTextEditing(dummy, w, bbold)
        self.connect(wpos, QtCore.SIGNAL("textEdited(const QString&)"), func_callback)
            # returnPressed
        func_callback = lambda dummy="", w=wpos, bbold=False: self.processTextEditing(dummy, w, bbold)
        self.connect(wpos, QtCore.SIGNAL("returnPressed()"), func_callback)

        # edit boxes - creating new values
            # new step value
        func_callback = lambda n=name, w=wstep: self.processNewStep(n, w)
        self.connect(wstep, QtCore.SIGNAL("editingFinished()"), func_callback)
        self.connect(wstep, QtCore.SIGNAL("returnPressed()"), func_callback)
            # new position value
        func_callback = lambda n=name, w=wpos: self.processNewPosition(n, w)
        self.connect(wpos, QtCore.SIGNAL("returnPressed()"), func_callback)
        return

    # create row widget with controls
    def createMotorWidget(self, name, motor):
        # wdgt list used for later in grid placing
        wdgtlist = []

        # motor properties upon initialization
        (pos, lolim, uplim, step) = self.getMotorProperties(motor, "Position", "LowLimit", "UpLimit", "Step")

        # label with name, initialize widget, adjust style, add to motors dict, add to list for future placement
        key = "Label"
        value = "%s :" % name
        w = QtGui.QLabel(value)
            # adjust font
        font = w.font()
        font.setBold(True)
        w.setFont(font)
            # add tooltip
        tooltip = "Motor: %s; Low limit: (%.04f); Upper Limit: (%.04f)" % (name, lolim, uplim)
        w.setToolTip(tooltip)
            #
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        # button with large step
        key = "LSLeft"
        w = Motor_QPushButton("<<")
        self._motorsdict[name]["Widgets"][key] = w
        w.setToolTip("%s"%str(w))
        wdgtlist.append(w)

        # button small step
        key = "SSLeft"
        w = Motor_QPushButton("<")
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        # position field
        key = "Position"
        value = "0.0000"
        try:
            value = "%.04f" % float(pos)
        except ValueError:
            print "Error: ValueError in MotorWidgetAdvanced.createMotorWidget()"
        w = Motor_QLineEditPosition(value)
        w.setValidator(QtGui.QDoubleValidator(w))
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        # button small step
        key = "SSRight"
        w = Motor_QPushButton(">")
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        # button with large step
        key = "LSRight"
        w = Motor_QPushButton(">>")
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        # step label field
        key = "StepsLabel"
        w = QtGui.QLabel("Step:")
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        # step combobox
        key = "Step"
        w = Motor_QLineEditStep("")
        wstep = w                       # to have possibility to update first step
            # set Validator to positive numbers
        val = QtGui.QDoubleValidator(w)
        val.setBottom(0)
        w.setValidator(val)
            #
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        # steps selector
        key = "Steps"
        w = Motor_QComboBoxSteps()
        self.setMotorCmbSteps(w)
            # update step to first step of initialization
        value = w.itemText(1)
        wstep.setText(value)
            # update current step to the motor dict value
        try:
            step = float(value)
        except ValueError:
            print("Error: ValueError in MotorWidgetAdvanced.createMotorWidget()")
        
        self._motorsdict[name]["Step"] = step
            # 
        self._motorsdict[name]["Widgets"][key] = w
        wdgtlist.append(w)

        return wdgtlist

    # place widgets upon the list entries for a certain grid, certain row
    def gridAddWidgetList(self, grid, row, tlist):
        for col, w in enumerate(tlist):
            if(w is not None and type(w) is not str):
                grid.addWidget(w, row, col)
        return

    # sets specific steps to combobox of choice
    def setMotorCmbSteps(self, wcmb, tlist=None):
        # prep default list of steps
        if(tlist is None):
            tlist = ["step",0.001, 0.002, 0.005, 0.010, 0.020, 0.050, 0.100, 1]

        # prepare string values of steps, depending on type
        strlist = QtCore.QStringList()
        for item in tlist:
            format = "%.03f"
            t = type(item)
            if(t is str):
                format = "%s"
            elif(t is float and item>=1.):
                format = "%.f"
            elif(t is int):
                format = "%i"
            string = format % item
            strlist.append(QtCore.QString(string))
        # add steps to the combobox
        wcmb.clear()
        wcmb.addItems(strlist)
        return


    # return list of motor(dict) property values from keys
    def getMotorProperties(self, motor, *tlist):
        t = type(tlist[0])
        temp = []
        if(t is tuple or t is list):
            tlist = tlist[0]

        for p in tlist:
            value = None
            try:
                value = motor[p]
            except KeyError:
                print("Error: KeyError in MotorWidgetAdvanced.getMotorProperties()")
            temp.append(value)
        return temp
        
    # perform a relative movement - button based
    def relativeMovement(self, name, vector, blargestep):
        # find current step
        (motor, step, stepmult)= (self._motorsdict[name]["Motor"], self._motorsdict[name]["Step"], self._motorsdict[name]["SStepMult"])
        # find step multiplicator
        
        if(blargestep):
            stepmult = self._motorsdict[name]["LStepMult"]

        # calculate new position and move to it
        self.absoluteMovement(motor, motor.pos + vector*step*stepmult)
        return

    # perform absolute movement - all movements go throught this function
    def absoluteMovement(self, motor, newpos):
        motor.pos = newpos
        return

    # stop all motors
    def processStopMotors(self):
        for k in self._motorsdict.keys():
            self._motorsdict[k]["Motor"]._proxy.StopMove()
        return

    # process selection of step - change step in motors(dict) + gui elements
    def processStepSelection(self, *tlist):
        # get new value and name for motor
        (strvalue, name) = tlist
        # get widgets responsible
        (wcmb, wstep) = (self._motorsdict[name]["Widgets"]["Steps"], self._motorsdict[name]["Widgets"]["Step"])

        # index is >0, should be float value provided, otherwise programmer is stupid
        if(wcmb.currentIndex()>0):
            # synchronize values
            wstep.setText(strvalue)
            wcmb.setCurrentIndex(0)
            # set step for motor
            try:
                self._motorsdict[name]["Step"] = float(strvalue)
            except ValueError:
                print("Error: Value error in MotorWidgetAdvanced.processStepSelection()")
        return

    # adjust font editing
    def processTextEditing(self, *tlist):
        (string, w, bbold) = tlist
        font = w.font()
        font.setBold(bbold)
        w.setFont(font)
        return

    # process new step value
    def processNewStep(self, name, wdgt):
        # value length check - do nothing if length is 0
        text = str(wdgt.text())
        if(len(text)==0):
            return

        # set step
        step = 0.00
        try:
            step = float(text)
        except ValueError:
            print("Error: Value error in MotorWidgetAdvanced.processNewStep()")

        self._motorsdict[name]["Step"] = step
        return

    # process new position
    def processNewPosition(self, name, wdgt):
        # value length check - do nothing if length is 0
        text = str(wdgt.text())
        if(len(text)==0):
            return

        position = 0.00
        try:
            position = float(text)
            # movement occurs only if float conversion was successful
            motor = self._motorsdict[name]["Motor"]
            self.absoluteMovement(motor, position)
        except ValueError:
            print("Error: Value error in MotorWidgetAdvanced.processNewPosition()")
        return

    # update UI on timer
    def updateUI(self):
        # enumerate motors, update their positions into position widget
        for name in self._motorsdict.keys():
            (motor, wpos, oldpos) = (self._motorsdict[name]["Motor"], self._motorsdict[name]["Widgets"]["Position"], self._motorsdict[name]["Position"])
            # update if positions have changed
            # read current from motor
            pos = motor.pos
            if(pos != oldpos):
                # update widget
                wpos.setText("%.04f" % motor.pos)
                # update motors(dict) set new position
                self._motorsdict[name]["Position"] = pos

    #
    # utility functions - enable disable, set positions
    #

    # disable - enable certain rows of widgets; enable, disable widgets by row numbers
    def setWidgetRowsDisabledByNum(self, value, *tlist):
        # tlist - enable, disable widgets by row numbers
        t = type(tlist[0])
        if(t is tuple or t is list):
            tlist = tlist[0]

        # use row number as criterion
        for name in self._motorsdict.keys():
            number = self._motorsdict[name]["Number"]
            try:
                # try exception
                tlist.index(number)
                # found
                wdgtlist = self._motorsdict[name]["Widgets"]
                self.setWidgetsDisabled(value, tlist)
            except ValueError:
                # not found
                continue

    # disable - enable certain rows of widgets; enable, disable widgets by names of motors (CENX, etc)
    def setWidgetRowsDisabledByName(self, value, *tlist):
        # tlist - enable, disable widgets by motor name
        t = type(tlist[0])
        if(t is tuple or t is list):
            tlist = tlist[0]

        # use name as criterion
        for name in self._motorsdict.keys():
            try:
                # try exception
                tlist.index(name)
                # found
                wdgtlist = self._motorsdict[name]["Widgets"]
                self.setWidgetsDisabled(value, tlist)
            except ValueError:
                # not found
                continue

    # set motor position by row number
    def setMotorPositionByNumber(self, extnumber, value):
        # use row number as criterion
        for name in self._motorsdict.keys():
            number = self._motorsdict[name]["Number"]
            # found
            if(number == extnumber):
                (pos, format) = (0.0, "%.04f")
                try:
                    pos = float(value)
                except ValueError:
                    print("Error: Value error in MotorWidgetAdvanced.setMotorPositionByRowNumber()")

                # set position as a text in the widget
                strpos = format % pos
                wdgtpos = self._motorsdict[name]["Widgets"]["Position"]
                self.processTextEditing("", wdgtpos, True)
                wdgtpos.setText(strpos)
                # do not set position in the real world, na-ha, user must press Enter
                    # exit loop
                break
        return

    # set motor position by name
    def setMotorPositionByName(self, extname, value):
        # use motor name as criterion
        for name in self._motorsdict.keys():
            # found
            if(name==extname): 
                (pos, format) = (0.0, "%.04f")
                try:
                    pos = float(value)
                except ValueError:
                    print("Error: Value error in MotorWidgetAdvanced.setMotorPositionByName()")
                # set position as a text in the widget
                strpos = format % pos
                wdgtpos = self._motorsdict[name]["Widgets"]["Position"]
                self.processTextEditing("", wdgtpos, True)
                wdgtpos.setText(strpos)
                # do not set position in the real world, na-ha, user must press Enter
                    # exit loop
                break
        return

    # set steps for motor by name
    def setMotorStepsByNumber(self, extnumber, tlist=None):
        # use motor name as criterion
        for name in self._motorsdict.keys():
            number = self._motorsdict[name]["Number"]
            # found
            if(number == extnumber):
                wdgtcmb = self._motorsdict[name]["Widgets"]["Steps"]
                self.setMotorCmbSteps(wdgtcmb, tlist)
                # do not set position in the real world, na-ha, user must press Enter
                    # exit loop
                break
        return

    # set steps for motor by row number
    def setMotorStepsByName(self, extname, tlist=None):
        # use motor name as criterion
        for name in self._motorsdict.keys():
            # found
            if(name==extname):
                wdgtcmb = self._motorsdict[name]["Widgets"]["Steps"]
                self.setMotorCmbSteps(wdgtcmb, tlist)
                # do not set position in the real world, na-ha, user must press Enter
                    # exit loop
                break
        return

    # enable, disable set of widgets at once
    def setWidgetsDisabled(self, value, *tlist):
        t = type(tlist[0])
        if(t is tuple or t is list):
            tlist = tlist[0]        

        for w in tlist:
            w.setDisabled(value)

    # cleanup on close
    def closeEvent(self, event):
        # cleanup timer
        if(self._mainTimer.isActive()):
            self._mainTimer.stop()

        event.accept()


###
## End Of MotorWidget
###

# test initialization and run
if __name__ == '__main__':
    app = QtGui.QApplication([])
    print(DISCLAMER)

    # motor positions
    (SAMPLEX, SAMPLEY, SAMPLEZ, SAMPLEOMEGA) = ("haspp02oh1:10000/p02/motor/eh2a.09", "haspp02oh1:10000/p02/motor/eh2a.10", "haspp02oh1:10000/p02/motor/eh2a.05", "haspp02oh1:10000/p02/motor/eh2a.06")
    # set motor description
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
    
    # create MotorWidget
    stack_widget = MotorWidgetAdvanced([cenxGP,cenyGP,SamzGP,omegaGP])

    # show motor widget and start QApplication loop
    stack_widget.show()
    app.exec_()