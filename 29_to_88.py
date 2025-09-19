"""
Modified 09-Apr-2025 to use case-insensitive matching on B and C pathname parts
Modified 19-Sep-2025 to use allow more complex B pathname parts

Mike Perryman
CEIWR-HEC
"""
from com.rma.client import Browser
from hec.heclib.dss import HecDss
from hec.script     import Constants, MessageBox
import os, string, re, time, traceback
progname = None
offset_pattern = re.compile(r"^\s*#(29|LOCAL)-88#(.+?)((?:,|\s)*[+-]\d*\.?\d*)\s*$")
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
		
def getOffsets(filename) :
	'''
	Reads the offsets from the "verticalDatumOffsets.txt" file in the base shared directory
	'''
	if not os.path.isfile(filename) : 
		error("No such file: %s" % filename)
		
	with open(filename, "r") as f : lines = f.read().strip().split("\n")
	offsets = {}
	for line in lines :
		m = offset_pattern.match(line)
		if m:
			datum = m.group(1).strip()
			bPart = m.group(2).strip()
			offset = float(m.group(3).strip())
			offsets.setdefault(bPart.upper(), {})[datum] = offset
	output()
	output("Offsets from %s:" % filename)
	for bPart in sorted(offsets.keys()) :
		for datum in sorted(offsets[bPart].keys()) :
			output("\t%s:\t%s to 88 = %s ft" % (bPart, datum, offsets[bPart][datum]))
	return offsets
	
def applyOffsets(dssfile, offsets) :
	'''
	applies the offsets to the forecast DSS file
	'''
	valueCount = recordCount = skipped = 0
	dss = HecDss.open(dssfile)
	dm = dss.getDataManager()
	dm.createNewCatalog (1)
	try :
		records = {}
		for pn in sorted([p for p in dss.getPathnameList() if p.split("/")[3].upper().startswith("ELEV")]) :
			bPart, cPart = pn.upper().split("/")[2:4]
			if cPart.startswith("ELEV(29)") :
				records.setdefault(bPart, {}).setdefault("29", []).append(pn)
			elif cPart.startswith("ELEV(LOCAL)") :
				records.setdefault(bPart, {}).setdefault("LOCAL", []).append(pn)
			else :
				records.setdefault(bPart, {}).setdefault("NORMAL", []).append(pn)
		if progname == "29_to_88" :
			for bPart in sorted(records.keys()) :
				for datum in ("29", "LOCAL") :
					if records[bPart].has_key(datum) :
						if not offsets.has_key(bPart) or not offsets[bPart].has_key(datum) :
							output("No offset specified for %s for %s to 88, but records exist in forecast DSS file" % (bPart, datum))
							skipped += 1
							continue
						offset = offsets[bPart][datum]
						for pathname in records[bPart][datum] :
							try :
								tsc = dss.get(pathname)
								recordCount += 1
								for i in range(len(tsc.values)) :
									if tsc.values[i] != Constants.UNDEFINED :
										tsc.values[i] += offset
										valueCount += 1
								before = tsc.parameter
								tsc.parameter = tsc.parameter.replace("(%s)" % datum, "")
								after = tsc.parameter
								tsc.fullName = tsc.fullName.replace(before, after)
								output("%s --> %s" % (pathname, tsc.fullName))
								dss.put(tsc)
							except :
								output(traceback.format_exc())
		elif progname == "88_to_29" :
			for bPart in sorted(records.keys()) :
				if records[bPart].has_key("NORMAL") :
					if not offsets.has_key(bPart) :
						output("No offset specified for %s for 88 to 29 or local, but records exist in forecast DSS file" % bPart)
						skipped += 1
						continue
					for pathname in records[bPart]["NORMAL"] :
						for datum in ("29", "LOCAL") :
							if offsets[bPart].has_key(datum) :
								offset = offsets[bPart][datum]
								try :
									tsc = dss.get(pathname)
									recordCount += 1
									for i in range(len(tsc.values)) :
										if tsc.values[i] != Constants.UNDEFINED :
											tsc.values[i] -= offset
											valueCount += 1
									before = tsc.parameter
									tsc.parameter = tsc.parameter + ("(%s)" % datum)
									after = tsc.parameter
									tsc.fullName = tsc.fullName.replace(before, after)
									output("%s --> %s" % (pathname, tsc.fullName))
									dss.put(tsc)
								except :
								    output(traceback.format_exc())
		else :
			error("Unexpected script name: %s" % progname)
			
		return valueCount, recordCount, skipped
		
	finally :
		dss.close()		
	
user     = arg1
progname = arg2
output("===================================")
output("Running at %s" % time.ctime())
output("===================================")
frame    = Browser.getBrowser().getBrowserFrame()
proj     = frame.getCurrentProject()
pane     = frame.getTabbedPane()
tab      = pane.getSelectedComponent()
chktab(tab)
fcst     = tab.getForecast()
chkfcst(fcst)
dssfile  = fcst.getOutDssPath()
shdir    = os.path.join(proj.getProjectDirectory(), "shared")
filename = os.path.join(shdir, "verticalDatumOffsets.txt")
offsets  = getOffsets(filename)
valueCount, recordCount, skipped = applyOffsets(dssfile, offsets)
msg = "Shifted %d values in %d records - %d location(s) skipped" % (valueCount, recordCount, skipped)
output()
output(msg)
MessageBox.showInformation(msg, progname)


