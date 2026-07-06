# -------------------------------------------------------------------
# NWS RFC (NWPS) Gauges Filter + staging list exporter
#
# Features (mirrors HADS selector):
# - Load/filter NWPS gauges
# - Staging list with DSS_PATH snapshotted on add
# - Staging list supports editing ALL columns
# - Add Blank Row for ad-hoc/manual entries
# - Import/Open existing .nws file and append entries to staging list (dedupe)
# - Export writes key=value blocks including DSS_PATH
#
# Data source:
#   https://api.water.noaa.gov/nwps/v1/gauges?srid=SRID_UNSPECIFIED
# -------------------------------------------------------------------

from __future__					import print_function
from java.awt					import BorderLayout, Dimension, FlowLayout
from java.awt.event				import ActionListener, KeyAdapter
from javax.swing				import (JButton, JCheckBox, JComboBox, JDialog, JFrame,
										JLabel, JPanel, JScrollPane, JTable, JTextField,
										SwingUtilities, JFileChooser, JSplitPane)
from javax.swing.filechooser	import FileNameExtensionFilter
from javax.swing.table			import AbstractTableModel
from hec2.rts.script			import RTS
import java.io, sys, os, re, urllib2, json


API_URL = "https://api.water.noaa.gov/nwps/v1/gauges?srid=SRID_UNSPECIFIED"

BPART_MODES = ["GAUGE_ID", "Name", "GAUGE_ID (WFO)", "GAUGE_ID (RFC)"]

def script_dir_fallback():
	try:
		p = sys.argv[0]
		if p:
			p = os.path.abspath(p)
			d = os.path.dirname(p)
			if d and os.path.isdir(d):
				return d
	except:
		pass
	return os.getcwd()


SCRIPT_DIR = script_dir_fallback()


def watershed_project_dir_fallback():
	try:
		proj_dir = RTS.getWatershed().getProjectDirectory()
		target = os.path.join(proj_dir, "shared", "source")
		if not os.path.isdir(target):
			os.makedirs(target)
		return target
	except:
		return SCRIPT_DIR


def safe_strip(s):
	try:
		return s.strip() if s is not None else ""
	except:
		try:
			return str(s).strip()
		except:
			return ""


def get_abbrev_or_str(v):
	try:
		if isinstance(v, dict):
			a = v.get("ABBREVIATION", v.get("abbreviation", ""))
			return safe_strip(a).upper()
	except:
		pass
	return safe_strip(v).upper()


def download_text(url):
	req = urllib2.Request(url, headers={"User-Agent": "JythonSwing/1.0"})
	resp = urllib2.urlopen(req, timeout=60)
	data = resp.read()
	try:
		return data.decode("utf-8", "replace")
	except:
		return data


def sanitize_dss_part(s):
	s = safe_strip(s)
	if not s:
		return ""
	s = s.replace("/", "-").replace("\\", "-")
	s = re.sub(r"\s+", " ", s).strip()
	s = re.sub(r"[^A-Za-z0-9 _\-\.\(\)]", "", s)
	s = re.sub(r"\s+", " ", s).strip()
	return s


def build_dss_path(a, b, f):
	a = sanitize_dss_part(a)
	b = sanitize_dss_part(b)
	f = sanitize_dss_part(f)
	return "/%s/%s////%s/" % (a, b, f)


