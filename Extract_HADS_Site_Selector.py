# USGS HADS Sites Filter + staging list exporter
#
# Features:
# - Load/filter USGS HADS sites per state
# - Staging list with DSS_PATH snapshotted on add
# - Staging list supports editing ALL columns (ad-hoc/manual entries)
# - Add Blank Row for ad-hoc/manual entries
# - NEW: Import/Open existing .config file and append entries to staging list
#
# Export writes key=value blocks:
#   NWS_ID=...
#   USGS_ID=...
#   GOES_ID=...
#   HSA=...
#   LAT=...
#   LON=...
#   NAME=...
#   DSS_PATH=...

from __future__					import print_function
from java.awt					import BorderLayout, Dimension, FlowLayout
from java.awt.event				import ActionListener, KeyAdapter
from javax.swing				import (JButton, JCheckBox, JComboBox, JDialog, JFrame,
										JLabel, JPanel, JScrollPane, JTable, JTextField,
										SwingUtilities, JFileChooser, JSplitPane)
from javax.swing.filechooser	import FileNameExtensionFilter
from javax.swing.table			import AbstractTableModel
from hec2.rts.script			import RTS
import java.io, sys, os, re, urllib2


BASE_URL = "https://hads.ncep.noaa.gov/USGS/%s_USGS-HADS_SITES.txt"

STATE_CODES = [
	"ALL",
	"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
	"HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
	"MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
	"NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
	"SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"
]

BPART_MODES = ["NWS_ID", "USGS_ID", "NWS_ID (USGS_ID)", "Name"]


def watershed_project_dir_fallback():
	try:
		proj_dir = RTS.getWatershed().getProjectDirectory()
		target = os.path.join(proj_dir, "shared", "source")
		if not os.path.isdir(target):
			os.makedirs(target)
		return target
	except:
		return SCRIPT_DIR


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


def safe_strip(s):
	return s.strip() if s is not None else ""


def download_text(url):
	req = urllib2.Request(url, headers={"User-Agent": "JythonSwing/1.0"})
	resp = urllib2.urlopen(req, timeout=30)
	data = resp.read()
	try:
		return data.decode("utf-8", "replace")
	except:
		return data


def parse_hads_sites(text):
	sites = []
	for raw_line in text.splitlines():
		line = raw_line.rstrip("\r\n")
		if not line or "|" not in line:
			continue

		parts = [p.strip() for p in line.split("|")]
		if len(parts) < 7:
			continue

		nws_id = parts[0]
		if nws_id.upper().startswith("NWS"):
			continue
		if len(nws_id) < 3:
			continue

		sites.append({
			"nws_id": safe_strip(parts[0]),
			"usgs_id": safe_strip(parts[1]),
			"goes_id": safe_strip(parts[2]),
			"hsa": safe_strip(parts[3]),
			"lat_raw": safe_strip(parts[4]),
			"lon_raw": safe_strip(parts[5]),
			"name": safe_strip(parts[6]),
			"dss_path": "",
		})
	return sites


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


def set_table_column_widths(table, widths):
	cm = table.getColumnModel()
	for i in range(min(len(widths), cm.getColumnCount())):
		col = cm.getColumn(i)
		col.setPreferredWidth(int(widths[i]))
		col.setMinWidth(20)


def parse_config_file_text(text):
	rows = []
	cur = {}
	def push_cur():
		if not cur:
			return
		row = {
			"nws_id": safe_strip(cur.get("NWS_ID", "")),
			"usgs_id": safe_strip(cur.get("USGS_ID", "")),
			"goes_id": safe_strip(cur.get("GOES_ID", "")),
			"hsa": safe_strip(cur.get("HSA", "")),
			"lat_raw": safe_strip(cur.get("LAT", "")),
			"lon_raw": safe_strip(cur.get("LON", "")),
			"name": safe_strip(cur.get("NAME", "")),
			"dss_path": safe_strip(cur.get("DSS_PATH", "")),
		}
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
	COLS = ["NWS ID", "USGS ID", "GOES", "HSA", "Latitude", "Longitude", "Name"]

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
		if col == 0: return r.get("nws_id", "")
		if col == 1: return r.get("usgs_id", "")
		if col == 2: return r.get("goes_id", "")
		if col == 3: return r.get("hsa", "")
		if col == 4: return r.get("lat_raw", "")
		if col == 5: return r.get("lon_raw", "")
		if col == 6: return r.get("name", "")
		return ""


