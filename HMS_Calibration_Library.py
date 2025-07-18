from	javax.swing				import	JDialog, JLabel, JScrollPane, JList, JButton, JTextField, SpringLayout, ScrollPaneConstants, JCheckBox, JOptionPane, JFileChooser
from	javax.swing.filechooser	import	FileNameExtensionFilter
from	java.awt				import	Frame, Dialog, Dimension, Window, GraphicsConfiguration, Font
from	java.awt.event			import	ActionListener, ItemListener, ItemEvent
from	java.io					import	File
from	hec.dssgui				import	ListSelection
from	hec.script				import	MessageBox
from	hec.heclib.dss			import	HecDss
from	hec.heclib.util			import	HecTime
from	com.rma.client			import	Browser
from	hec2.rts.script			import	RTS
import glob, shutil, re

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

## Get the current forecast ##
frame = Browser.getBrowser().getBrowserFrame()
proj = frame.getCurrentProject()
pane = frame.getTabbedPane()
tab = pane.getSelectedComponent()
chktab(tab)
fcst = tab.getForecast()
chkfcst(fcst)
dssfile = fcst.getOutDssPath()
fcstTimeWindowString = str(fcst.getRunTimeWindow())
cwmsFile = HecDss.open(dssfile)

## Watershed name for use in defining base directory path
Watershed = str(RTS.getWatershed())
	
## print 'fcstTimeWindowString : %s' %(fcstTimeWindowString)
important_times = [ i.strip(' ') for i in fcstTimeWindowString.split(';') ]
start_time, forecast_time, end_time = important_times[0], important_times[1], important_times[2]

## Forecast Time for default naming for exporting
fcst_time = HecTime()
fcst_time.set(forecast_time)
fcst_time1 = fcst_time.dateAndTime(104)
fcst_time_string1 = str(fcst_time1)
fcst_time_string = fcst_time_string1.replace(",", "").replace(":", "")

## Define forecast directory
dssFileName = fcst.getForecastDSSFilename()
forecastDirectory = str(os.path.dirname(dssFileName))

## Find HMS active forecast calibration file
ActiveFcst = tab.getActiveForecastRun()
ActiveAlts = ActiveFcst.getModelAlternatives("HMS")
print ActiveAlts
No_ActiveRSSAlts = len(ActiveAlts)
if No_ActiveRSSAlts > 1:
	SelectedHMSAlt = JOptionPane.showInputDialog(None,"Select ResSim Alternative","ResSim Alternative",JOptionPane.PLAIN_MESSAGE,None,ActiveAlts,ActiveAlts[0])
else:
	SelectedHMSAlt = ActiveAlts[0]
ActiveHMSAlt = (str(SelectedHMSAlt)
	.replace(" ","_")
	.replace("-","_")
	.replace("!","_")
	.replace("@","_")
	.replace("#","_")
	.replace("$","_")
	.replace("%","_")
	.replace("^","_")
	.replace("&","_")
	.replace("*","_")
	.replace("(","_")
	.replace(")","_")
	.replace("[","_")
	.replace("]","_")
	.replace("{","_")
	.replace("}","_")
	.replace(":","_")
	.replace("|","_"))
print("Active HMS Alternative: "+ActiveHMSAlt)
Current_HMS_fcstFileName1 = os.path.join(forecastDirectory,'hms\\forecast', ""+ActiveHMSAlt+".forecast")
Current_HMS_fcstFileName2 = Current_HMS_fcstFileName1.replace("\\", "/")
Current_HMS_fcstFileName = Current_HMS_fcstFileName2.replace(",", "")

## Check is calibration_library folder exists in base hms/forecast directory
Calibration_Library_Directory_os = os.path.join(forecastDirectory,'..\\..\\..\\watershed\\'+Watershed+'\\hms\\forecast\\calibration_library')
Calibration_Library_Directory = Calibration_Library_Directory_os.replace("\\", "/")
if os.path.exists(Calibration_Library_Directory) :
	print("calibration_library directory exists")
else :
	print("calibration_library directory does not exists.  hms/forecast/calibration_library directory created in base watershed.")
	os.makedirs(Calibration_Library_Directory)
	
if os.path.exists(Calibration_Library_Directory + '/Remote_Calibration_Library_Directory.txt') :
	print("directory file exists")
else :
	print("directory file does not exists.  directory file created.")
	remote_directory_file = open(Calibration_Library_Directory + '/Remote_Calibration_Library_Directory.txt',"w")
	remote_directory_file.write("Not Defined")
	remote_directory_file.close()