def parse_nwps_gauges_json(text):
	obj = json.loads(text)

	items = None
	if isinstance(obj, list):
		items = obj
	elif isinstance(obj, dict):
		if "gauges" in obj and isinstance(obj["gauges"], list):
			items = obj["gauges"]
		elif "features" in obj and isinstance(obj["features"], list):
			items = obj["features"]
		elif "data" in obj and isinstance(obj["data"], list):
			items = obj["data"]
		else:
			for k, v in obj.items():
				if isinstance(v, list):
					items = v
					break
	if items is None:
		return []

	def fmt_num(x):
		if x is None:
			return ""
		try:
			return "{0:.6f}".format(float(x))
		except:
			return safe_strip(x)

	out = []
	for it in items:
		if isinstance(it, dict) and "properties" in it and isinstance(it["properties"], dict):
			p = it["properties"]
		else:
			p = it if isinstance(it, dict) else {}

		gid = safe_strip(p.get("id", p.get("gaugeId", p.get("lid", "")))).upper()
		name = safe_strip(p.get("name", p.get("location", p.get("stationName", ""))))
		state = get_abbrev_or_str(p.get("state", p.get("st", "")))
		wfo   = get_abbrev_or_str(p.get("wfo", p.get("cwa", "")))
		rfc   = get_abbrev_or_str(p.get("rfc", p.get("rfcId", "")))

		lat = p.get("latitude", p.get("lat", None))
		lon = p.get("longitude", p.get("lon", None))

		if (lat is None or lon is None) and isinstance(it, dict):
			geom = it.get("geometry", None)
			try:
				if geom and geom.get("type") == "Point":
					coords = geom.get("coordinates", None)
					if coords and len(coords) >= 2:
						lon = coords[0]
						lat = coords[1]
			except:
				pass

		row = {
			"gauge_id": gid,
			"name": name,
			"state": state,
			"wfo": wfo,
			"rfc": rfc,
			"lat": fmt_num(lat),
			"lon": fmt_num(lon),
			"dss_path": "",
		}
		if not row["gauge_id"]:
			continue
		out.append(row)

	return out


def set_table_column_widths(table, widths):
	cm = table.getColumnModel()
	for i in range(min(len(widths), cm.getColumnCount())):
		col = cm.getColumn(i)
		col.setPreferredWidth(int(widths[i]))
		col.setMinWidth(20)


def parse_nws_file_text(text):
	rows = []
	cur = {}

	def push_cur():
		if not cur:
			return
		row = {
			"gauge_id": safe_strip(cur.get("GAUGE_ID", "")).upper(),
			"name": safe_strip(cur.get("NAME", "")),
			"state": safe_strip(cur.get("STATE", "")).upper(),
			"wfo": safe_strip(cur.get("WFO", "")).upper(),
			"rfc": safe_strip(cur.get("RFC", "")).upper(),
			"lat": safe_strip(cur.get("LAT", "")),
			"lon": safe_strip(cur.get("LON", "")),
			"dss_path": safe_strip(cur.get("DSS_PATH", "")),
		}
		if row["gauge_id"]:
			rows.append(row)

	for raw in text.splitlines():
		line = raw.strip()
		if not line:
			push_cur()
			cur = {}
			continue
		if line.startswith("#"):
			continue
		if "=" not in line:
			continue
		k, v = line.split("=", 1)
		cur[k.strip().upper()] = v.strip()
	push_cur()
	return rows


class SitesTableModel(AbstractTableModel):
	COLS = ["Gauge ID", "Name", "State", "WFO", "RFC", "Latitude", "Longitude"]
	KEYS = ["gauge_id", "name", "state", "wfo", "rfc", "lat", "lon"]

	def __init__(self, rows):
		AbstractTableModel.__init__(self)
		self._rows = rows[:]

	def setRows(self, rows):
		self._rows = rows[:]
		self.fireTableDataChanged()

	def getRows(self):
		return self._rows

	def getRow(self, model_row_index):
		return self._rows[model_row_index]

	def addRowsUnique(self, new_rows, key_fn):
		existing = set([key_fn(r) for r in self._rows])
		added = 0
		for r in new_rows:
			k = key_fn(r)
			if k in existing:
				continue
			self._rows.append(r)
			existing.add(k)
			added += 1
		if added:
			self.fireTableDataChanged()
		return added

	def removeRowsByKeys(self, keys_to_remove, key_fn):
		before = len(self._rows)
		self._rows = [r for r in self._rows if key_fn(r) not in keys_to_remove]
		removed = before - len(self._rows)
		if removed:
			self.fireTableDataChanged()
		return removed

	def clear(self):
		if self._rows:
			self._rows = []
			self.fireTableDataChanged()

	def getRowCount(self):
		return len(self._rows)

	def getColumnCount(self):
		return len(self.COLS)

	def getColumnName(self, col):
		return self.COLS[col]

	def getValueAt(self, row, col):
		r = self._rows[row]
		return safe_strip(r.get(self.KEYS[col], ""))


