# -------------------------------------------------------------------
# Extract RFC (NWPS) Config Builder (Jython)
#
# Creates/edits a .config file that stores:
#   - path to an RFC site list (.rfc)
#   - path to a TimeSeries.dss file
#
# Intended for use inside HEC-RTS Jython environment.
# -------------------------------------------------------------------

from java.awt					import BorderLayout, GridBagLayout, GridBagConstraints, Insets
from java.awt.event				import ActionListener
from javax.swing				import JDialog, JPanel, JLabel, JTextField, JButton, JFileChooser, JOptionPane, SwingUtilities
from javax.swing.filechooser	import FileNameExtensionFilter
from hec2.rts.script			import RTS
import os, java.io

CONFIG_VERSION = "1"
DEFAULT_CONFIG_NAME = "extract_rfc.config"

# Watershed context
WATERSHED_NAME = str(RTS.getWatershed())
PROJ_DIR = RTS.getWatershed().getProjectDirectory()
CWMS_HOME = os.path.normpath(os.path.join(PROJ_DIR, "..", ".."))

# Default .rfc location: <projectDir>\shared\source\<Watershed>.rfc
DEFAULT_RFC_PATH = os.path.join(PROJ_DIR, "shared", "source", WATERSHED_NAME + ".rfc")
# Default DSS location: <cwms_home>\database\RFC_Data\<Watershed>_TimeSeries.dss
DEFAULT_DSS_PATH = os.path.join(CWMS_HOME, "database", "RFC_Data", WATERSHED_NAME + "_TimeSeries.dss")


def _abs_norm(p):
	if p is None:
		return ""
	p = p.strip()
	if not p:
		return ""
	return os.path.abspath(p)


def load_config(config_path):
	data = {
		"version": CONFIG_VERSION,
		"rfc_file": "",
		"dss_file": "",
	}

	if not config_path or (not os.path.isfile(config_path)):
		return data

	f = None
	try:
		f = open(config_path, "r")
		for raw in f:
			line = raw.strip()
			if not line or line.startswith("#"):
				continue
			if "=" not in line:
				continue
			k, v = line.split("=", 1)
			k = k.strip()
			v = v.strip()
			if k in data:
				data[k] = v
	finally:
		if f:
			f.close()

	return data


def save_config(config_path, rfc_file, dss_file):
	rfc_file = _abs_norm(rfc_file)
	dss_file = _abs_norm(dss_file)

	f = None
	try:
		f = open(config_path, "w")
		f.write("# RFC (NWPS) extract paths config\n")
		f.write("version={0}\n".format(CONFIG_VERSION))
		f.write("rfc_file={0}\n".format(rfc_file))
		f.write("dss_file={0}\n".format(dss_file))
	finally:
		if f:
			f.close()


def choose_file(parent, title, extensions, desc, initial_path=None, directories_only=False, save_dialog=False):
	fc = JFileChooser()

	if initial_path:
		try:
			if os.path.isdir(initial_path):
				fc.setCurrentDirectory(java.io.File(initial_path))
			elif os.path.isfile(initial_path):
				fc.setSelectedFile(java.io.File(initial_path))
				fc.setCurrentDirectory(java.io.File(os.path.dirname(initial_path)))
		except:
			pass

	fc.setDialogTitle(title)

	if directories_only:
		fc.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)
	else:
		if extensions:
			fc.setFileFilter(FileNameExtensionFilter(desc, extensions))

	rc = fc.showSaveDialog(parent) if save_dialog else fc.showOpenDialog(parent)
	if rc == JFileChooser.APPROVE_OPTION:
		return str(fc.getSelectedFile().getAbsolutePath())
	return None


