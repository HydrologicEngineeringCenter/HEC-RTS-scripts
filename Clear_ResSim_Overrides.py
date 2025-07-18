from	hec.script		import	Plot
from	hec.script		import	MessageBox
#from hec.io import TimeSeriesContainer
#from hec.io import PairedDataContainer
#from hec.hecmath import TimeSeriesMath
#from hec.hecmath import PairedDataMath
from	hec.heclib.dss	import	HecDss, DSSPathname
from	com.rma.client	import	Browser
from	javax.swing		import	JOptionPane
import datetime, time, calendar, inspect, java, os, sys, traceback, math, shutil, logging, getpass, hec, wcds

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
	
try :
	try :
		
################## Stection-Start ####################################################################
		
		def	clearOverrides(dssFile,pathname):
			#dssFile.setTimeWindow(forecast_time, end_time)
			tsc = dssFile.get(pathname)
			for i in range(len(tsc.values)):
				tsc.values[i] = -3.4028234663852886E38
			dssFile.put(tsc)
			
		def	clearOverrideList(dssFile,pathnameList):
			for p in pathnameList:
				clearOverrides(dssFile,p)
			
		##	Get the current forecast ##
		frame = Browser.getBrowser().getBrowserFrame()
		proj = frame.getCurrentProject()
		pane = frame.getTabbedPane()
		tab = pane.getSelectedComponent()
		chktab(tab)
		fcst = tab.getForecast()
		chkfcst(fcst)
		dssfile = fcst.getOutDssPath()
		fcstTimeWindowString = str(fcst.getRunTimeWindow())
		
		## print 'fcstTimeWindowString : %s' %(fcstTimeWindowString)
		important_times = [ i.strip(' ') for i in fcstTimeWindowString.split(';') ]
		start_time, forecast_time, end_time = important_times[0], important_times[1], important_times[2]
		
		## Define forecast directory
		dssFileName = fcst.getForecastDSSFilename()
		forecastDirectory = str(os.path.dirname(dssFileName))
		
		## Find first ResSim in selected forecast run alternative
		ActiveFcst = tab.getActiveForecastRun()
		ActiveAlts = ActiveFcst.getModelAlternatives("ResSim")
		print ActiveAlts
		No_ActiveRSSAlts = len(ActiveAlts)
		if No_ActiveRSSAlts > 1:
			SelectedRSSAlt = JOptionPane.showInputDialog(None,"Select ResSim Alternative","ResSim Alternative",JOptionPane.PLAIN_MESSAGE,None,ActiveAlts,ActiveAlts[0])
			ActiveRSSAlt = SelectedRSSAlt
			ActiveRSSAlt_Fpart = ActiveRSSAlt.getFpart()
		else:
			ActiveRSSAlt = ActiveAlts.get(0)
			ActiveRSSAlt_Fpart = ActiveRSSAlt.getFpart()
			
		print("ResSim F-part: "+ActiveRSSAlt_Fpart)
		
		##	Open ResSim override dss file for selected forecast run alternative
		OverrideFile_osDir = os.path.join(forecastDirectory,'rss', ActiveRSSAlt_Fpart)
		OverrideFile_Dir = OverrideFile_osDir.replace("\\", "/")
		OverrideFile = HecDss.open(OverrideFile_Dir)
		OverrideList = OverrideFile.getCondensedCatalog()
		print OverrideList

		##	Create a list for the JOptionPane dialog
		CleanOverrideList = ["Clear All Override Sets"]
		for p in OverrideList:
			parts = str(p).split("/")
			parts[4] = ""
			p = "/".join(parts)
			CleanOverrideList.append(p)
		
		##	JOptionPane for selecting which Overrides to have cleared.  
		SelectedOverride = JOptionPane.showInputDialog(None,"Select Override","Override",JOptionPane.PLAIN_MESSAGE,None,CleanOverrideList,CleanOverrideList[0])
		print SelectedOverride
		
		if SelectedOverride == None:
			MessageBox.showInformation("No Overrides selected.", "ResSim Overrides")
		
		elif SelectedOverride == "Clear All Override Sets":
			clearOverrideList(OverrideFile,CleanOverrideList[1:])
			
			#ActiveFcst.computeModel(ActiveRSSAlt,1)
			
			MessageBox.showInformation("<html>All ResSim overrides have been cleared.<li>"
				"Compute ResSim from the CAVI before computing in OSI.</html>", "ResSim Overrides")
		
		else:
			OverridePath = str(SelectedOverride)
			clearOverrides(OverrideFile,OverridePath)
			
			#ActiveFcst.computeModel(ActiveRSSAlt,1)
			
			MessageBox.showInformation("<html>Selected ResSim override has been cleared.<li>"
				"Compute ResSim from the CAVI before computing in OSI.</html>", "ResSim Overrides")
		
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
	OverrideFile.done()
