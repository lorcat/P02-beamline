from PyQt4.QtCore import *

# to bring new PyQt functionality - make wrapper
class QDateTimeM(QDateTime):
    def __init__(self, parent=None):
        super(QDateTimeM, self).__init__(QDateTime().currentDateTime())

    def toMSecsSinceEpoch(self):
	    time = self.time()
	    return int((float(self.toTime_t())+float(time.msec())/1000)*1000)
 

if __name__=='__main__':
	qdt = QDateTimeM()
	print(qdt.toMSecsSinceEpoch())
