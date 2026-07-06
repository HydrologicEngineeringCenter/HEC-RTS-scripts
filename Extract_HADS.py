# Read extract_hads.config (hads_file + dss_file), then:
# - read the .hads list (GOES_ID + DSS_PATH blocks)
# - fetch DecodedData (pipe format)
# - parse into time series by SHEF code
# - store to DSS using DSS_PATH as a base.
#
# Includes:
# - lookback-days prompt
# - end-of-run popup dialog with wrapped, scrollable log (also used for cancel/error)

from __future__ import print_function
from javax.swing import JOptionPane, JScrollPane, JTextArea
from java.awt import Dimension
from java.net import URL
from java.io import BufferedReader, InputStreamReader
from hec.heclib.dss import HecDss
from hec.io import TimeSeriesContainer
from hec.heclib.util import HecTime
from hec2.rts.script import RTS
from java.net import SocketTimeoutException
import os, sys, time

BASE = "https://hads.ncep.noaa.gov/nexhads2/servlet/DecodedData"
WATERSHED_NAME = str(RTS.getWatershed())

SHEF_MAP = {
	"HG": ("Stage", "ft"),
	"HG2": ("Stage-bkup", "ft"),
	"QR": ("Flow", "cfs"),
	"PC": ("Precip", "in"),
	"VB": ("Battery", "v"),
	"SD": ("Snow Depth", "in"),
	"TA": ("Air Temp", "F"),
	"TW": ("Water Temp", "F"),
	"WS": ("Wind Speed", "fps"),
	"WT": ("Turbidity", "ppm"),
	# add more as you encounter them...
}

def safe_strip(s):
	try:
		return s.strip() if s is not None else ""
	except:
		try:
			return str(s).strip()
		except:
			return ""


def dms_parts_to_decimal(dms, is_lon=False):
	"""
	Convert 'DD MM SS.S' (no hemisphere letters) to decimal degrees.
	Examples:
	  LAT='38 23 30.2'  ->  38.391722...
	  LON='090 38 16.1' -> -90.637805...  (assumed West)
	Args:
	  dms: string like 'DD MM SS.S'
	  is_lon: if True, result is negated (assume West)
	"""
	s = safe_strip(dms)
	if not s:
		return None

	toks = s.split()
	if len(toks) < 2:
		return None

	try:
		deg = float(toks[0])
		minu = float(toks[1])
		sec = float(toks[2]) if len(toks) >= 3 else 0.0
	except:
		return None

	dd = abs(deg) + (minu / 60.0) + (sec / 3600.0)
	if is_lon:
		dd = -dd
	return dd


def show_log_popup(title, lines, width=900, height=600, max_chars=25000):
	txt = "\n".join(lines)
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


def default_extract_hads_config_path():
	# <projectDir>/shared/source/extract_hads.config
	try:
		proj_dir = RTS.getWatershed().getProjectDirectory()
		return os.path.join(proj_dir, "shared", "source", "extract_hads.config")
	except:
		return os.path.join(os.getcwd(), "extract_hads.config")


def prompt_lookback_days(default_days=2, max_days=7):
	msg = "Enter number of days back to retrieve (1-{0}):".format(max_days)
	user_input = JOptionPane.showInputDialog(None, msg, str(default_days))
	if user_input is None:
		return None
	try:
		days = int(str(user_input).strip())
	except:
		JOptionPane.showMessageDialog(None, "Invalid number: {0}".format(user_input))
		return None
	if days < 1 or days > max_days:
		JOptionPane.showMessageDialog(None, "Days must be between 1 and {0}.".format(max_days))
		return None
	return days


