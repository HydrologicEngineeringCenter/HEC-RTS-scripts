from hec.heclib.dss		import HecDss
from hec.heclib.util	import Heclib
from hec.plugins.usgs	import UsgsControlFrame
from hec.script			import MessageBox
from java.lang			import Exception as JavaException
from javax.swing		import JOptionPane, JScrollPane, JTextArea
from java.awt           import Dimension
from hec2.rts.script	import RTS
from datetime			import datetime
import os, sys, threading

# ---------------------------#
# static global definitions  #
# ---------------------------#
SCRIPT_NAME		= "Get USGS Data"
LOG_FILENAME	   = None
MAX_LOOKBACK_DAYS  = 800
CONFIG_NAME		= "extract_usgs.config"

# ---------------------------#
# utility / output handling  #
# ---------------------------#
def make_fallback_output(script_name, log_filename=None):
	logfile = open(log_filename, "w") if log_filename else None
	output_to_log = bool(logfile)

	def _output(text, level=None, beep=False, acknowledge=False, title=None, log=None):
		if beep:
			print("\a")

		lvl = None if level is None else str(level).upper()
		if (lvl is None) or (lvl == "NONE"):
			prefix = ""
		elif (lvl == "1") or (lvl == "INFO") or (level == 1):
			prefix = "INFO: "
		elif (lvl == "2") or (lvl == "WARNING") or (level == 2):
			prefix = "WARNING: "
		elif (lvl == "3") or (lvl == "ERROR") or (level == 3):
			prefix = "ERROR: "
		else:
			raise ValueError("Invalid level: {0}".format(level))
		if prefix:
			i = 0
			while i < len(text) and text[i].isspace():
				i += 1
			to_output = "{0}{1}{2}".format(text[:i], prefix, text[i:])
		else:
			to_output = text
		print(to_output)
		do_log = output_to_log if log is None else bool(log)
		if logfile and do_log:
			timestr = str(datetime.now())[:-7]
			logfile.write("{0} {1}\n".format(timestr, to_output))
			logfile.flush()
		if acknowledge:
			if not title:
				title = script_name
			if (lvl is None) or (lvl == "NONE") or (lvl == "INFO") or (level == 1) or (level == 0):
				func = MessageBox.showInformation
			elif (lvl == "WARNING") or (level == 2):
				func = MessageBox.showWarning
			else:
				func = MessageBox.showError
			func(text, title)
	return _output

def show_scroll_popup(title, message, width=900, height=500, max_chars=25000):
	try:
		txt = str(message)
	except:
		txt = repr(message)

	if len(txt) > max_chars:
		txt = txt[:max_chars] + "\n\n...(truncated)..."
	ta = JTextArea(txt)
	ta.setEditable(False)
	ta.setLineWrap(True)
	ta.setWrapStyleWord(True)
	ta.setCaretPosition(0)
	sp = JScrollPane(ta)
	sp.setPreferredSize(Dimension(width, height))
	JOptionPane.showMessageDialog(None, sp, title, JOptionPane.INFORMATION_MESSAGE)

def load_kv_config(config_path):
	data = {}
	if (not config_path) or (not os.path.isfile(config_path)):
		return data
	f = None
	try:
		f = open(config_path, "r")
		for raw in f:
			line = raw.strip()
			if (not line) or line.startswith("#"):
				continue
			if "=" not in line:
				continue
			k, v = line.split("=", 1)
			data[k.strip()] = v.strip()
	finally:
		if f:
			f.close()
	return data

def ensure_dss_exists(dss_path):
	dss_dir = os.path.dirname(dss_path)
	if dss_dir and (not os.path.isdir(dss_dir)):
		os.makedirs(dss_dir)
	if not os.path.isfile(dss_path):
		dss = None
		try:
			dss = HecDss.open(dss_path)  # creates file if missing
		finally:
			if dss is not None:
				dss.close()

def get_time_window(frame, cur_module):
	tw = None
	try:
		if cur_module is not None and hasattr(cur_module, "getTimeWindowString"):
			tw = cur_module.getTimeWindowString()
	except:
		tw = None
	if (tw is not None) and (str(tw).strip() != ""):
		return tw
	user_input = JOptionPane.showInputDialog(
		frame,
		"Enter number of days back to retrieve",
		SCRIPT_NAME,
		JOptionPane.QUESTION_MESSAGE
	)
	if user_input is None:
		return None  # canceled
	try:
		lookback_days = int(str(user_input).strip())
	except:
		raise ValueError("Invalid entry for number of days: {0}".format(user_input))
	if lookback_days <= 0:
		raise ValueError("Lookback days must be > 0 (got {0})".format(lookback_days))
	if lookback_days > MAX_LOOKBACK_DAYS:
		raise ValueError("Lookback days exceeds max ({0})".format(MAX_LOOKBACK_DAYS))

	return "T-{0}D, T".format(lookback_days)

##############################
##  environment / globals   ##
##############################
has_cavi = False
has_outputter = False
cavi_frame = None
cur_module = None
watershed = None
proj_dir = None
cwms_home = None
script_dir = None
usgs_filename = None
dss_filename = None
config_path = None
outputter = None

