# -------------------------------------------------------------------
# Extract_RFC (NWPS) -> DSS
#
# Reads extract_rfc.config (rfc_file + dss_file), then:
# - reads the .rfc list (GAUGE_ID + DSS_PATH blocks)
# - fetches NWPS stageflow JSON for each gauge:
#     https://api.water.noaa.gov/nwps/v1/gauges/<GAUGE_ID>/stageflow
# - separates observed vs forecast
# - writes each to DSS using DSS_PATH as a base:
#     - Observed:   F-part = "<base>-Obs"      (e.g., RFC-Obs)
#     - Forecast:   F-part = "<base>-Forecast" (e.g., RFC-Forecast)
# -------------------------------------------------------------------

from __future__			import print_function
from javax.swing		import JOptionPane, JScrollPane, JTextArea
from java.awt			import Dimension
from java.net			import URL
from java.io			import BufferedReader, InputStreamReader
from java.net			import SocketTimeoutException
from hec.heclib.dss		import HecDss
from hec.io				import TimeSeriesContainer
from hec.heclib.util	import HecTime
from hec2.rts.script	import RTS
import os, sys, time, json


BASE_STAGEFLOW = "https://api.water.noaa.gov/nwps/v1/gauges/{0}/stageflow"
WATERSHED_NAME = str(RTS.getWatershed())

DEBUG_JSON_SNIPPET = False  # set True to include partial JSON in log for troubleshooting

# DSS Defaults
DEFAULT_STAGE_PART = "Stage"
DEFAULT_STAGE_UNITS  = "ft"
DEFAULT_FLOW_C_PART  = "Flow"
DEFAULT_FLOW_UNITS   = "cfs"
DEFAULT_E_PART = "IR-Day"
DEFAULT_TYPE   = "INST-VAL"

def build_ts_path_from_base(base_path, c_part, e_part, f_part):
	a, b, c, d, e, f = split_dss_path(base_path)
	c = safe_strip(c) or safe_strip(c_part) or "Stage"
	e = safe_strip(e) or safe_strip(e_part) or "IR-Day"
	f = safe_strip(f_part)

	return join_dss_path(a, b, c, d, e, f)


def safe_strip(s):
	try:
		return s.strip() if s is not None else ""
	except:
		try:
			return str(s).strip()
		except:
			return ""


def show_log_popup(title, lines, width=900, height=600, max_chars=25000):
	txt = "\n".join([str(x) for x in (lines or [])])
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


def default_extract_rfc_config_path():
	# <projectDir>/shared/source/extract_rfc.config
	try:
		proj_dir = RTS.getWatershed().getProjectDirectory()
		return os.path.join(proj_dir, "shared", "source", "extract_rfc.config")
	except:
		return os.path.join(os.getcwd(), "extract_rfc.config")


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