class ExportSitesTableModel(SitesTableModel):
	COLS = ["Gauge ID", "Name", "State", "WFO", "RFC", "Latitude", "Longitude", "DSS_PATH"]
	KEYS = ["gauge_id", "name", "state", "wfo", "rfc", "lat", "lon", "dss_path"]

	def getColumnCount(self):
		return len(self.COLS)

	def getColumnName(self, col):
		return self.COLS[col]

	def getValueAt(self, row, col):
		r = self._rows[row]
		return safe_strip(r.get(self.KEYS[col], ""))

	def isCellEditable(self, row, col):
		return True

	def setValueAt(self, value, row, col):
		r = self._rows[row]
		k = self.KEYS[col]
		r[k] = safe_strip(value)
		self.fireTableCellUpdated(row, col)


class NwsSitesDialog(JDialog):
	def __init__(self, owner=None):
		JDialog.__init__(self, owner, "NWS RFC (NWPS) Sites Filter", True)
		self.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE)

		self.all_sites = []
		self.filtered_sites = []

		# --- Filters panel ---
		filters = JPanel(FlowLayout(FlowLayout.LEFT))

		self.tfGauge = JTextField(10)
		self.tfName = JTextField(22)
		self.tfState = JTextField(4)
		self.tfWfo = JTextField(6)
		self.tfRfc = JTextField(6)

		filters.add(JLabel("Gauge ID:"))
		filters.add(self.tfGauge)
		filters.add(JLabel("Name contains:"))
		filters.add(self.tfName)
		filters.add(JLabel("State:"))
		filters.add(self.tfState)
		filters.add(JLabel("WFO:"))
		filters.add(self.tfWfo)
		filters.add(JLabel("RFC:"))
		filters.add(self.tfRfc)

		# --- Top buttons ---
		top_btns = JPanel(FlowLayout(FlowLayout.LEFT))
		self.btnLoad = JButton("Load/Reload")
		self.btnClear = JButton("Clear Filters")
		self.btnClose = JButton("Close")
		top_btns.add(self.btnLoad)
		top_btns.add(self.btnClear)
		top_btns.add(self.btnClose)

		top = JPanel(BorderLayout())
		top.add(filters, BorderLayout.CENTER)
		top.add(top_btns, BorderLayout.SOUTH)

		# --- DSS naming panel ---
		dss = JPanel(FlowLayout(FlowLayout.LEFT))
		self.tfA = JTextField(10)
		self.tfF = JTextField(10)
		self.cbBMode = JComboBox(BPART_MODES)

		self.tfA.setText("")
		self.tfF.setText("RFC")

		dss.add(JLabel("DSS A (Watershed, optional):"))
		dss.add(self.tfA)
		dss.add(JLabel("DSS B (Location):"))
		dss.add(self.cbBMode)
		dss.add(JLabel("DSS F (Source):"))
		dss.add(self.tfF)

		# --- Main results table ---
		self.model = SitesTableModel([])
		self.table = JTable(self.model)
		self.table.setAutoCreateRowSorter(True)
		set_table_column_widths(self.table, [90, 360, 55, 55, 55, 90, 100])
		scroller = JScrollPane(self.table)
		scroller.setPreferredSize(Dimension(1100, 300))

		# --- Staging list table ---
		self.exportModel = ExportSitesTableModel([])
		self.exportTable = JTable(self.exportModel)
		self.exportTable.setAutoCreateRowSorter(True)
		set_table_column_widths(self.exportTable, [90, 320, 55, 55, 55, 90, 100, 420])
		exportScroller = JScrollPane(self.exportTable)
		exportScroller.setPreferredSize(Dimension(1100, 240))

		# --- Staging buttons ---
		stage_btns = JPanel(FlowLayout(FlowLayout.LEFT))
		self.btnAddSelected = JButton("Add Selected")
		self.btnAddFiltered = JButton("Add Filtered")
		self.btnAddBlankRow = JButton("Add Blank Row")
		self.btnImport = JButton("Open .rfc...")
		self.btnRemoveFromList = JButton("Remove Selected from List")
		self.btnClearList = JButton("Clear List")
		self.btnExportList = JButton("Export List...")

		stage_btns.add(self.btnAddSelected)
		stage_btns.add(self.btnAddFiltered)
		stage_btns.add(self.btnAddBlankRow)
		stage_btns.add(self.btnImport)
		stage_btns.add(self.btnRemoveFromList)
		stage_btns.add(self.btnClearList)
		stage_btns.add(self.btnExportList)

		stage_panel = JPanel(BorderLayout())
		stage_panel.add(JLabel("Selected for Export (staging list):"), BorderLayout.NORTH)
		stage_panel.add(exportScroller, BorderLayout.CENTER)
		stage_panel.add(stage_btns, BorderLayout.SOUTH)

		# --- Split panels ---
		top_split = JSplitPane(JSplitPane.VERTICAL_SPLIT, scroller, dss)
		top_split.setResizeWeight(0.80)

		split = JSplitPane(JSplitPane.VERTICAL_SPLIT, top_split, stage_panel)
		split.setResizeWeight(0.60)

		self.lblStatus = JLabel("Ready.")

		self.getContentPane().setLayout(BorderLayout())
		self.getContentPane().add(top, BorderLayout.NORTH)
		self.getContentPane().add(split, BorderLayout.CENTER)
		self.getContentPane().add(self.lblStatus, BorderLayout.SOUTH)

		# Events
		self.btnLoad.addActionListener(self._onLoad())
		self.btnClear.addActionListener(self._onClear())
		self.btnClose.addActionListener(self._onClose())

		self.btnAddSelected.addActionListener(self._onAddSelected())
		self.btnAddFiltered.addActionListener(self._onAddFiltered())
		self.btnAddBlankRow.addActionListener(self._onAddBlankRow())
		self.btnImport.addActionListener(self._onImport())
		self.btnRemoveFromList.addActionListener(self._onRemoveFromList())
		self.btnClearList.addActionListener(self._onClearList())
		self.btnExportList.addActionListener(self._onExportList())

		dialog = self
		class RefKey(KeyAdapter):
			def keyReleased(_, e):
				dialog.applyFilters()
		self.tfGauge.addKeyListener(RefKey())
		self.tfName.addKeyListener(RefKey())
		self.tfState.addKeyListener(RefKey())
		self.tfWfo.addKeyListener(RefKey())
		self.tfRfc.addKeyListener(RefKey())

		self.setPreferredSize(Dimension(1200, 780))
		self.pack()
		self.setLocationRelativeTo(owner)

		self.loadSites(use_cache=False)

	# ---------- helpers ----------
	def siteKey(self, site):
		return (safe_strip(site.get("gauge_id", "")).upper(), safe_strip(site.get("dss_path", "")))

	def _getSelectedModelRowIndexes(self, table):
		view_rows = table.getSelectedRows()
		if view_rows is None or len(view_rows) == 0:
			return []
		return [table.convertRowIndexToModel(vr) for vr in view_rows]

	def _siteToDssBPart(self, site):
		mode = str(self.cbBMode.getSelectedItem())
		gid = safe_strip(site.get("gauge_id", ""))
		name = safe_strip(site.get("name", ""))
		wfo = safe_strip(site.get("wfo", ""))
		rfc = safe_strip(site.get("rfc", ""))

		if mode == "GAUGE_ID":
			return gid
		if mode == "Name":
			return name
		if mode == "GAUGE_ID (WFO)":
			return "%s (%s)" % (gid, wfo)
		if mode == "GAUGE_ID (RFC)":
			return "%s (%s)" % (gid, rfc)
		return gid

	def _siteToDssPath(self, site):
		a = self.tfA.getText()
		b = self._siteToDssBPart(site)
		f = self.tfF.getText()
		return build_dss_path(a, b, f)

	def _snapshotForStaging(self, site):
		s = dict(site)
		s["dss_path"] = self._siteToDssPath(site)
		return s

	def _blankRow(self):
		return {
			"gauge_id": "",
			"name": "",
			"state": "",
			"wfo": "",
			"rfc": "",
			"lat": "",
			"lon": "",
			"dss_path": "",
		}

	def _updateStatus(self, extra=None):
		base = "Showing %d / %d. Staging list: %d." % (
			len(self.filtered_sites), len(self.all_sites), self.exportModel.getRowCount()
		)
		if extra:
			base = base + " " + extra
		self.lblStatus.setText(base)

	def _siteToBlocks(self, site):
		name = safe_strip(site.get("name", "")).replace("\n", " ").replace("\r", " ")
		block = [
			"GAUGE_ID={0}".format(safe_strip(site.get("gauge_id", "")).upper()),
			"NAME={0}".format(name),
			"STATE={0}".format(safe_strip(site.get("state", "")).upper()),
			"WFO={0}".format(safe_strip(site.get("wfo", "")).upper()),
			"RFC={0}".format(safe_strip(site.get("rfc", "")).upper()),
			"LAT={0}".format(safe_strip(site.get("lat", ""))),
			"LON={0}".format(safe_strip(site.get("lon", ""))),
			"DSS_PATH={0}".format(safe_strip(site.get("dss_path", "")) or self._siteToDssPath(site)),
		]
		return [block]

	# ---------- event factories ----------
	def _onLoad(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.loadSites(use_cache=False)
		return AL()

	def _onClear(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.tfGauge.setText("")
				dialog.tfName.setText("")
				dialog.tfState.setText("")
				dialog.tfWfo.setText("")
				dialog.tfRfc.setText("")
				dialog.applyFilters()
		return AL()

	def _onClose(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.dispose()
		return AL()

	def _onAddSelected(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.addSelectedToStaging()
		return AL()

	def _onAddFiltered(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.addFilteredToStaging()
		return AL()

	def _onAddBlankRow(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.addBlankRowToStaging()
		return AL()

	def _onImport(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.importNwsToStaging()
		return AL()

	def _onRemoveFromList(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.removeSelectedFromStaging()
		return AL()

	def _onClearList(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.exportModel.clear()
				dialog._updateStatus()
		return AL()

	def _onExportList(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.exportStagingToNws()
		return AL()

	# ---------- load/filter ----------
	def loadSites(self, use_cache=False):
		try:
			self.lblStatus.setText("Downloading NWPS gauge list...")
			SwingUtilities.invokeLater(lambda: None)

			txt = download_text(API_URL)
			sites = parse_nwps_gauges_json(txt)

			self.all_sites = sites
			self.applyFilters()
			self.lblStatus.setText("Loaded %d gauges from NWPS." % len(self.all_sites))
		except Exception as ex:
			self.all_sites = []
			self.filtered_sites = []
			self.model.setRows([])
			self.lblStatus.setText("ERROR loading gauge list: %s" % ex)

	def applyFilters(self):
		gauge_q = safe_strip(self.tfGauge.getText()).upper()
		name_q = safe_strip(self.tfName.getText()).upper()
		state_q = safe_strip(self.tfState.getText()).upper()
		wfo_q = safe_strip(self.tfWfo.getText()).upper()
		rfc_q = safe_strip(self.tfRfc.getText()).upper()

		def match(site):
			if gauge_q and gauge_q not in safe_strip(site.get("gauge_id", "")).upper():
				return False
			if name_q and name_q not in safe_strip(site.get("name", "")).upper():
				return False
			if state_q and state_q != safe_strip(site.get("state", "")).upper():
				return False
			if wfo_q and wfo_q != safe_strip(site.get("wfo", "")).upper():
				return False
			if rfc_q and rfc_q != safe_strip(site.get("rfc", "")).upper():
				return False
			return True

		self.filtered_sites = [s for s in self.all_sites if match(s)]
		self.model.setRows(self.filtered_sites)
		self._updateStatus()

	# ---------- staging ops ----------
	def addSelectedToStaging(self):
		idxs = self._getSelectedModelRowIndexes(self.table)
		if not idxs:
			self._updateStatus("No rows selected to add.")
			return
		rows = [self._snapshotForStaging(self.model.getRow(i)) for i in idxs]
		added = self.exportModel.addRowsUnique(rows, self.siteKey)
		self._updateStatus("Added %d (selected), %d already existed." % (added, len(rows) - added))

	def addFilteredToStaging(self):
		if not self.filtered_sites:
			self._updateStatus("No filtered rows to add.")
			return
		rows = [self._snapshotForStaging(s) for s in self.filtered_sites]
		added = self.exportModel.addRowsUnique(rows, self.siteKey)
		self._updateStatus("Added %d (filtered), %d already existed." % (added, len(rows) - added))

	def addBlankRowToStaging(self):
		self.exportModel._rows.append(self._blankRow())
		self.exportModel.fireTableDataChanged()
		self._updateStatus("Added blank row (editable).")

	def importNwsToStaging(self):
		chooser = JFileChooser()
		chooser.setDialogTitle("Open .rfc file to import")
		chooser.setCurrentDirectory(java.io.File(watershed_project_dir_fallback()))

		chooser.setAcceptAllFileFilterUsed(True)
		chooser.resetChoosableFileFilters()
		ff = FileNameExtensionFilter("RFC gauge list (*.rfc)", ["rfc"])
		chooser.addChoosableFileFilter(ff)
		chooser.setFileFilter(ff)

		rc = chooser.showOpenDialog(self)
		if rc != JFileChooser.APPROVE_OPTION:
			self._updateStatus("Import canceled.")
			return

		in_file = chooser.getSelectedFile()
		path = in_file.getAbsolutePath()

		try:
			with open(path, "rb") as f:
				data = f.read()
			try:
				text = data.decode("utf-8", "replace")
			except:
				text = str(data)

			rows = parse_nws_file_text(text)
			if not rows:
				self._updateStatus("No blocks found in: %s" % path)
				return

			added = self.exportModel.addRowsUnique(rows, self.siteKey)
			self._updateStatus("Imported %d row(s) from %s (%d duplicates skipped)." % (added, path, len(rows) - added))
		except Exception as ex:
			self._updateStatus("ERROR importing %s: %s" % (path, ex))

	def removeSelectedFromStaging(self):
		idxs = self._getSelectedModelRowIndexes(self.exportTable)
		if not idxs:
			self._updateStatus("No staging rows selected to remove.")
			return
		rows = [self.exportModel.getRow(i) for i in idxs]
		keys = set([self.siteKey(r) for r in rows])
		removed = self.exportModel.removeRowsByKeys(keys, self.siteKey)
		self._updateStatus("Removed %d from staging list." % removed)

	# ---------- export ----------
	def exportStagingToNws(self):
		rows_to_export = self.exportModel.getRows()[:]
		if not rows_to_export:
			self._updateStatus("Staging list is empty; nothing to export.")
			return

		chooser = JFileChooser()
		chooser.setDialogTitle("Save .rfc file")
		chooser.setCurrentDirectory(java.io.File(watershed_project_dir_fallback()))

		chooser.setAcceptAllFileFilterUsed(True)
		chooser.resetChoosableFileFilters()
		ff = FileNameExtensionFilter("RFC gauge list (*.rfc)", ["rfc"])
		chooser.addChoosableFileFilter(ff)
		chooser.setFileFilter(ff)

		default_dir = watershed_project_dir_fallback()
		default_name = "{0}.rfc".format(str(RTS.getWatershed()))
		chooser.setSelectedFile(java.io.File(os.path.join(default_dir, default_name)))

		rc = chooser.showSaveDialog(self)
		if rc != JFileChooser.APPROVE_OPTION:
			self._updateStatus("Export canceled.")
			return

		out_file = chooser.getSelectedFile()
		path = out_file.getAbsolutePath()
		if not path.lower().endswith(".rfc"):
			path = path + ".rfc"

		try:
			with open(path, "wb") as f:
				f.write(("# Exported from NWS RFC (NWPS) Sites Filter\n").encode("utf-8"))
				f.write(("# Source: %s\n" % API_URL).encode("utf-8"))
				f.write(("# DSS template: /A-Part/B-Part////F-Part/\n").encode("utf-8"))
				f.write(("\n").encode("utf-8"))

				for site in rows_to_export:
					blocks = self._siteToBlocks(site)
					for block in blocks:
						for line in block:
							f.write((line + "\n").encode("utf-8"))
						f.write(("\n").encode("utf-8"))

			self._updateStatus("Exported %d gauge(s) to %s" % (len(rows_to_export), path))
		except Exception as ex:
			self._updateStatus("ERROR exporting: %s" % ex)


def main():
	f = JFrame("Owner")
	f.setUndecorated(True)
	f.setSize(0, 0)
	f.setLocationRelativeTo(None)

	dlg = NwsSitesDialog(f)
	dlg.setVisible(True)


if __name__ == "__main__":
	SwingUtilities.invokeLater(main)
