
import vxi11
instr =  vxi11.Instrument("192.168.57.162")
print(instr.ask("*IDN?"))
# returns 'AGILENT TECHNOLOGIES,MSO7104A,MY********,06.16.0001'