remote_library_directory_file_r = open(Calibration_Library_Directory + '/Remote_Calibration_Library_Directory.txt',"r")
remote_library_directory = remote_library_directory_file_r.read(200)
remote_library_directory_file_r.close()

def	copy_file(src_name, dst_name):
	with open(dst_name, "wb") as dst:
		with open(src_name, "rb") as src:
			dst.write(src.read())

def close_pushed(event):
	print("Close Button Pushed")
	theDialog.dispose()
	
class HMS_Cal_Lib_Dialog(JDialog, ActionListener):

	def __init__(self, owner=None, title="", modal=False, modalityType=None, gc=None):
		global theDialog
		# Call the superclass constructor with different arguments based on provided values
		if isinstance(owner, Frame):
			super(HMS_Cal_Lib_Dialog, self).__init__(owner, title, modal, gc)
		elif isinstance(owner, Dialog):
			super(HMS_Cal_Lib_Dialog, self).__init__(owner, title, modal, gc)
		elif isinstance(owner, Window):
			super(HMS_Cal_Lib_Dialog, self).__init__(owner, title, modalityType, gc)
		else:
			super(HMS_Cal_Lib_Dialog, self).__init__()
		

################## Stection-Start ####################################################################
################################
####	Create Java Dialog	####
################################
		##	Layout settings
		spring_layout = SpringLayout()
		self.getContentPane().setLayout(spring_layout)

		##	Close Button
		btn_close = JButton("Close")
		btn_close.addActionListener(close_pushed)
		spring_layout.putConstraint(SpringLayout.SOUTH, btn_close, -10, SpringLayout.SOUTH, self.getContentPane())
		self.getContentPane().add(btn_close)
		
		####################################
		####	New Section of Dialog	####
		####################################
		##	Calibration Library Directory Section Lable
		lbl_calibration_library_directory = JLabel("Calibration Library Directory")
		spring_layout.putConstraint(SpringLayout.EAST, lbl_calibration_library_directory, 0, SpringLayout.EAST, btn_close)
		lbl_calibration_library_directory.setFont(Font("Tahoma", Font.BOLD, 14))
		spring_layout.putConstraint(SpringLayout.NORTH, lbl_calibration_library_directory, 10, SpringLayout.NORTH, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.WEST, lbl_calibration_library_directory, 10, SpringLayout.WEST, self.getContentPane())
		self.getContentPane().add(lbl_calibration_library_directory)
		
		##	Default Calibration Library Directory Lable
		lbl_default_base_watershed = JLabel("Local Library: ...\\watershed\\"+Watershed+"\\hms\\forecast\\calibration_library")
		spring_layout.putConstraint(SpringLayout.NORTH, lbl_default_base_watershed, 6, SpringLayout.SOUTH, lbl_calibration_library_directory)
		spring_layout.putConstraint(SpringLayout.WEST, lbl_default_base_watershed, 20, SpringLayout.WEST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.EAST, lbl_default_base_watershed, -10, SpringLayout.EAST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.EAST, btn_close, 0, SpringLayout.EAST, lbl_default_base_watershed)
		lbl_default_base_watershed.setFont(Font("Tahoma", Font.PLAIN, 12))
		self.getContentPane().add(lbl_default_base_watershed)
		
		##	Remote Calibration Library Directory Lable
		lbl_remote_base_watershed = JLabel("Remote Library: " + remote_library_directory)
		spring_layout.putConstraint(SpringLayout.NORTH, lbl_remote_base_watershed, 6, SpringLayout.SOUTH, lbl_default_base_watershed)
		spring_layout.putConstraint(SpringLayout.WEST, lbl_remote_base_watershed, 20, SpringLayout.WEST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.EAST, lbl_remote_base_watershed, -10, SpringLayout.EAST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.EAST, btn_close, 0, SpringLayout.EAST, lbl_remote_base_watershed)
		lbl_remote_base_watershed.setFont(Font("Tahoma", Font.PLAIN, 12))
		self.getContentPane().add(lbl_remote_base_watershed)
		
		btn_defineDir = JButton("Change Remote Directory", actionPerformed=self.define_directory)
		spring_layout.putConstraint(SpringLayout.NORTH, btn_defineDir, 6, SpringLayout.SOUTH, lbl_remote_base_watershed);
		spring_layout.putConstraint(SpringLayout.WEST, btn_defineDir, 10, SpringLayout.WEST, lbl_remote_base_watershed);
		self.getContentPane().add(btn_defineDir)
		
		btn_downDir = JButton("Download from Remote", actionPerformed=self.download_from_directory)
		spring_layout.putConstraint(SpringLayout.NORTH, btn_downDir, 6, SpringLayout.SOUTH, lbl_remote_base_watershed);
		spring_layout.putConstraint(SpringLayout.WEST, btn_downDir, 10, SpringLayout.EAST, btn_defineDir);
		self.getContentPane().add(btn_downDir)
		
		btn_upDir = JButton("Upload to Remote", actionPerformed=self.upload_from_directory)
		spring_layout.putConstraint(SpringLayout.NORTH, btn_upDir, 6, SpringLayout.SOUTH, lbl_remote_base_watershed);
		spring_layout.putConstraint(SpringLayout.WEST, btn_upDir, 10, SpringLayout.EAST, btn_downDir);
		self.getContentPane().add(btn_upDir)
		
		####################################
		####	New Section of Dialog	####
		####################################
		##	Import Calibration File Section Lable
		lbl_import_calibration_file = JLabel("Import Calibration File")
		spring_layout.putConstraint(SpringLayout.WEST, lbl_import_calibration_file, 10, SpringLayout.WEST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.EAST, lbl_import_calibration_file, -10, SpringLayout.EAST, self.getContentPane())
		lbl_import_calibration_file.setFont(Font("Tahoma", Font.BOLD, 14))
		spring_layout.putConstraint(SpringLayout.NORTH, lbl_import_calibration_file, 120, SpringLayout.NORTH, self.getContentPane())
		self.getContentPane().add(lbl_import_calibration_file)
		
		##	Create scroll pane
		scroll_pane = JScrollPane()
		spring_layout.putConstraint(SpringLayout.NORTH, scroll_pane, 6, SpringLayout.SOUTH, lbl_import_calibration_file)
		spring_layout.putConstraint(SpringLayout.EAST, scroll_pane, -10, SpringLayout.EAST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.WEST, scroll_pane, 20, SpringLayout.WEST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.SOUTH, scroll_pane, -180, SpringLayout.SOUTH, self.getContentPane())
		scroll_pane.setVerticalScrollBarPolicy(ScrollPaneConstants.VERTICAL_SCROLLBAR_ALWAYS)
		scroll_pane.setHorizontalScrollBarPolicy(ScrollPaneConstants.HORIZONTAL_SCROLLBAR_ALWAYS)
		self.getContentPane().add(scroll_pane)
				
		##	Filter for calibration files that are only associated to active HMS alternative
		os.chdir(Calibration_Library_Directory_os)
		Available_HMS_Calibration_Files = glob.glob(''+ActiveHMSAlt+'*')
		
		##	List Selection Panel
		calibration_list = JList(Available_HMS_Calibration_Files)
		scroll_pane.setViewportView(calibration_list)
		
		##	Import Button
		btn_import = JButton("Import")
		btn_import.addActionListener(lambda e: self.Selected_Calibration(frame, calibration_list))
		spring_layout.putConstraint(SpringLayout.NORTH, btn_import, 6, SpringLayout.SOUTH, scroll_pane)
		spring_layout.putConstraint(SpringLayout.EAST, btn_import, 0, SpringLayout.EAST, scroll_pane)
		self.getContentPane().add(btn_import)
		
		####################################
		####	New Section of Dialog	####
		####################################
		##	Export Calibration File Section Lable
		lbl_export_calibration_file = JLabel("Export Calibration File")
		spring_layout.putConstraint(SpringLayout.NORTH, lbl_export_calibration_file, 10, SpringLayout.SOUTH, btn_import)
		spring_layout.putConstraint(SpringLayout.WEST, lbl_export_calibration_file, 10, SpringLayout.WEST, self.getContentPane())
		spring_layout.putConstraint(SpringLayout.EAST, lbl_export_calibration_file, 0, SpringLayout.EAST, btn_close)
		lbl_export_calibration_file.setFont(Font("Tahoma", Font.BOLD, 14))
		self.getContentPane().add(lbl_export_calibration_file)

		lbl_filename = JLabel("Filename")
		spring_layout.putConstraint(SpringLayout.NORTH, lbl_filename, 6, SpringLayout.SOUTH, lbl_export_calibration_file)
		spring_layout.putConstraint(SpringLayout.WEST, lbl_filename, 20, SpringLayout.WEST, self.getContentPane())
		lbl_filename.setFont(Font("Tahoma", Font.PLAIN, 12))
		self.getContentPane().add(lbl_filename)

		text_field_1 = JTextField(fcst_time_string)
		spring_layout.putConstraint(SpringLayout.NORTH, text_field_1, 6, SpringLayout.SOUTH, lbl_export_calibration_file)
		spring_layout.putConstraint(SpringLayout.WEST, text_field_1, 6, SpringLayout.EAST, lbl_filename)
		spring_layout.putConstraint(SpringLayout.EAST, text_field_1, -10, SpringLayout.EAST, self.getContentPane())
		self.getContentPane().add(text_field_1)
		text_field_1.setColumns(10)
		
		##	Export Button
		btn_export = JButton("Export")
		btn_export.addActionListener(lambda e: self.Calibration_File(frame, text_field_1))
		spring_layout.putConstraint(SpringLayout.NORTH, btn_export, 6, SpringLayout.SOUTH, text_field_1)
		spring_layout.putConstraint(SpringLayout.EAST, btn_export, 0, SpringLayout.EAST, text_field_1)
		self.getContentPane().add(btn_export)

		self.setPreferredSize(Dimension(600, 600))
		self.pack()
		theDialog = self
		print("owner = {}".format(owner))
		ownerLocation = owner.getLocation()
		self.setLocation(ownerLocation.x+10, ownerLocation.y+10)
	
	####################################################
	####	User defined remote library location	####
	####################################################
	def define_directory(self, event):
		if remote_library_directory == "Not Defined" :
			filepath_chooser = JFileChooser(Calibration_Library_Directory)
		else :
			filepath_chooser = JFileChooser(remote_library_directory)
		filepath_chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)
		result = filepath_chooser.showOpenDialog(self)
		
		if result == JFileChooser.APPROVE_OPTION:
			directory_file_w = open(Calibration_Library_Directory + '/Remote_Calibration_Library_Directory.txt',"w")
			selected_path = filepath_chooser.getSelectedFile().getAbsolutePath()
			directory_file_w.write(selected_path)
			directory_file_w.close()
			print "Selected file: ", str(selected_path)
		elif result == JFileChooser.CANCEL_OPTION:
			print "File selection cancelled."
		elif result == JFileChooser.ERROR_OPTION:
			print "An error occurred during file selection."
	
	####################################################
	####	Download from remote library location	####
	####################################################
	def download_from_directory(self, event):
		dl_cal_file_chooser = JFileChooser(remote_library_directory)
		filter = FileNameExtensionFilter("forecast files", "forecast")
		dl_cal_file_chooser.setFileFilter(filter)
		result = dl_cal_file_chooser.showOpenDialog(self)
		
		if result == JFileChooser.APPROVE_OPTION:
			dl_remote_file_name = dl_cal_file_chooser.getSelectedFile().getName()
			dl_remote_file = str(dl_cal_file_chooser.getSelectedFile())
			local_library_directory = os.path.normpath(Calibration_Library_Directory)
			dl_local_file = Calibration_Library_Directory+'/'+dl_remote_file_name
			## Check if file name exists in calibration library directory 
			if os.path.exists(dl_local_file) :
				FileExist = JOptionPane.showConfirmDialog(None, "<html>HMS calibration file named <b>"+dl_remote_file_name+"</b> exist in local calibration library.<li>Overwrite existing file?</html>","Calibration File Exists", JOptionPane.YES_NO_OPTION)
				if FileExist == 0 :
					shutil.copy2(dl_remote_file, Calibration_Library_Directory)
					MessageBox.showInformation("<html>HMS calibration file copied and replaced <b>"+dl_remote_file_name+"</b> in local calibration library.</html>", "HMS Calibration File")
					print("File overwritten")
				else :
					MessageBox.showError("HMS calibration file NOT copied to local calibration library.", "HMS Calibration File")
					print("File not copied")
			else :
				shutil.copy2(dl_remote_file, Calibration_Library_Directory)
				MessageBox.showInformation("HMS calibration file copied to local calibration library.", "HMS Calibration File")
			print("File copied")
		elif result == JFileChooser.CANCEL_OPTION:
			print("File selection cancelled.")
		elif result == JFileChooser.ERROR_OPTION:
			print("An error occurred during file selection.")
	
	################################################
	####	Upload to remote library location	####
	################################################
	def upload_from_directory(self, event):
		ul_cal_file_chooser = JFileChooser(Calibration_Library_Directory)
		filter = FileNameExtensionFilter("forecast files", "forecast")
		ul_cal_file_chooser.setFileFilter(filter)
		result = ul_cal_file_chooser.showOpenDialog(self)
		
		if result == JFileChooser.APPROVE_OPTION:
			ul_local_file_name = ul_cal_file_chooser.getSelectedFile().getName()
			ul_local_file = str(ul_cal_file_chooser.getSelectedFile())
			ul_remote_file = remote_library_directory+'/'+ul_local_file_name
			## Check if file name exists in calibration library directory 
			if os.path.exists(ul_remote_file) :
				FileExist = JOptionPane.showConfirmDialog(None, "<html>HMS calibration file named <b>"+ul_local_file_name+"</b> exist in remote calibration library.<li>Overwrite existing file?</html>","Calibration File Exists", JOptionPane.YES_NO_OPTION)
				if FileExist == 0 :
					shutil.copy2(ul_local_file, remote_library_directory)
					MessageBox.showInformation("<html>HMS calibration file copied and replaced <b>"+ul_local_file_name+"</b> in remote calibration library.</html>", "HMS Calibration File")
					print("File overwritten")
				else :
					MessageBox.showError("HMS calibration file NOT copied to remote calibration library.", "HMS Calibration File")
					print("File not copied")
			else :
				shutil.copy2(ul_local_file, remote_library_directory)
				MessageBox.showInformation("HMS calibration file copied to remote calibration library.", "HMS Calibration File")
			print("File copied")
		elif result == JFileChooser.CANCEL_OPTION:
			print("File selection cancelled.")
		elif result == JFileChooser.ERROR_OPTION:
			print("An error occurred during file selection.")
	
	############################################################	
	####	Import forecast file from calibration library	####
	############################################################
	def Selected_Calibration(self, frame, calibration_list):
		HMSFcstCalSelected = calibration_list.getSelectedValue()
		
		Selected_HMS_Calibration_File_os = os.path.join(forecastDirectory,'..\\..\\..\\watershed\\'+Watershed+'\\hms\\forecast\\calibration_library\\'+HMSFcstCalSelected+'')
		Selected_HMS_Calibration_File = Selected_HMS_Calibration_File_os.replace("\\", "/")
		
		## Close forecast, copy selecated calibration file to forecast directory, and then reopen forecast
		tab.closeForecast()
		shutil.copy2(Selected_HMS_Calibration_File, Current_HMS_fcstFileName)
		tab.openForecastAction()
		
		MessageBox.showInformation("<html>HMS forecast calibration <b>"+HMSFcstCalSelected+"</b> file copied to active forecast.</html>", "HMS Calibration File Import")
		
	########################################################	
	####	Export forecast file to calibration library	####
	########################################################
	def Calibration_File(self, frame, text_field_1):
		Calibration_Name = text_field_1.getText()
		
		HMS_Calibration_Library_File_os = os.path.join(forecastDirectory,'..\\..\\..\\watershed\\'+Watershed+'\\hms\\forecast\\calibration_library\\'+ActiveHMSAlt+'_'+Calibration_Name+'.forecast')
		HMS_Calibration_Library_File = HMS_Calibration_Library_File_os.replace("\\", "/")
		
		## Check if file name exists in calibration library directory 
		if os.path.exists(HMS_Calibration_Library_File) :
			FileExist = JOptionPane.showConfirmDialog(None, "<html>A calibration file named <b>"+Calibration_Name+"</b> exist.<li>Overwrite existing file?</html>","Calibration File Exists", JOptionPane.YES_NO_OPTION)
			if FileExist == 0 :
				shutil.copy2(Current_HMS_fcstFileName, HMS_Calibration_Library_File)
				MessageBox.showInformation("<html>HMS forecast calibration file copied and replaced <b>"+Calibration_Name+"</b> in calibration library.</html>", "HMS Calibration File")
				print("File overwritten")
			else :
				MessageBox.showError("<html>HMS forecast calibration file NOT copied to calibration library.  Use another name different than <b>"+Calibration_Name+"</b>.</html>", "HMS Calibration File")
				print("File not copied")
		else :
			shutil.copy2(Current_HMS_fcstFileName, HMS_Calibration_Library_File)
			MessageBox.showInformation("HMS forecast calibration file copied to calibration library.", "HMS Calibration File")

def main():
	dialog = HMS_Cal_Lib_Dialog(owner=ListSelection.getMainWindow(), title="HMS Calibration Library")
	dialog.setVisible(True)
			
if __name__ == "__main__":
	main()