def fetch_text_java(url_string, connect_timeout_ms=60000, read_timeout_ms=180000, retries=3, backoff_seconds=5, log=None):
	last_ex = None
	for attempt in range(1, retries + 1):
		try:
			u = URL(url_string)
			conn = u.openConnection()
			conn.setRequestProperty("User-Agent", "JythonJavaURLConnection/1.0")
			conn.setConnectTimeout(connect_timeout_ms)
			conn.setReadTimeout(read_timeout_ms)
			charset = "UTF-8"
			try:
				ctype = conn.getContentType()
				if ctype and "charset=" in ctype.lower():
					charset = ctype.split("charset=")[-1].split(";")[0].strip()
			except:
				pass
			br = BufferedReader(InputStreamReader(conn.getInputStream(), charset))
			lines = []
			line = br.readLine()
			while line is not None:
				lines.append(line)
				line = br.readLine()
			br.close()
			return u"\n".join(lines) + u"\n"
		except SocketTimeoutException as ex:
			last_ex = ex
			msg = "Timeout reading URL (attempt %d/%d). Waiting %ds then retrying..." % (attempt, retries, backoff_seconds)
			print(msg)
			if log is not None:
				log.append(msg)
			try:
				time.sleep(backoff_seconds)
			except:
				pass
		except Exception as ex:
			last_ex = ex
			msg = "Error fetching URL (attempt %d/%d): %s" % (attempt, retries, ex)
			print(msg)
			if log is not None:
				log.append(msg)
			try:
				time.sleep(backoff_seconds)
			except:
				pass

	raise last_ex


def read_extract_hads_config(config_path):
	data = {
		"version": "",
		"hads_file": "",
		"dss_file": "",
	}
	if not config_path or not os.path.isfile(config_path):
		return data
	f = None
	try:
		f = open(config_path, "rb")
		for raw in f:
			try:
				line = raw.decode("utf-8", "replace")
			except:
				line = raw
			line = safe_strip(line)
			if not line or line.startswith("#"):
				continue
			if "=" not in line:
				continue
			k, v = line.split("=", 1)
			k = safe_strip(k).lower()
			v = safe_strip(v)
			if k in data:
				data[k] = v
	finally:
		if f:
			f.close()
	return data


def read_hads_sites(hads_list_path):
	sites = []
	current = {}
	required = ["GOES_ID", "DSS_PATH"]

	def finalize_block():
		if not current:
			return
		missing = [k for k in required if not safe_strip(current.get(k, ""))]
		if missing:
			return
		lat_raw = safe_strip(current.get("LAT", ""))
		lon_raw = safe_strip(current.get("LON", ""))
		sites.append({
			"cfg_nws_id": safe_strip(current.get("NWS_ID", "")),
			"usgs_id":    safe_strip(current.get("USGS_ID", "")),
			"goes_id":    safe_strip(current.get("GOES_ID", "")).upper(),
			"hsa":        safe_strip(current.get("HSA", "")),
			"lat":        lat_raw,
			"lon":        lon_raw,
			"lat_dd":     dms_parts_to_decimal(lat_raw, is_lon=False),
			"lon_dd":     dms_parts_to_decimal(lon_raw, is_lon=True),  # assume West
			"name":       safe_strip(current.get("NAME", "")),
			"dss_base":   safe_strip(current.get("DSS_PATH", "")),
		})
	f = None
	try:
		f = open(hads_list_path, "rb")
		for raw in f:
			try:
				line = raw.decode("utf-8", "replace")
			except:
				line = raw
			line = safe_strip(line)
			if not line:
				finalize_block()
				current = {}
				continue
			if line.startswith("#"):
				continue
			if "=" not in line:
				continue
			k, v = line.split("=", 1)
			current[safe_strip(k).upper()] = safe_strip(v)
		finalize_block()
	finally:
		if f:
			f.close()
	return sites


def build_multi_station_url(goes_ids, lookback_hours=48, hsa="nil", state="nil", of=1):
	ids = [gid.strip().upper() for gid in (goes_ids or []) if gid and gid.strip()]
	if not ids:
		raise ValueError("No GOES_IDs provided")
	h = int(abs(int(lookback_hours)))
	parts = [
		"sinceday=-{0}".format(h),
		"hsa={0}".format(hsa),
		"state={0}".format(state),
	]
	for gid in ids:
		parts.append("nesdis_ids={0}".format(gid))
	parts.append("of={0}".format(of))
	return BASE + "?" + "&".join(parts)


def split_dss_path(fullname):
	p = fullname.strip()
	if not p.startswith("/"):
		raise ValueError("Not a DSS pathname: %s" % fullname)
	toks = p.split("/")
	if len(toks) < 8:
		raise ValueError("Unexpected DSS pathname format: %s" % fullname)
	return toks[1], toks[2], toks[3], toks[4], toks[5], toks[6]