try:
	from usace.cavi.client import CAVI as cCAVI
	has_cavi = True
	cavi_frame = cCAVI.getBrowserFrame()
	cur_module = RTS.getCurrentModule()
	watershed = str(RTS.getWatershed())
	proj_dir = RTS.getWatershed().getProjectDirectory()
	cwms_home = os.path.join(proj_dir, "..", "..")
	script_dir = os.path.join(proj_dir, "shared", "source")
	if script_dir not in sys.path:
		sys.path.append(script_dir)
	# -----------------------------
	# Read paths from config file
	# -----------------------------
	config_path = os.path.join(script_dir, CONFIG_NAME)
	cfg = load_kv_config(config_path)
	usgs_filename = cfg.get("usgs_file", None)
	dss_filename  = cfg.get("dss_file", None)
	if not usgs_filename or not dss_filename:
		MessageBox.showError(
			"Missing required config keys in:\n{0}\n\n"
			"Expected:\n"
			"  usgs_file=<full path to .usgs>\n"
			"  dss_file=<full path to .dss>\n\n"
			"Current values:\n"
			"  usgs_file={1}\n"
			"  dss_file={2}".format(config_path, usgs_filename, dss_filename),
			SCRIPT_NAME
		)
		raise Exception("Config missing usgs_file and/or dss_file")
	# Optional: normalize to absolute paths
	usgs_filename = os.path.abspath(usgs_filename)
	dss_filename  = os.path.abspath(dss_filename)
	# Optional: ensure DSS file exists
	ensure_dss_exists(dss_filename)
	try:
		from MessageOutput import Outputter
		outputter = Outputter()
		has_outputter = True
	except ImportError:
		has_outputter = False
except ImportError:
	has_cavi = False
	has_outputter = False

# Configure output()
if has_outputter:
	outputter.messenger	= cavi_frame
	outputter.level		= "INFO"
	outputter.beep		 = False
	outputter.acknowledge  = False
	outputter.title		= SCRIPT_NAME
	outputter.logmode	  = "w"
	outputter.make_log_dir = False
	outputter.logfile	  = LOG_FILENAME
	output = outputter.output
else:
	output = make_fallback_output(SCRIPT_NAME, LOG_FILENAME)

##########################
##  main work function  ##
##########################
def get_usgs_data():
	if not has_cavi:
		output("This script must be run inside CAVI.", level="ERROR", acknowledge=True)
		return -1

	frame = cavi_frame
	# Validate config-resolved file paths
	if (not usgs_filename) or (not os.path.isfile(usgs_filename)) or os.path.getsize(usgs_filename) == 0:
		output("USGS control file missing or empty:\n{0}".format(usgs_filename),
			   level="ERROR", beep=True, acknowledge=True)
		return -1
	if not dss_filename:
		output("DSS file path not set (check config):\n{0}".format(config_path),
			   level="ERROR", beep=True, acknowledge=True)
		return -1
	# Time window
	try:
		tw = get_time_window(frame, cur_module)
	except ValueError as e:
		output(str(e), level="ERROR", acknowledge=True)
		return -1
	if tw is None:
		output("Script canceled.", level="WARNING")
		return 1
	output("Using time window {0}".format(tw))
	output("Using USGS file {0}".format(usgs_filename))
	output("Using HEC-DSS file {0}".format(dss_filename))

	dssFile = None
	try:
		dssFile = HecDss.open(dss_filename, tw)

		if has_outputter:
			outputter.capture = True
		usgs = UsgsControlFrame(dssFile)
		usgs.loadStations(usgs_filename)
		istat = usgs.retrieveData()
		if istat == 0:
			output("Unable to retrieve data from the USGS.", level="ERROR", beep=True, acknowledge=True)
			return -1
		return 0
	except JavaException as e:
		output("Error during data retrieval: {0}".format(e.getMessage()),
			   level="ERROR", beep=True, acknowledge=True)
		return -1
	finally:
		try:
			if dssFile is not None:
				dssFile.close()
		except:
			pass
		if has_outputter:
			outputter.capture = False

def main():
	Heclib.zset("MLVL", "", 0)
	rc = get_usgs_data()

	if rc == 0:
		output("Done", level="INFO", beep=False, acknowledge=False)

		msg = "USGS download complete.\n\nTime window:\n{0}\n\nUSGS file:\n{1}\n\nDSS file:\n{2}".format(
			getattr(cur_module, "getTimeWindowString", lambda: "N/A")(),
			usgs_filename,
			dss_filename
		)
		show_scroll_popup(SCRIPT_NAME + " - Complete", msg)

	elif rc == 1:
		show_scroll_popup(SCRIPT_NAME + " - Cancelled", "USGS download cancelled by user.")
	else:
		show_scroll_popup(SCRIPT_NAME + " - ERROR", "USGS download failed.\nCheck the console/log output for details.")

if __name__ == "__main__":
	threading.Thread(target=main).start()
