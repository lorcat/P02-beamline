#!/bin/env python

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from subprocess import *

# commands and arguments for them in order to start Popen subprocess
GNUPLOTPATH = ["konsole -T Gnuplot --geometry 200x200 -e /bin/gnuplot "]
ONLINEPATH  = ['/usr/bin/xterm -T online -e "/home/experiment/Spectra/bin/gra_main_vme -online -novme -c online_user.xml -tki"']
ONLINEEXPPATH  = ['/usr/bin/xterm -T online -e "/home/experiment/Spectra/bin/gra_main_vme -online -novme -tki"']

# QPushButtons captions
(BTNPROCSTART, BTNPROCSTOP) = ("Start", "Stop")

# label captions
(LABELGNUPLOT, LABELONLINEUSER, LABELONLINEEXPERT) = ("Scans Directory (gnuplot):", "Scans Directory (online/usermode):", "Scans Directory (online/expert):")

# signal for child processes
SIGNPROCFINISHED = "procFinished"

###
## MGnuplotStarter class - starts a subprocess of a gnuplot, online in a given directory
###
class MGnuplotStarter(QWidget):
    def __init__(self, parent=None):
        super(MGnuplotStarter, self).__init__(parent)
        
        self.initVars()
        self.initSelf()
        self.initEvents()

    # initialize variables
    def initVars(self):
        # WorkerProcess QThread instances
            # gnuplot
        self._gnuplot = None
            # online user mode
        self._online = None
            # online expert mode
        self._onlineexp = None

        # is expert mode enabled
        self._bexpert = False
        return

    # initialize gui
    def initSelf(self):
        grid=QGridLayout(self)

        grid.addWidget(QLabel(LABELGNUPLOT), 1, 1)

        # current path
        path = QDir.currentPath()

        # gnuplot
        self.legnupath = QLineEdit(path)
        self.legnupath.setReadOnly(True)
        self.legnupath.setToolTip(path)
        grid.addWidget(self.legnupath, 1, 2)

        self.btngnupath = QToolButton()
        grid.addWidget(self.btngnupath, 1, 3)

        self.btngnustart = QPushButton(BTNPROCSTART)
        grid.addWidget(self.btngnustart, 1, 5)

        # online
        grid.addWidget(QLabel(LABELONLINEUSER), 3, 1)

        self.leonlinepath = QLineEdit(path)
        self.leonlinepath.setReadOnly(True)
        self.leonlinepath.setToolTip(path)
        grid.addWidget(self.leonlinepath, 3, 2)

        self.btnonlinepath = QToolButton()
        grid.addWidget(self.btnonlinepath, 3, 3)

        self.btnonlinestart = QPushButton(BTNPROCSTART)
        grid.addWidget(self.btnonlinestart, 3, 5)

        # online expert
        grid.addWidget(QLabel(LABELONLINEEXPERT), 5, 1)

        self.leonlineexppath = QLineEdit(path)
        self.leonlineexppath.setReadOnly(True)
        self.leonlineexppath.setToolTip(path)
        grid.addWidget(self.leonlineexppath, 5, 2)

        self.btnonlineexppath = QToolButton()
        grid.addWidget(self.btnonlineexppath, 5, 3)

        self.btnonlineexpstart = QPushButton(BTNPROCSTART)
        grid.addWidget(self.btnonlineexpstart, 5, 5)

        self.adjustGridColumnWidth(grid, 10, 0, 4, 6)
        self.adjustGridRowHeight(grid, 10, 0, 2, 4, 6)

        grid.setRowStretch(11, 50)
        grid.setColumnStretch(2, 50)

        # expert mode
        self.setExpertMode(True)

        # set standard palette
        self.setStandardPalette(self.btngnustart, self.btnonlinestart, self.btnonlineexpstart)

        # common tooltips
        self.setWidgetsCommonTooltips("Select Working Directory", self.btngnupath, self.btnonlinepath, self.btnonlineexppath)
        self.setWidgetsCommonTooltips("Start child process", self.btngnustart, self.btnonlinestart, self.btnonlineexpstart)

        # adjust minimum diwth for directories
        self.setWidgetsMinimumWidth(300, self.legnupath, self.leonlinepath, self.leonlineexppath)

        self.show()
        return

    # initialize events and slots
    def initEvents(self):
        # gnuplot path change
        func_callback = lambda wdgt = self.legnupath: self.openFileDialog(wdgt)
        self.connect(self.btngnupath, SIGNAL("clicked()"), func_callback)
        # online path change
        func_callback = lambda wdgt = self.leonlinepath: self.openFileDialog(wdgt)
        self.connect(self.btnonlinepath, SIGNAL("clicked()"), func_callback)
        # online path change
        func_callback = lambda wdgt = self.leonlineexppath: self.openFileDialog(wdgt)
        self.connect(self.btnonlineexppath, SIGNAL("clicked()"), func_callback)
        # bind online paths
        self.connect(self.leonlinepath, SIGNAL("textChanged(const QString&)"), self.leonlineexppath, SLOT("setText(const QString&)"))
        self.connect(self.leonlinepath, SIGNAL("textChanged(const QString&)"), self.leonlineexppath.setToolTip)
        self.connect(self.leonlinepath, SIGNAL("textChanged(const QString&)"), self.legnupath, SLOT("setText(const QString&)"))
        self.connect(self.leonlinepath, SIGNAL("textChanged(const QString&)"), self.legnupath.setToolTip)
        # gnuplot start
        func_callback = lambda wdgt = self.legnupath: self.startSubprocess(wdgt)
        self.connect(self.btngnustart, SIGNAL("clicked()"), func_callback)
        # online start user mode
        func_callback = lambda wdgt = self.leonlinepath: self.startSubprocess(wdgt)
        self.connect(self.btnonlinestart, SIGNAL("clicked()"), func_callback)
        # online start expert mode
        func_callback = lambda wdgt = self.leonlineexppath: self.startSubprocess(wdgt)
        self.connect(self.btnonlineexpstart, SIGNAL("clicked()"), func_callback)
        return

    # reinitialize events for the threads
    def initThreadEvents(self):
        # check if process is finished, after think about expert mode - enabled or not
        if(self._online is not None):
            self.connect(self._online, SIGNAL(SIGNPROCFINISHED), self.processProcFinished)
        if(self._onlineexp is not None):
            self.connect(self._onlineexp, SIGNAL(SIGNPROCFINISHED), self.processProcFinished)

    # adjust QGridLayout gui
    def adjustGridColumnWidth(self, grid, size, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for i in tlist:
            grid.setColumnMinimumWidth(i, size)

    # adjust QGridLayout gui
    def adjustGridRowHeight(self, grid, size, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for i in tlist:
            grid.setRowMinimumHeight(i, size)

    # initiate child processes
    def startSubprocess(self, wdgt):
        path = str(wdgt.text())

        # discriminate between different widgets, control different thread processes
        if(wdgt==self.legnupath):
            if(self._gnuplot is not None and self._gnuplot.isRunning()):
                self._gnuplot.stop()
                self._gnuplot.wait()
                self._gnuplot = None
            else:
                self._gnuplot = WorkerProcess(self.btngnustart, (self.btngnupath), GNUPLOTPATH, path, self)
                self._gnuplot.start()
        elif(wdgt==self.leonlinepath):
            if(self._online is not None and self._online.isRunning()):
                self._online.stop()
                self._online.wait()
                self._online = None
            else:
                self._online = WorkerProcess(self.btnonlinestart, (self.btnonlinepath, self.btnonlineexppath, self.btnonlineexpstart), ONLINEPATH, path, self)
                self.initThreadEvents()
                self._online.start()
        elif(wdgt==self.leonlineexppath):
            if(self._onlineexp is not None and self._onlineexp.isRunning()):
                self._onlineexp.stop()
                self._onlineexp.wait()
                self._onlineexp = None
            else:
                self._onlineexp = WorkerProcess(self.btnonlineexpstart, (self.btnonlinepath, self.btnonlineexppath, self.btnonlinestart), ONLINEEXPPATH, path, self)
                self.initThreadEvents()
                self._onlineexp.start()
        return

    # process end of process, check expert mode
    def processProcFinished(self, *tlist):
        self.setExpertMode(self._bexpert)


    #use dialog to select directories
    def openFileDialog(self, wdgt):
        fdir = wdgt.text()

        currdir = QDir(fdir)

        # select existing path
        fdialog = QFileDialog.getExistingDirectory(self, "Select Working Directory", fdir)
        if(fdialog.length()>0):
            path = fdialog
            wdgt.setText(path)
            wdgt.setToolTip(path)

    # disable certain widgets in a sequence
    def setWidgetsDisable(self, value, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for w in tlist:
            w.setDisabled(value)

    # sets common tooltips
    def setWidgetsCommonTooltips(self, value, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for w in tlist:
            w.setToolTip(value)

    # sets common tooltips
    def setWidgetsMinimumWidth(self, value, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for w in tlist:
            w.setMinimumWidth(value)

    # setup expert mode
    def setExpertMode(self, flag=False):
        self._bexpert = flag
        if(self._bexpert):
            self.setWidgetsDisable(False, self.btnonlineexpstart, self.btnonlineexppath)
        else:
            self.setWidgetsDisable(True, self.btnonlineexpstart, self.btnonlineexppath)

    # update interface - update style for the QPushButton
    def setStandardPalette(self, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for w in tlist:
            if(type(w) is QPushButton):
                pal = w.style().standardPalette()
                w.setPalette(pal)


    # on close
    def closeEvent(self, event):
        # stop relevant process threads
            # gnuplot
        if(self._gnuplot is not None and self._gnuplot.isRunning()):
            self._gnuplot.stop()
            self._gnuplot.wait()
            # online user mode
        if(self._online is not None and self._online.isRunning()):
            self._online.stop()
            self._online.wait()
            # online expert mode
        if(self._onlineexp is not None and self._onlineexp.isRunning()):
            self._onlineexp.stop()
            self._onlineexp.wait()

        event.accept()


###
## WorkerProcess - QThread for controling external processes
###
class WorkerProcess(QThread):
    def __init__(self, wdgtbnt, wdgtlist, proc, cwd=None, parent=None):
        super(WorkerProcess, self).__init__(parent)

        self._bstop = False
        self._qmstop = QMutex()

        self._wdgtlist = wdgtlist
        self._proc = proc
        self._cwd = cwd
        self._btn = wdgtbnt

        self._runproc = None

    # stop thread and child process
    def stop(self):
        with(QMutexLocker(self._qmstop)):
            self._bstop = True
            if(self._runproc is not None and self._runproc.poll()==None):
                self._runproc.terminate()

    # main thread loop
    def run(self):
        print("thread start")
        # disable widgets
        self._bstop = False
        self._btn.setText(BTNPROCSTOP)
        self.setWidgetsDisable(True, self._wdgtlist)

        # start self._runprocess
        self._runproc = Popen(self._proc, stdin=PIPE, stdout=PIPE, cwd=self._cwd, shell=True)

        # loop to keep child self._runprocess alive
        while(not self._bstop and self._runproc.poll()==None):
            # print self._runproc.poll()
            self.msleep(500)

        # check self._runproc termination
        self.stop()
        # enable widgets
        self._btn.setText(BTNPROCSTART)
        self.setWidgetsDisable(False, self._wdgtlist)

        self.emit(SIGNAL(SIGNPROCFINISHED))
        print("thread end")
        return

    # disable certain widgets in a sequence
    def setWidgetsDisable(self, value, *tlist):
        if(type(tlist[0]) is list or type(tlist[0]) is tuple):
            tlist = tlist[0]

        for w in tlist:
            w.setDisabled(value)
        

# start app if started as a script
if(__name__=="__main__"):
    app = QApplication([])
    form = MGnuplotStarter()
    app.exec_()