class ExportSitesTableModel(SitesTableModel):
	COLS = ["NWS ID", "USGS ID", "GOES", "HSA", "Latitude", "Longitude", "Name", "DSS_PATH"]
	KEYS = ["nws_id", "usgs_id", "goes_id", "hsa", "lat_raw", "lon_raw", "name", "dss_path"]

	def __init__(self, rows):
		SitesTableModel.__init__(self, rows)

	def getColumnCount(self):
		return len(self.COLS)

	def getColumnName(self, col):
		return self.COLS[col]

	def getValueAt(self, row, col):
		r = self._rows[row]
		k = self.KEYS[col]
		return r.get(k, "")

	def isCellEditable(self, row, col):
		return True

	def setValueAt(self, value, row, col):
		r = self._rows[row]
		k = self.KEYS[col]
		r[k] = safe_strip(value)
		self.fireTableCellUpdated(row, col)

	def refresh(self):
		self.fireTableDataChanged()


class HadsSitesDialog(JDialog):
	def __init__(self, owner=None):
		JDialog.__init__(self, owner, "USGS HADS Sites Filter", True)
		self.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE)

		self.all_sites = []
		self.filtered_sites = []
		self.cache = {}

		# --- Filters panel ---
		filters = JPanel(FlowLayout(FlowLayout.LEFT))

		self.cbState = JComboBox(STATE_CODES)
		self.tfNws = JTextField(6)
		self.tfUsgs = JTextField(10)
		self.tfHsa = JTextField(4)
		self.tfName = JTextField(18)
		self.cbNameEndsWithState = JCheckBox("Name ends w/ state code", False)

		filters.add(JLabel("State:"))
		filters.add(self.cbState)
		filters.add(JLabel("NWS ID:"))
		filters.add(self.tfNws)
		filters.add(JLabel("USGS ID:"))
		filters.add(self.tfUsgs)
		filters.add(JLabel("HSA:"))
		filters.add(self.tfHsa)
		filters.add(JLabel("Name contains:"))
		filters.add(self.tfName)
		filters.add(self.cbNameEndsWithState)

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
		self.tfF.setText("HADS")

		dss.add(JLabel("DSS A (Watershed, optional):"))
		dss.add(self.tfA)
		dss.add(JLabel("DSS B (Location):"))
		dss.add(self.cbBMode)
		dss.add(JLabel("DSS F (Source):"))
		dss.add(self.tfF)

		# no refresh on A/F/B changes (paths snapshot on add)
		dialog = self
		class DssKey(KeyAdapter):
			def keyReleased(_, e):
				pass
		self.tfA.addKeyListener(DssKey())
		self.tfF.addKeyListener(DssKey())
		self.cbBMode.addActionListener(self._onDssTemplateChanged())

		# --- Main results table ---
		self.model = SitesTableModel([])
		self.table = JTable(self.model)
		self.table.setAutoCreateRowSorter(True)
		set_table_column_widths(self.table, [80, 90, 85, 55, 80, 90, 420])
		scroller = JScrollPane(self.table)
		scroller.setPreferredSize(Dimension(1100, 300))

		# --- Staging list table ---
		self.exportModel = ExportSitesTableModel([])
		self.exportTable = JTable(self.exportModel)
		self.exportTable.setAutoCreateRowSorter(True)
		set_table_column_widths(self.exportTable, [80, 90, 85, 55, 80, 90, 320, 420])
		exportScroller = JScrollPane(self.exportTable)
		exportScroller.setPreferredSize(Dimension(1100, 220))

		# --- Staging buttons ---
		stage_btns = JPanel(FlowLayout(FlowLayout.LEFT))
		self.btnAddSelected = JButton("Add Selected")
		self.btnAddFiltered = JButton("Add Filtered")
		self.btnAddBlankRow = JButton("Add Blank Row")
		self.btnImportConfig = JButton("Open HADS list...")
		self.btnRemoveFromList = JButton("Remove Selected from List")
		self.btnClearList = JButton("Clear List")
		self.btnExportList = JButton("Export List...")

		stage_btns.add(self.btnAddSelected)
		stage_btns.add(self.btnAddFiltered)
		stage_btns.add(self.btnAddBlankRow)
		stage_btns.add(self.btnImportConfig)
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
		split.setResizeWeight(0.62)

		self.lblStatus = JLabel("Ready.")

		self.getContentPane().setLayout(BorderLayout())
		self.getContentPane().add(top, BorderLayout.NORTH)
		self.getContentPane().add(split, BorderLayout.CENTER)
		self.getContentPane().add(self.lblStatus, BorderLayout.SOUTH)

		# Events
		self.btnLoad.addActionListener(self._onLoad())
		self.btnClear.addActionListener(self._onClear())
		self.btnClose.addActionListener(self._onClose())
		self.cbState.addActionListener(self._onStateChanged())

		self.btnAddSelected.addActionListener(self._onAddSelected())
		self.btnAddFiltered.addActionListener(self._onAddFiltered())
		self.btnAddBlankRow.addActionListener(self._onAddBlankRow())
		self.btnImportConfig.addActionListener(self._onImportConfig())
		self.btnRemoveFromList.addActionListener(self._onRemoveFromList())
		self.btnClearList.addActionListener(self._onClearList())
		self.btnExportList.addActionListener(self._onExportList())

		class RefKey(KeyAdapter):
			def keyReleased(_, e):
				dialog.applyFilters()

		self.tfNws.addKeyListener(RefKey())
		self.tfUsgs.addKeyListener(RefKey())
		self.tfHsa.addKeyListener(RefKey())
		self.tfName.addKeyListener(RefKey())
		self.cbNameEndsWithState.addActionListener(self._onAnyFilterChanged())

		self.setPreferredSize(Dimension(1200, 780))
		self.pack()
		self.setLocationRelativeTo(owner)

		self.loadDataForSelectedState(use_cache=True)

	# ---------- helpers ----------
	def selectedState(self):
		return str(self.cbState.getSelectedItem())

	def makeUrlForState(self, state_code):
		return BASE_URL % state_code

	def siteKey(self, site):
		# dedupe key for imported + selected entries
		return (site.get("nws_id", ""), site.get("usgs_id", ""), site.get("goes_id", ""), site.get("dss_path", ""))

	def _onDssTemplateChanged(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				pass
		return AL()

	def _getSelectedModelRowIndexes(self, table):
		view_rows = table.getSelectedRows()
		if view_rows is None or len(view_rows) == 0:
			return []
		return [table.convertRowIndexToModel(vr) for vr in view_rows]

	def _siteToConfigBlocks(self, site):
		name = safe_strip(site.get("name", "")).replace("\n", " ").replace("\r", " ")
		nws_id  = safe_strip(site.get("nws_id", ""))
		usgs_id = safe_strip(site.get("usgs_id", ""))
		goes_id = safe_strip(site.get("goes_id", ""))
		hsa     = safe_strip(site.get("hsa", ""))
		lat     = safe_strip(site.get("lat_raw", ""))
		lon     = safe_strip(site.get("lon_raw", ""))
		dss_path = safe_strip(site.get("dss_path", ""))
		if not dss_path:
			dss_path = self._siteToDssPath(site)

		block = [
			"NWS_ID={0}".format(nws_id),
			"USGS_ID={0}".format(usgs_id),
			"GOES_ID={0}".format(goes_id),
			"HSA={0}".format(hsa),
			"LAT={0}".format(lat),
			"LON={0}".format(lon),
			"NAME={0}".format(name),
			"DSS_PATH={0}".format(dss_path),
		]
		return [block]

	def _siteToDssBPart(self, site):
		mode = str(self.cbBMode.getSelectedItem())
		if mode == "NWS_ID":
			return site.get("nws_id", "")
		if mode == "USGS_ID":
			return site.get("usgs_id", "")
		if mode == "NWS_ID (USGS_ID)":
			return "%s (%s)" % (site.get("nws_id", ""), site.get("usgs_id", ""))
		if mode == "Name":
			return site.get("name", "")
		return site.get("nws_id", "")

	def _siteToDssPath(self, site):
		a = self.tfA.getText()
		b = self._siteToDssBPart(site)
		f = self.tfF.getText()
		return build_dss_path(a, b, f)

	def _snapshotSiteForStaging(self, site):
		s = dict(site)
		s["dss_path"] = self._siteToDssPath(site)
		return s

	def _blankSiteRow(self):
		return {
			"nws_id": "",
			"usgs_id": "",
			"goes_id": "",
			"hsa": "",
			"lat_raw": "",
			"lon_raw": "",
			"name": "",
			"dss_path": "",
		}

	def _updateStatus(self, extra=None):
		base = "Showing %d / %d (state=%s). Staging list: %d." % (
			len(self.filtered_sites), len(self.all_sites), self.selectedState().upper(), self.exportModel.getRowCount()
		)
		if extra:
			base = base + " " + extra
		self.lblStatus.setText(base)

	# ---------- event factories ----------
	def _onLoad(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.loadDataForSelectedState(use_cache=False)
		return AL()

	def _onClear(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.tfNws.setText("")
				dialog.tfUsgs.setText("")
				dialog.tfHsa.setText("")
				dialog.tfName.setText("")
				dialog.cbNameEndsWithState.setSelected(False)
				dialog.applyFilters()
		return AL()

	def _onClose(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.dispose()
		return AL()

	def _onStateChanged(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.loadDataForSelectedState(use_cache=True)
		return AL()

	def _onAnyFilterChanged(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.applyFilters()
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

	def _onImportConfig(self):
		dialog = self
		class AL(ActionListener):
			def actionPerformed(self, e):
				dialog.importConfigToStaging()
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
				dialog.exportStagingListToConfig()
		return AL()

	# ---------- data loading / filtering ----------
	def loadDataForSelectedState(self, use_cache=True):
		state_code = self.selectedState()

		if use_cache and state_code in self.cache:
			self.all_sites = self.cache[state_code]
			self.applyFilters()
			self.lblStatus.setText("Loaded %d sites from cache for %s." % (len(self.all_sites), state_code))
			return
		url = self.makeUrlForState(state_code)
		try:
			self.lblStatus.setText("Downloading %s ..." % url)
			SwingUtilities.invokeLater(lambda: None)
			text = download_text(url)
			sites = parse_hads_sites(text)
			self.cache[state_code] = sites
			self.all_sites = sites
			self.applyFilters()
			self.lblStatus.setText("Loaded %d sites for %s." % (len(self.all_sites), state_code))
		except Exception as ex:
			self.all_sites = []
			self.filtered_sites = []
			self.model.setRows([])
			self.lblStatus.setText("ERROR loading %s: %s" % (url, ex))

	def applyFilters(self):
		nws_q = safe_strip(self.tfNws.getText()).upper()
		usgs_q = safe_strip(self.tfUsgs.getText())
		hsa_q = safe_strip(self.tfHsa.getText()).upper()
		name_q = safe_strip(self.tfName.getText()).upper()
		state_code = self.selectedState().upper()
		require_name_state = self.cbNameEndsWithState.isSelected()

		def match(site):
			if nws_q and nws_q not in site["nws_id"].upper():
				return False
			if usgs_q and usgs_q not in site["usgs_id"]:
				return False
			if hsa_q and hsa_q not in site["hsa"].upper():
				return False
			if name_q and name_q not in site["name"].upper():
				return False
			if require_name_state and state_code != "ALL":
				if not site["name"].upper().endswith(" " + state_code):
					return False
			return True

		self.filtered_sites = [s for s in self.all_sites if match(s)]
		self.model.setRows(self.filtered_sites)
		self._updateStatus()

	# ---------- staging list ops ----------
	def addSelectedToStaging(self):
		idxs = self._getSelectedModelRowIndexes(self.table)
		if not idxs:
			self._updateStatus("No rows selected to add.")
			return
		rows = [self._snapshotSiteForStaging(self.model.getRow(i)) for i in idxs]
		added = self.exportModel.addRowsUnique(rows, self.siteKey)
		self._updateStatus("Added %d (selected), %d already existed." % (added, len(rows) - added))

	def addFilteredToStaging(self):
		if not self.filtered_sites:
			self._updateStatus("No filtered rows to add.")
			return
		rows = [self._snapshotSiteForStaging(s) for s in self.filtered_sites]
		added = self.exportModel.addRowsUnique(rows, self.siteKey)
		self._updateStatus("Added %d (filtered), %d already existed." % (added, len(rows) - added))

	def addBlankRowToStaging(self):
		row = self._blankSiteRow()
		self.exportModel._rows.append(row)
		self.exportModel.fireTableDataChanged()
		last = self.exportModel.getRowCount() - 1
		if last >= 0:
			try:
				self.exportTable.getSelectionModel().setSelectionInterval(last, last)
				rect = self.exportTable.getCellRect(last, 0, True)
				self.exportTable.scrollRectToVisible(rect)
			except:
				pass
		self._updateStatus("Added blank row (editable).")

	def importConfigToStaging(self):
		chooser = JFileChooser()
		chooser.setDialogTitle("Open .hads file to import")
		chooser.setCurrentDirectory(java.io.File(watershed_project_dir_fallback()))
		chooser.setAcceptAllFileFilterUsed(True)
		chooser.resetChoosableFileFilters()
		chooser.addChoosableFileFilter(FileNameExtensionFilter("HADS list (*.hads)", ["hads"]))
		chooser.setFileFilter(FileNameExtensionFilter("HADS list (*.hads)", ["hads"]))
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
			rows = parse_config_file_text(text)
			if not rows:
				self._updateStatus("No blocks found in config: %s" % path)
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
	def exportStagingListToConfig(self):
		rows_to_export = self.exportModel.getRows()[:]
		if not rows_to_export:
			self._updateStatus("Staging list is empty; nothing to export.")
			return
		chooser = JFileChooser()
		chooser.setDialogTitle("Save .config file")
		chooser.setCurrentDirectory(java.io.File(watershed_project_dir_fallback()))
		default_dir = watershed_project_dir_fallback()
		default_name = "{0}.hads".format(str(RTS.getWatershed()))
		chooser.setSelectedFile(java.io.File(os.path.join(default_dir, default_name)))
		rc = chooser.showSaveDialog(self)
		if rc != JFileChooser.APPROVE_OPTION:
			self._updateStatus("Export canceled.")
			return
		out_file = chooser.getSelectedFile()
		path = out_file.getAbsolutePath()
		if not path.lower().endswith(".hads"):
			path = path + ".hads"
		try:
			with open(path, "wb") as f:
				f.write(("# Exported from USGS HADS Sites Filter\n").encode("utf-8"))
				f.write(("# Source URL (current state): %s\n" % self.makeUrlForState(self.selectedState())).encode("utf-8"))
				f.write(("# DSS template: /A-Part/B-Part////F-Part/\n").encode("utf-8"))
				f.write(("\n").encode("utf-8"))

				for site in rows_to_export:
					blocks = self._siteToConfigBlocks(site)
					for block in blocks:
						for line in block:
							f.write((line + "\n").encode("utf-8"))
						f.write(("\n").encode("utf-8"))

			self._updateStatus("Exported %d site(s) to %s" % (len(rows_to_export), path))
		except Exception as ex:
			self._updateStatus("ERROR exporting: %s" % ex)

def main():
	f = JFrame("Owner")
	f.setUndecorated(True)
	f.setSize(0, 0)
	f.setLocationRelativeTo(None)

	dlg = HadsSitesDialog(f)
	dlg.setVisible(True)

if __name__ == "__main__":
	SwingUtilities.invokeLater(main)