def join_dss_path(a, b, c, d, e, f):
	return "/%s/%s/%s/%s/%s/%s/" % (a, b, c, d, e, f)


MONTHS = ["", "JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

def ymdhm_to_hec_string(dt):
	yyyy = int(dt[0:4])
	mm = int(dt[5:7])
	dd = int(dt[8:10])
	hh = int(dt[11:13])
	mi = int(dt[14:16])
	return "%02d%s%04d %02d%02d" % (dd, MONTHS[mm], yyyy, hh, mi)


def parse_decoded_pipe(text):
	series = {}
	for raw in text.splitlines():
		line = raw.strip()
		if not line or line.startswith("#"):
			continue
		parts = [p.strip() for p in line.split("|")]
		if len(parts) < 5:
			continue
		goes_id = parts[0].upper()
		shef = parts[2]
		dt = parts[3]
		val_s = parts[4]
		if not dt or not val_s:
			continue
		try:
			v = float(val_s)
		except:
			continue
		try:
			ht = HecTime()
			ht.set(ymdhm_to_hec_string(dt))
			t = ht.value()
		except:
			continue
		key = (goes_id, shef)
		if key not in series:
			series[key] = []
		series[key].append((t, v))

	for k in series.keys():
		series[k].sort(key=lambda tv: tv[0])
	return series

def write_irregular_ts(dss, pathname, times, values, units="UNSPEC", dtype="INST-VAL", lat=None, lon=None):
	tsc = TimeSeriesContainer()
	tsc.fullName = pathname
	tsc.units = units
	tsc.type = dtype
	tsc.times = times
	tsc.values = values
	tsc.numberValues = len(values)
	if lat is not None and lon is not None:
		try:
			tsc.setLatLong(float(lat), float(lon))
		except:
			pass
	# Coordinate System is Lat/Lon (2), Horizontal Datum is NAD83 (1), and Units of Decimal Degrees (3)
	tsc.coordinateSystem = 2
	tsc.horizontalDatum = 1
	tsc.horizontalUnits = 3
	tsc.timeZoneID = "UTC"
	dss.put(tsc)
	return len(values)

def main():
	run_log = []
	run_log.append("HADS DecodedData -> DSS import log")
	run_log.append("Watershed: %s" % WATERSHED_NAME)
	run_log.append("")
	# Lookback prompt
	days = prompt_lookback_days(default_days=2, max_days=7)
	if days is None:
		print("Cancelled.")
		run_log.append("Cancelled by user at lookback prompt.")
		show_log_popup("HADS Import - Cancelled", run_log)
		return
	lookback_hours = days * 24
	of = 1
	# Determine extract_hads.config path (arg1 overrides default)
	cfg = None
	try:
		if len(sys.argv) >= 2 and os.path.isfile(sys.argv[1]):
			cfg = sys.argv[1]
	except:
		cfg = None
	if not cfg:
		cfg = default_extract_hads_config_path()

	run_log.append("extract_hads.config: %s" % cfg)
	conf = read_extract_hads_config(cfg)
	hads_list = safe_strip(conf.get("hads_file", ""))
	out_dss = safe_strip(conf.get("dss_file", ""))
	run_log.append("HADS list: %s" % hads_list)
	run_log.append("Output DSS: %s" % out_dss)
	run_log.append("Lookback: %d days (%d hours)" % (days, lookback_hours))
	run_log.append("")
	print("Using extract_hads.config:", cfg)
	print("HADS list:", hads_list)
	print("Output DSS:", out_dss)
	
	if not hads_list or not os.path.isfile(hads_list):
		msg = "ERROR: hads_file not found in config or file missing: %s" % hads_list
		print(msg)
		run_log.append(msg)
		show_log_popup("HADS Import - ERROR", run_log)
		return
	if not out_dss:
		msg = "ERROR: dss_file not set in config."
		print(msg)
		run_log.append(msg)
		show_log_popup("HADS Import - ERROR", run_log)
		return
	sites = read_hads_sites(hads_list)
	if not sites:
		msg = "ERROR: No sites found in HADS list: %s" % hads_list
		print(msg)
		run_log.append(msg)
		show_log_popup("HADS Import - No Sites", run_log)
		return
	goes_ids = [s["goes_id"] for s in sites]
	url = build_multi_station_url(goes_ids, lookback_hours=lookback_hours, hsa="nil", state="nil", of=of)

	run_log.append("Sites requested: %d" % len(goes_ids))
	run_log.append("DecodedData URL:")
	run_log.append(url)
	run_log.append("")

	print("Fetching {0} sites in one request...".format(len(goes_ids)))
	print(url)

	# Fetch
	try:
		txt = fetch_text_java(url, log=run_log)
		run_log.append("Fetch: OK (%d chars)" % len(txt))
	except Exception as ex:
		msg = "ERROR fetching DecodedData: %s" % ex
		print(msg)
		run_log.append(msg)
		show_log_popup("HADS Import - ERROR", run_log)
		return

	# Parse
	series = parse_decoded_pipe(txt)
	run_log.append("Parsed series keys: %d (unique (GOES_ID, SHEF) pairs)" % len(series))
	run_log.append("")

	# Write
	written_sites = 0
	missing_sites = 0
	error_sites = 0
	total_values_written = 0
	write_details = []

	dss = None
	try:
		dss = HecDss.open(out_dss)
	except Exception as ex:
		msg = "ERROR opening DSS file '%s': %s" % (out_dss, ex)
		print(msg)
		run_log.append(msg)
		show_log_popup("HADS Import - ERROR", run_log)
		return
	try:
		for s in sites:
			goes_id = s["goes_id"]
			base_path = s["dss_base"]
			try:
				a0, b0, c0, d0, e0, f0 = split_dss_path(base_path)
			except Exception as ex:
				error_sites += 1
				write_details.append("GOES_ID=%s -> ERROR invalid DSS_PATH '%s' (%s)" % (goes_id, base_path, ex))
				continue
			wrote_any = False
			shef_written = 0
			values_written = 0

			for (gid, shef), tvs in series.items():
				if gid != goes_id:
					continue
				c_part, units = SHEF_MAP.get(shef, (shef, "UNSPEC"))
				e_part = "IR-DAY"
				pathname = join_dss_path(a0, b0, c_part, d0, e_part, f0)
				times = [t for (t, v) in tvs]
				values = [v for (t, v) in tvs]
				lat_dd = s.get("lat_dd", None)
				lon_dd = s.get("lon_dd", None)
				try:
					n = write_irregular_ts(dss, pathname, times, values, units=units, dtype="INST-VAL",lat=lat_dd, lon=lon_dd)
					wrote_any = True
					shef_written += 1
					values_written += n
					total_values_written += n
					line = "GOES_ID=%s SHEF=%s -> wrote %d to %s" % (goes_id, shef, n, pathname)
					print(line)
					write_details.append(line)
				except Exception as ex:
					error_sites += 1
					line = "GOES_ID=%s SHEF=%s -> ERROR writing to %s (%s)" % (goes_id, shef, pathname, ex)
					print(line)
					write_details.append(line)
			if wrote_any:
				written_sites += 1
				write_details.append("GOES_ID=%s -> wrote %d value(s) across %d SHEF code(s) [B=%s]" % (goes_id, values_written, shef_written, b0))
			else:
				missing_sites += 1
				write_details.append("GOES_ID=%s -> no data returned" % goes_id)
	finally:
		try:
			if dss is not None:
				dss.done()
		except:
			pass
	run_log.append("Write summary:")
	run_log.append("  Sites in list: %d" % len(sites))
	run_log.append("  Sites with data: %d" % written_sites)
	run_log.append("  Sites with no data: %d" % missing_sites)
	run_log.append("  Sites with errors: %d" % error_sites)
	run_log.append("  Total values written: %d" % total_values_written)
	run_log.append("")
	run_log.append("Details:")
	run_log.extend(write_details)
	run_log.append("")
	run_log.append("Done.")

	print("Done.")
	show_log_popup("HADS Import - Complete", run_log)

if __name__ == "__main__":
	main()