def read_extract_rfc_config(config_path):
	data = {
		"version": "",
		"rfc_file": "",
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


def read_rfc_sites(rfc_list_path):
	sites = []
	current = {}
	required = ["GAUGE_ID", "DSS_PATH"]

	def finalize_block():
		if not current:
			return
		missing = [k for k in required if not safe_strip(current.get(k, ""))]
		if missing:
			return
		sites.append({
			"gauge_id": safe_strip(current.get("GAUGE_ID", "")).upper(),
			"name": safe_strip(current.get("NAME", "")),
			"state": safe_strip(current.get("STATE", "")),
			"wfo": safe_strip(current.get("WFO", "")),
			"rfc": safe_strip(current.get("RFC", "")),
			"lat": safe_strip(current.get("LAT", "")),
			"lon": safe_strip(current.get("LON", "")),
			"dss_base": safe_strip(current.get("DSS_PATH", "")),
		})

	f = None
	try:
		f = open(rfc_list_path, "rb")
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

def iso_to_hec_string(dt):
	s = safe_strip(dt)
	if not s:
		raise ValueError("Empty datetime")

	# normalize
	s = s.replace("Z", "")
	s = s.replace("T", " ")
	# remove timezone if present
	if "+" in s:
		s = s.split("+", 1)[0]
	if "-" in s[10:]:
		# handles ...-05:00 after the time
		s = s[:19]

	yyyy = int(s[0:4])
	mm = int(s[5:7])
	dd = int(s[8:10])
	hh = int(s[11:13])
	mi = int(s[14:16])
	return "%02d%s%04d %02d%02d" % (dd, MONTHS[mm], yyyy, hh, mi)


def safe_float(x, default=None):
	try:
		s = safe_strip(x)
		if not s:
			return default
		return float(s)
	except:
		return default


def parse_stageflow_json(text):
	"""
	Returns:
	  obs_stage_tvs, fc_stage_tvs, obs_flow_tvs, fc_flow_tvs, meta

	meta includes units if present:
	  meta["primaryUnits"] (stage units)
	  meta["secondaryUnits"] (flow units)
	"""
	obj = json.loads(text)

	meta = {}

	def points_to_tvs(points, value_key):
		out = []
		for p in (points or []):
			if not isinstance(p, dict):
				continue

			t_raw = p.get("validTime", p.get("time", p.get("dateTime", None)))
			v_raw = p.get(value_key, None)
			if t_raw is None or v_raw is None:
				continue

			try:
				v = float(v_raw)
			except:
				continue

			try:
				ht = HecTime()
				ht.set(iso_to_hec_string(str(t_raw)))
				t = int(ht.value())
			except:
				continue

			out.append((t, v))

		out.sort(key=lambda tv: tv[0])
		return out
	
	obs_block = obj.get("observed", None) if isinstance(obj, dict) else None
	fc_block  = obj.get("forecast", None) if isinstance(obj, dict) else None

	obs_data = None
	fc_data  = None

	if isinstance(obs_block, dict):
		meta["primaryUnits"]   = obs_block.get("primaryUnits", meta.get("primaryUnits"))
		meta["secondaryUnits"] = obs_block.get("secondaryUnits", meta.get("secondaryUnits"))
		obs_data = obs_block.get("data", None)

	if isinstance(fc_block, dict):
		meta["primaryUnits"]   = fc_block.get("primaryUnits", meta.get("primaryUnits"))
		meta["secondaryUnits"] = fc_block.get("secondaryUnits", meta.get("secondaryUnits"))
		fc_data = fc_block.get("data", None)

	# Stage uses "primary"; Flow uses "secondary"
	obs_stage_tvs = points_to_tvs(obs_data, "primary")
	fc_stage_tvs  = points_to_tvs(fc_data,  "primary")
	obs_flow_tvs  = points_to_tvs(obs_data, "secondary")
	fc_flow_tvs   = points_to_tvs(fc_data,  "secondary")

	return obs_stage_tvs, fc_stage_tvs, obs_flow_tvs, fc_flow_tvs, meta


def convert_flow_to_cfs(flow_tvs, flow_units):
	u = safe_strip(flow_units).lower()
	if not flow_tvs:
		return [], "cfs"
	# NWPS commonly uses kcfs (thousand cubic feet per second)
	if u in ["kcfs", "k cfs", "k-cfs", "k_cfs"]:
		return [(t, v * 1000.0) for (t, v) in flow_tvs], "cfs"
	# If already cfs, keep
	if u in ["cfs", "ft3/s", "ft^3/s", "cms"]:
		return flow_tvs, flow_units if flow_units else "cfs"
	return flow_tvs, (flow_units if flow_units else "cfs")


def write_irregular_ts(dss, pathname, times, values, units="ft", dtype="INST-VAL", lat=None, lon=None):
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


def replace_f_part(pathname, new_f):
	a, b, c, d, e, f = split_dss_path(pathname)
	return join_dss_path(a, b, c, d, e, new_f)


def get_cavi_time_window_string(debug_log=None):
	candidates = []
	
	try:
		m = RTS.getCurrentModule()
		if m is not None:
			if hasattr(m, "getTimeWindowString"):
				candidates.append(("RTS.getCurrentModule().getTimeWindowString()", m.getTimeWindowString()))
			if hasattr(m, "getTimeWindow"):
				candidates.append(("RTS.getCurrentModule().getTimeWindow()", m.getTimeWindow()))
	except Exception as ex:
		candidates.append(("RTS.getCurrentModule() EX", str(ex)))
	
	try:
		from usace.cavi.client import CAVI as cCAVI
		frame = cCAVI.getBrowserFrame()
		if frame is not None:
			# These method names vary by CAVI version, so probe safely.
			for meth in ["getCurrentModule", "getActiveModule", "getSelectedModule", "getSelectedComponent"]:
				if hasattr(frame, meth):
					try:
						obj = getattr(frame, meth)()
						candidates.append(("CAVI.getBrowserFrame().%s()" % meth, obj))
						if obj is not None and hasattr(obj, "getTimeWindowString"):
							candidates.append(("CAVI frame obj.getTimeWindowString()", obj.getTimeWindowString()))
						if obj is not None and hasattr(obj, "getTimeWindow"):
							candidates.append(("CAVI frame obj.getTimeWindow()", obj.getTimeWindow()))
					except Exception as ex:
						candidates.append(("CAVI frame %s EX" % meth, str(ex)))
	except Exception as ex:
		candidates.append(("CAVI import/frame EX", str(ex)))
	
	def norm(v):
		if v is None:
			return None
		try:
			s = str(v)
		except:
			return None
		s = s.strip()
		return s if s else None

	found = None
	for src, v in candidates:
		s = norm(v)
		if s:
			found = s
			break

	# Optional debug logging
	if debug_log is not None:
		debug_log.append("TimeWindow probe results:")
		for src, v in candidates:
			debug_log.append("  {0}: {1}".format(src, v))
		debug_log.append("Selected time window: {0}".format(found if found else "(none)"))

	return found


def prompt_lookback_lookahead(title, default_back=7, default_ahead=5, max_back=800, max_ahead=30):
	prompt = (
		"Enter lookback days and lookahead days.\n"
		"Examples: 7,5   or   7 5\n\n"
		"Lookback (observed) range: 1-{0}\n"
		"Lookahead (forecast) range: 0-{1}"
	).format(max_back, max_ahead)

	default_text = "{0},{1}".format(int(default_back), int(default_ahead))

	s = JOptionPane.showInputDialog(None, prompt, default_text)
	if s is None:
		return None, None  # cancelled

	txt = safe_strip(s)
	if not txt:
		return None, None

	# split by comma or whitespace
	parts = [p for p in txt.replace(",", " ").split() if p]
	if len(parts) == 1:
		back_s = parts[0]
		ahead_s = "0"
	else:
		back_s = parts[0]
		ahead_s = parts[1]

	try:
		back = int(back_s)
		ahead = int(ahead_s)
	except:
		JOptionPane.showMessageDialog(None, "Invalid entry: {0}".format(txt), title, JOptionPane.ERROR_MESSAGE)
		return None, None

	if back < 1 or back > max_back:
		JOptionPane.showMessageDialog(None, "Lookback must be between 1 and {0}.".format(max_back), title, JOptionPane.ERROR_MESSAGE)
		return None, None

	if ahead < 0 or ahead > max_ahead:
		JOptionPane.showMessageDialog(None, "Lookahead must be between 0 and {0}.".format(max_ahead), title, JOptionPane.ERROR_MESSAGE)
		return None, None

	return back, ahead


def resolve_obs_fc_windows(tw=None, max_days_back=800, max_days_ahead=30):
	def _is_blank(x):
		return (x is None) or (safe_strip(str(x)) == "")

	ht_now = HecTime()
	ht_now.setCurrent()
	now_int = int(ht_now.value())

	# -------------------------
	# Use TW if provided
	# -------------------------
	if not _is_blank(tw):
		tw_s = safe_strip(str(tw))
		
		try:
			from hec.heclib.util import HecTimeWindow
			twobj = HecTimeWindow()
			twobj.setTimeWindow(tw_s)
			obs_start_int = int(twobj.getStartTime())
			obs_end_int   = int(twobj.getEndTime())
			return obs_start_int, obs_end_int, obs_start_int, obs_end_int, "Module time window: {0}".format(tw_s)
		except:
			pass
		
		try:
			parts = tw_s.split(";")
			if len(parts) != 2:
				raise ValueError("Unexpected TW format (missing ';'): {0}".format(tw_s))

			def parse_one(p):
				p = safe_strip(p)
				if "," in p:
					date_s, time_s = [safe_strip(x) for x in p.split(",", 1)]
				else:
					toks = p.split()
					if len(toks) < 2:
						raise ValueError("Unexpected TW part: {0}".format(p))
					date_s = toks[0]
					time_s = toks[1]
				
				time_s = time_s.replace(":", "")
				hec_str = "{0} {1}".format(date_s, time_s)

				ht = HecTime()
				ht.set(hec_str)
				return int(ht.value())

			start_int = parse_one(parts[0])
			end_int   = parse_one(parts[1])

			return start_int, end_int, start_int, end_int, "Module time window: {0}".format(tw_s)

		except Exception as ex:
			raise ValueError("Could not parse module time window '{0}': {1}".format(tw_s, ex))

	# -------------------------
	# TW not available -> prompt
	# -------------------------
	obs_days, fc_days = prompt_lookback_lookahead(
		"Extract_RFC Time Window",
		default_back=7,
		default_ahead=5,
		max_back=max_days_back,
		max_ahead=max_days_ahead
	)
	if obs_days is None:
		return None, None, None, None, "Cancelled"

	obs_start_int = now_int - obs_days * 24 * 60
	obs_end_int   = now_int
	fc_start_int  = now_int
	fc_end_int    = now_int + fc_days * 24 * 60

	return obs_start_int, obs_end_int, fc_start_int, fc_end_int, "Prompted window: Obs T-{0}D..T, Fcst T..T+{1}D".format(obs_days, fc_days)


def filter_tvs_to_window(tvs, start_int, end_int):
	if not tvs:
		return []
	out = []
	for t, v in tvs:
		try:
			ti = int(t)
		except:
			continue
		if ti < start_int or ti > end_int:
			continue
		out.append((ti, v))
	return out


def main():
	run_log = []
	run_log.append("RFC (NWPS stageflow) -> DSS import log")
	run_log.append("Watershed: %s" % WATERSHED_NAME)
	run_log.append("")
	
	cfg_path = None
	try:
		if len(sys.argv) >= 2 and os.path.isfile(sys.argv[1]):
			cfg_path = sys.argv[1]
	except:
		cfg_path = None
	if not cfg_path:
		cfg_path = default_extract_rfc_config_path()

	run_log.append("extract_rfc.config: %s" % cfg_path)

	conf = read_extract_rfc_config(cfg_path)
	rfc_list = safe_strip(conf.get("rfc_file", ""))
	out_dss = safe_strip(conf.get("dss_file", ""))

	run_log.append("RFC list: %s" % rfc_list)
	run_log.append("Output DSS: %s" % out_dss)
	run_log.append("")

	if not rfc_list or not os.path.isfile(rfc_list):
		msg = "ERROR: rfc_file not found in config or file missing: %s" % rfc_list
		print(msg)
		run_log.append(msg)
		show_log_popup("RFC Extract - ERROR", run_log)
		return

	if not out_dss:
		msg = "ERROR: dss_file not set in config."
		print(msg)
		run_log.append(msg)
		show_log_popup("RFC Extract - ERROR", run_log)
		return

	sites = read_rfc_sites(rfc_list)
	if not sites:
		msg = "ERROR: No sites found in RFC list: %s" % rfc_list
		print(msg)
		run_log.append(msg)
		show_log_popup("RFC Extract - No Sites", run_log)
		return

	run_log.append("Sites in list: %d" % len(sites))
	run_log.append("")

	# -----------------------------
	# Resolve time window ONCE
	# -----------------------------
	tw = get_cavi_time_window_string(debug_log=None)
	
	try:
		obs_start, obs_end, fc_start, fc_end, tw_summary = resolve_obs_fc_windows(tw=tw)
	except Exception as ex:
		run_log.append("ERROR resolving time window: {0}".format(ex))
		show_log_popup("RFC Extract - ERROR", run_log)
		return
	if obs_start is None:
		run_log.append("Cancelled by user.")
		show_log_popup("RFC Extract - Cancelled", run_log)
		return
	run_log.append(tw_summary)
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
		show_log_popup("RFC Extract - ERROR", run_log)
		return

	try:
		for s in sites:
			gauge_id = s["gauge_id"]
			base_path = s["dss_base"]
			lat = safe_float(s.get("lat", None), default=None)
			lon = safe_float(s.get("lon", None), default=None)
			
			if lat is None or lon is None:
				run_log.append("Gauge %s: LAT/LON missing or invalid (LAT=%s LON=%s)" % (gauge_id, s.get("lat",""), s.get("lon","")))

			url = BASE_STAGEFLOW.format(gauge_id)
			run_log.append("Gauge %s URL: %s" % (gauge_id, url))

			# Validate DSS base pathname
			try:
				a0, b0, c0, d0, e0, f0 = split_dss_path(base_path)
			except Exception as ex:
				error_sites += 1
				write_details.append("GAUGE_ID=%s -> ERROR invalid DSS_PATH '%s' (%s)" % (gauge_id, base_path, ex))
				continue

			# Fetch
			try:
				txt = fetch_text_java(url, log=run_log)
				if DEBUG_JSON_SNIPPET:
					write_details.append("GAUGE_ID=%s -> JSON snippet: %s" % (gauge_id, safe_strip(txt[:600]).replace("\n", " ")))
			except Exception as ex:
				error_sites += 1
				write_details.append("GAUGE_ID=%s -> ERROR fetching stageflow (%s)" % (gauge_id, ex))
				continue

			# Parse observed/forecast + apply time windows
			try:
				obs_stage, fc_stage, obs_flow, fc_flow, meta = parse_stageflow_json(txt)
				# filter to windows
				obs_stage = filter_tvs_to_window(obs_stage, obs_start, obs_end)
				fc_stage  = filter_tvs_to_window(fc_stage,  fc_start,  fc_end)
				obs_flow  = filter_tvs_to_window(obs_flow,  obs_start, obs_end)
				fc_flow   = filter_tvs_to_window(fc_flow,   fc_start,  fc_end)
			except Exception as ex:
				error_sites += 1
				write_details.append("GAUGE_ID=%s -> ERROR parsing JSON (%s)" % (gauge_id, ex))
				write_details.append("GAUGE_ID=%s -> fetched %d chars" % (gauge_id, len(txt)))
				continue

			# Prepare DSS pathnames
			f_obs = ("%s-Obs" % f0) if f0 else "RFC-Obs"
			f_fc  = ("%s-Forecast" % f0) if f0 else "RFC-Forecast"
			# Stage paths
			path_stage_obs = build_ts_path_from_base(base_path, "Stage", DEFAULT_E_PART, f_obs)
			path_stage_fc  = build_ts_path_from_base(base_path, "Stage", DEFAULT_E_PART, f_fc)
			# Flow paths
			path_flow_obs  = build_ts_path_from_base(base_path, "Flow",  DEFAULT_E_PART, f_obs)
			path_flow_fc   = build_ts_path_from_base(base_path, "Flow",  DEFAULT_E_PART, f_fc)

			wrote_any = False
			values_written = 0
			
			# Stage units from meta if available
			stage_units = safe_strip(meta.get("primaryUnits", "")) or "FT"
			
			# Flow units and conversion
			flow_units_raw = safe_strip(meta.get("secondaryUnits", ""))  # often "kcfs"
			obs_flow_c, flow_units_out = convert_flow_to_cfs(obs_flow, flow_units_raw)
			fc_flow_c,  flow_units_out = convert_flow_to_cfs(fc_flow,  flow_units_raw)
			
			# Write STAGE observed/forecast
			if obs_stage:
				times = [t for (t, v) in obs_stage]
				vals  = [v for (t, v) in obs_stage]
				n = write_irregular_ts(dss, path_stage_obs, times, vals, units=stage_units.upper(), dtype=DEFAULT_TYPE, lat=lat, lon=lon)
				values_written += n
				total_values_written += n
				wrote_any = True
				write_details.append("GAUGE_ID=%s STAGE OBS -> wrote %d to %s" % (gauge_id, n, path_stage_obs))
			else:
				write_details.append("GAUGE_ID=%s STAGE OBS -> no data (in time window)" % gauge_id)
			
			if fc_stage:
				times = [t for (t, v) in fc_stage]
				vals  = [v for (t, v) in fc_stage]
				n = write_irregular_ts(dss, path_stage_fc, times, vals, units=stage_units.upper(), dtype=DEFAULT_TYPE)
				values_written += n
				total_values_written += n
				wrote_any = True
				write_details.append("GAUGE_ID=%s STAGE FORECAST -> wrote %d to %s" % (gauge_id, n, path_stage_fc))
			else:
				write_details.append("GAUGE_ID=%s STAGE FORECAST -> no data (in time window)" % gauge_id)
			
			# Write FLOW observed/forecast (only if available)
			if obs_flow_c:
				times = [t for (t, v) in obs_flow_c]
				vals  = [v for (t, v) in obs_flow_c]
				n = write_irregular_ts(dss, path_flow_obs, times, vals, units="CFS", dtype=DEFAULT_TYPE)
				values_written += n
				total_values_written += n
				wrote_any = True
				write_details.append("GAUGE_ID=%s FLOW OBS -> wrote %d to %s (from %s)" % (gauge_id, n, path_flow_obs, flow_units_raw))
			else:
				write_details.append("GAUGE_ID=%s FLOW OBS -> no data (in time window)" % gauge_id)
			
			if fc_flow_c:
				times = [t for (t, v) in fc_flow_c]
				vals  = [v for (t, v) in fc_flow_c]
				n = write_irregular_ts(dss, path_flow_fc, times, vals, units="CFS", dtype=DEFAULT_TYPE)
				values_written += n
				total_values_written += n
				wrote_any = True
				write_details.append("GAUGE_ID=%s FLOW FORECAST -> wrote %d to %s (from %s)" % (gauge_id, n, path_flow_fc, flow_units_raw))
			else:
				write_details.append("GAUGE_ID=%s FLOW FORECAST -> no data (in time window)" % gauge_id)

			if wrote_any:
				written_sites += 1
			else:
				missing_sites += 1

			write_details.append("GAUGE_ID=%s -> total values written: %d" % (gauge_id, values_written))

	finally:
		try:
			if dss is not None:
				dss.done()
		except:
			pass

	run_log.append("")
	run_log.append("Write summary:")
	run_log.append("  Sites in list: %d" % len(sites))
	run_log.append("  Sites with data written: %d" % written_sites)
	run_log.append("  Sites with no data (in window): %d" % missing_sites)
	run_log.append("  Sites with errors: %d" % error_sites)
	run_log.append("  Total values written: %d" % total_values_written)
	run_log.append("")
	run_log.append("Details:")
	if write_details:
		run_log.extend(write_details)
	else:
		run_log.append("(none)")
	run_log.append("")
	run_log.append("Done.")

	print("Done.")
	show_log_popup("RFC Extract - Complete", run_log)


if __name__ == "__main__":
	main()