class RFCConfigDialog(JDialog):
	def __init__(self, parent, config_path):
		JDialog.__init__(self, parent, "RFC (NWPS) Paths Configuration", True)
		self.config_path = config_path

		loaded = load_config(config_path)
		
		rfc_default = loaded.get("rfc_file", "").strip() or DEFAULT_RFC_PATH
		dss_default = loaded.get("dss_file", "").strip() or DEFAULT_DSS_PATH

		self.rfcField = JTextField(rfc_default, 45)
		self.dssField = JTextField(dss_default, 45)

		self._build_ui(parent)
		self.pack()
		self.setLocationRelativeTo(parent)

	def _build_ui(self, parent):
		panel = JPanel(GridBagLayout())
		gbc = GridBagConstraints()
		gbc.insets = Insets(6, 6, 6, 6)
		gbc.fill = GridBagConstraints.HORIZONTAL

		# Row 0: config path label
		gbc.gridx = 0
		gbc.gridy = 0
		gbc.gridwidth = 3
		panel.add(JLabel("Config file: {0}".format(self.config_path)), gbc)

		# Row 1: RFC list file
		gbc.gridwidth = 1
		gbc.gridy = 1
		gbc.gridx = 0
		panel.add(JLabel("Select RFC list (.rfc) file:"), gbc)

		gbc.gridx = 1
		panel.add(self.rfcField, gbc)

		btnBrowseRFC = JButton("Browse...")
		gbc.gridx = 2
		panel.add(btnBrowseRFC, gbc)

		# Row 2: DSS file
		gbc.gridy = 2
		gbc.gridx = 0
		panel.add(JLabel("Select output DSS file:"), gbc)

		gbc.gridx = 1
		panel.add(self.dssField, gbc)

		btnBrowseDSS = JButton("Browse...")
		gbc.gridx = 2
		panel.add(btnBrowseDSS, gbc)

		# Row 3: Buttons
		btnPanel = JPanel()
		btnSave = JButton("Save")
		btnCancel = JButton("Cancel")
		btnPanel.add(btnSave)
		btnPanel.add(btnCancel)

		# Wiring actions
		class BrowseRFC(ActionListener):
			def actionPerformed(self, event):
				initial = self_outer.rfcField.getText().strip()
				if not initial:
					initial = os.path.join(PROJ_DIR, "shared", "source")
				path = choose_file(
					self_outer,
					"Select RFC list (.rfc) file",
					["rfc"],
					"RFC List (*.rfc)",
					initial_path=initial,
					directories_only=False,
					save_dialog=False
				)
				if path:
					self_outer.rfcField.setText(path)

		class BrowseDSS(ActionListener):
			def actionPerformed(self, event):
				initial = self_outer.dssField.getText().strip()
				if not initial:
					initial = PROJ_DIR
				path = choose_file(
					self_outer,
					"Select DSS file",
					["dss"],
					"HEC-DSS File (*.dss)",
					initial_path=initial,
					directories_only=False,
					save_dialog=False
				)
				if path:
					self_outer.dssField.setText(path)

		class SaveAction(ActionListener):
			def actionPerformed(self, event):
				rfc_path = _abs_norm(self_outer.rfcField.getText())
				dss_path = _abs_norm(self_outer.dssField.getText())

				# Basic validation
				if (not rfc_path) or (not rfc_path.lower().endswith(".rfc")):
					JOptionPane.showMessageDialog(self_outer, "Please select a valid .rfc file.", "Validation", JOptionPane.WARNING_MESSAGE)
					return
				if not os.path.isfile(rfc_path):
					JOptionPane.showMessageDialog(self_outer, "The .rfc file does not exist:\n{0}".format(rfc_path), "Validation", JOptionPane.WARNING_MESSAGE)
					return

				if (not dss_path) or (not dss_path.lower().endswith(".dss")):
					JOptionPane.showMessageDialog(self_outer, "Please select a valid .dss file.", "Validation", JOptionPane.WARNING_MESSAGE)
					return

				# Create directory for config file if needed
				cfg_dir = os.path.dirname(self_outer.config_path)
				if cfg_dir and (not os.path.isdir(cfg_dir)):
					try:
						os.makedirs(cfg_dir)
					except Exception as e:
						JOptionPane.showMessageDialog(self_outer, "Could not create config directory:\n{0}\n\n{1}".format(cfg_dir, e), "Error", JOptionPane.ERROR_MESSAGE)
						return

				try:
					save_config(self_outer.config_path, rfc_path, dss_path)
				except Exception as e:
					JOptionPane.showMessageDialog(self_outer, "Failed to save config:\n{0}".format(e), "Error", JOptionPane.ERROR_MESSAGE)
					return

				JOptionPane.showMessageDialog(self_outer, "Saved:\n{0}".format(self_outer.config_path), "Saved", JOptionPane.INFORMATION_MESSAGE)
				self_outer.dispose()

		class CancelAction(ActionListener):
			def actionPerformed(self, event):
				self_outer.dispose()

		self_outer = self
		btnBrowseRFC.addActionListener(BrowseRFC())
		btnBrowseDSS.addActionListener(BrowseDSS())
		btnSave.addActionListener(SaveAction())
		btnCancel.addActionListener(CancelAction())

		self.getContentPane().setLayout(BorderLayout())
		self.getContentPane().add(panel, BorderLayout.CENTER)
		self.getContentPane().add(btnPanel, BorderLayout.SOUTH)


def run_dialog(config_path, parent=None):
	dlg = RFCConfigDialog(parent, config_path)
	dlg.setVisible(True)


# -------------------
# Choose config path
# -------------------
config_path = os.path.join(PROJ_DIR, "shared", "source", DEFAULT_CONFIG_NAME)

SwingUtilities.invokeLater(lambda: run_dialog(config_path, None))
