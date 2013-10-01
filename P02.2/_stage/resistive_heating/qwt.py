import sys
import numpy as np
from PyQt4.Qt import *
from PyQt4.Qwt5 import *
from PyQt4.Qwt5.qplt import *

import sys
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from random import gauss


class Dialog(QDialog):
    
    def __init__(self):
        super(Dialog, self).__init__()    
        
        self.p = None
        self.initUI()
        
        self.thread = Runner(self.p)
        self.thread.start()
        
        self.connect(self.thread, SIGNAL("replot"), self.p.replot)
        
    def initUI(self):         

        x = np.arange(-2*np.pi, 2*np.pi, 0.01)
        y = np.cos(x)
        
        
        symb = Symbol(Circle, Red)
        symb.setSize(10)
        symb.setPen(Pen(Black, 2))
        c1 = Curve(x, y, Pen(Red,3), symb, 'cos(x)')
        
        self.p = Plot(
            c1,
            'PyQwt ', self)

        self.p.setAxisScaleDraw(QwtPlot.xBottom, TimeScaleDraw())

       
        l=QVBoxLayout()
        l.addWidget(self.p)
        self.setLayout(l)
        self.setWindowTitle("Qwt?")
        
        self.show()
    
    def closeEvent(self, event):
        if(self.thread.isRunning()):
            self.thread.stop()
            self.thread.wait()
        QMainWindow().closeEvent(event)
        
class Runner(QThread):
    def __init__(self, plot, parent=None):
        super(Runner, self).__init__(parent)
        self.mstop = QMutex()
        self.fstop = True
        self.counter = 0.0
        self.plot = plot        
        
        self.datax = []
        self.datay = []
    
    def run(self):
        while(self.fstop):
            print("Thread Counter %i" % (self.counter))
            self.counter += 1
            
            self.datax.append(self.counter)
            self.datay.append(gauss(10,.5))
            
            if(len(self.datax)>10):
                self.datax = self.datax[-10:]
                self.datay = self.datay[-10:]
            
            print("%f\t%f"%(self.plot.itemList()[-1].data().xData()[-1], self.plot.itemList()[-1].data().yData()[-1]))
            
            a= self.plot.itemList()[-1].setData(self.datax, self.datay)
            
            self.emit(SIGNAL("replot"))

            self.msleep(100)
        
        self.stop()
    
    def stop(self):
        if(not self.fstop):
            return
        with(QMutexLocker(self.mstop)):
            self.fstop = False
        return

class TimeScaleDraw(QwtScaleDraw):
    def __init__(self):
        super(TimeScaleDraw, self).__init__()

    def label(self, v):
        print("->%f"%v)
        return QwtText("%03.f"%v)

        
def main():
    app = QApplication(sys.argv)
    ex = Dialog()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()