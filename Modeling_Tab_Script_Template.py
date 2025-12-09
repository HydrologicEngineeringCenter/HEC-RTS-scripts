from hec.hecmath            import TimeSeriesMath
from hec.io                 import TimeSeriesContainer
from hec.heclib.dss         import HecDss
from hec.heclib.util        import HecTime, Heclib
from hec.dssgui             import ListSelection
from hec.script             import MessageBox, Constants, Plot, AxisMarker
from com.rma.client         import Browser
def output(msg="") :
	'''
	Output to console log
	'''
	print ("%s : %s" % (progname, msg))
def error(msg) :
	'''
	Outputs an error message and rasies an exception
	'''
	output(msg)
	raise Exception(msg)
	
def chktab(tab) :
	'''
	Checks that the "Modeling" tab is selected
	'''
	if tab.getTabTitle() != "Modeling" : 
		msg = "The Modeling tab must be selected"
		output("ERROR : %s" % msg)
		raise Exception(msg)
	 
def chkfcst(fcst) :
	'''
	Checks that a forecast is open
	'''
	if fcst is None : 
		msg = "A forecast must be open"
		output("ERROR : %s" % msg)
		raise Exception(msg)

## Uncomment this section to add this script to a progranm order 
'''
def computeAlternative(currentAlternative, computeOptions):

	return True # success
'''

try :
	try :
################## Stection-Start ####################################################################
		## This section finds the current forecast.dss file (i.e. active forecast) ##
		frame = Browser.getBrowser().getBrowserFrame()
		proj = frame.getCurrentProject()
		pane = frame.getTabbedPane()
		tab = pane.getSelectedComponent()
		chktab(tab)
		fcst = tab.getForecast()
		chkfcst(fcst)
		
		fcstTimeWindowString = str(fcst.getRunTimeWindow())
		fcstNames = fcst.getForecastRunNames()
		fcstRun = fcst.getForecastRun(fcstNames[0])
		fcstRunKey = fcstRun.getKey()
		dssfile = fcst.getOutDssPath()
        
        ## Open forecast.dss file
		cwmsFile = HecDss.open(dssfile)
        
		## Read active forecast times: start of simulation; forecast time; and end of simulation
		important_times = [ i.strip(' ') for i in fcstTimeWindowString.split(';') ]
		start_time, forecast_time, end_time = important_times[0], important_times[1], important_times[2]
        
		## Set time window for the forecast.dss file.  Swap in start_time, forecast_time, end_time.
		cwmsFile.setTimeWindow(start_time, end_time)
################## Stection-End ######################################################################

################## Stection-Start ####################################################################
        
		## Enter your script in this section	##
		
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
################## Stection-End ######################################################################
	except Exception, e : 
		exc_type, exc_value, exc_traceback = sys.exc_info()
		traceback.print_exception(exc_type, exc_value, exc_traceback, limit=None, file=sys.stdout)
		formatted_lines = traceback.format_exc().splitlines()
		TracebackStr = '\n'.join(formatted_lines)
		MessageBox.showError(TracebackStr, 'Python Error')
	except java.lang.Exception, e : 
		exc_type, exc_value, exc_traceback = sys.exc_info()
		traceback.print_exception(exc_type, exc_value, exc_traceback, limit=None, file=sys.stdout)
		formatted_lines = traceback.format_exc().splitlines()
		TracebackStr = '\n'.join(formatted_lines)
		MessageBox.showError(TracebackStr, 'Java Error')
finally:
	cwmsFile.done()
