# pk renamer by Duncan Reeves
# File runs a gui and lets you select an order form,  and a source folder
	# filenames in the source folder should be in the format [Date]_[Customer]_[Farm]_[FieldName]_[Product].[extension]. (An '_' is also used within attribute names if there are spaces inside of them)
	# filenames should be renamed to: [Date]_[Customer]_[Farm]_[FieldName]_[Product]_p[pk].[extension]
# When run, the order form will be read file names in the source folder, and rename them accordingly

import os
import shutil
import csv
import tkinter as tk
from tkinter import filedialog, ttk
import sys
from datetime import datetime
# from enum import Enum
# from typing import Tuple, List

# Filename variables
TIF_FOLDER_NAME, JPG_FOLDER_NAME = "GeoTiff", "JPG"
PRODUCT_NAME_TRANSLATIONS = {
	# "EVI_Values": "Bioindex_Report",
	"FCIR": "Infrared",
	"RGB": "Color",
}
PRODUCT_SEPARATOR = '-'

# Order form variables. If the names of these change on the order form (even simple things like spelling or capitalization), they need to be changed here
class CSV_cols():
	pk = 'pk'
	field_name = 'FieldName'
	product = 'Product'
	crop = 'Crop'
	customer = 'Customer'
	farm = 'Farm'
	variety = 'Variety'
	manager = 'Manager'
	zone = 'Zone'
	region = 'Region'
	Order_status = 'Order_status' # Capitalized to keep the order in a desired way (any attributes not included in an order form will be added in alphabetical order). If it becomes a problem, this can be solved by explicitly stating the order that these attributes should be added in the 'extract_orders_from_order_form' method.
	date_aquired = 'Date_Acquired'
	reshoot = 'Reshoot'

# Order class to make sure that orders read from the order form are standardized
class Order:
	'''
	- Represents the relevant information from an order (where each line within the orderform is considered an order)
	- Contains relevant methods to manipulate Order objects, and read/write an order to/from a csv
	- Contains common details across orders of an order form (the header)
	'''
	def __init__(self, order_data):
		'''
		Initiates an Order object from the details inside a row of the order form (in dictionary form)

		NOTE
		- If a field is empty it will be read in as an empty string
		- Order form name data needs to match what the program expects. If a column name is referenced in the algorithm, then it needs to appear exactly as it does in CSV_cols
		'''
		self.data = order_data
		# Some columns (like Order_status, Date_Acquired, and Reshoot) are not guaranteed to be in the order form, so we need to make sure they're in the order object
		[self.data.setdefault(getattr(CSV_cols, attr),'') for attr in dir(CSV_cols) if not callable(getattr(CSV_cols,attr)) and not attr.startswith("__")]

	def extract_orders_from_order_form(order_form_path: str) -> list:
		'''
		Reads the order form and returns a list of Order objects, detailing what the order form wanted
		If there are duplicate orders, write those details to a file

		Parameters:
			order_form_path (str, PathLike): Path to the order form file (CSV format)

		Returns:
			list: A list of orders

		Raises:
			FileNotFoundError: If the order form does not exist.
		'''
		orders = []
		duplicate_orders = []
		# Translate all orders inside the order form into a list of Order objects. If duplicate orders exist, ignore the duplicates, and write that information out to a warning file.
		with open(order_form_path) as csvfile:
			reader = csv.reader(csvfile, delimiter=",") # Reader object that will iterate over each line in the CSV
			header = next(reader) # Moves the header out of the read buffer, so now we're working with the data we want. Throw this data away, we don't need it.
			for row in reader:
				new_order = Order(dict(zip(header, row)))
				duplicate_orders.append(str(new_order)) if new_order in orders else orders.append(new_order)
			
			# Some columns (like Order_status, Date_Acquired, and Reshoot) are not guaranteed to be in the order form, so we need to make sure they're in the header. Just add them onto the end
			for col in [getattr(CSV_cols, attr) for attr in dir(CSV_cols) if not callable(getattr(CSV_cols,attr)) and not attr.startswith("__")]:
				if col not in header:
					header.append(col)
			Order.csv_header = header
			
		if len(duplicate_orders) > 0: # Handle duplicate data in the order form
			duplicate_orders.insert(0,"The following are the duplicate orders:")
			write_logfile(location=os.path.dirname(order_form_path), name=f"Order_duplicates_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}", content='\n'.join(duplicate_orders), warning='Duplicate orders present')
		
		return orders
	
	def every_match_present(self, matching_photofiles:list) -> bool:
		'''
		Input is a list of all matching photofiles for this order
		Return a true or a false if every product type for this order has both a jpg and a tif

		Parameters:
			order_form_path (str, PathLike): Path to the order form file (CSV format)
			photo_dir_path (str, PathLike): Path to the directory of photos
			target_dir (str, PathLike): Path to the target directory
			copy (bool): copy or move

		Returns:
			bool: If every match is present
		'''
		for product in self.data[CSV_cols.product].split(PRODUCT_SEPARATOR): # If multiple products are present, they are separated by a dash
			jpeg_match = False
			tif_match = False
			for photofile in matching_photofiles:
				if photofile.product == product:
					if photofile.ext == 'tif':
						tif_match = True
					elif photofile.ext == 'jpeg' or photofile.ext == 'jpg':
						jpeg_match = True
					else:
						raise Exception(f"File found with unrecongnized extension (not 'jpeg', 'jpg', or 'tif')\nFile name: {photofile.filename}\tExtension: {photofile.ext}")
			if jpeg_match and tif_match:
				pass # Matches were found for this product
			else:
				return False
		return True

	def update_order_details(self, completed:bool, date:str = None) -> None:
		'''
		Update order details to show if an order was completed; and if it was, update the date and mark if it was a reshoot
		'''
		if completed:
			self.data[CSV_cols.date_aquired] = date # All matching photos should have the same date, so just use the first one
			if self.data[CSV_cols.Order_status] == 'Incomplete' or self.data[CSV_cols.Order_status] == '':
				self.data[CSV_cols.reshoot] = 'False'
			elif self.data[CSV_cols.Order_status] == 'Complete':
				self.data[CSV_cols.reshoot] = 'True'
			else:#If we ever reach this point, it means the order form had bad data for the order status
				self.data[CSV_cols.reshoot] = 'Unknown (previous order status data was neither "Complete" nor "Incomplete")'

			self.data[CSV_cols.Order_status] = 'Complete'
		elif self.data[CSV_cols.Order_status] == 'Complete':
			pass # If matches weren't found, but the order is already complete, then ignore this order, don't do anything with it
		else:
			self.data[CSV_cols.Order_status] = 'Incomplete'

	def __eq__(self, other):
		'''
		- Compare two orders for equality.
		- Currently is used to see if there are duplicate orders that match to the same file
			-- So the only detils being checked here are self.data[CSV_cols.___] for customer, farm, and fieldName
			-- If that changes and other data needs to be checked, then this needs to change
		'''
		if isinstance(other, Order):
			return (
				self.data[CSV_cols.field_name] == other.data[CSV_cols.field_name]
				and self.data[CSV_cols.customer] == other.data[CSV_cols.field_name]
				and self.data[CSV_cols.farm] == other.data[CSV_cols.field_name]
			)
		return False
	
	def __str__(self):
		"""
		Return a string representation of the Order object.
		"""
		return(str(self.data))

# PhotoFile class to make sure that photo filenames are read in a standarized way
class PhotoFile:
	SEARCHABLE_FEATURE_ORDER = ["customer", "farm", "field_name"] # Aspects of order

	def __init__(self, fname):
		'''
		- Represents the relevant information from a filename
		- Contains relevant methods to manipulate PhotoFile objects, and determine if the filename matches a given order

		fname should look like: [Date]_[Customer]_[Farm]_[FieldName]_[Product].[extension]. Unfortunately the '_' is also used within customer/farm names (and potentially field names in the future), so the aspects need to be handled if we split by '_'

		Date, Product, and extension can all be assumed to not contain underscores
		'''
		self.filename = fname
		
		split_name = fname.split('_')
		self.date = split_name[0]
		self.product, self.ext = split_name[-1].split('.')
		self.ext = self.ext.lower()
		
		self.order_searchable_name = '_'.join(split_name[1:-1]) # A name that only contains information the order will also contain. [Customer]_[Farm]_[FieldName]
	
	def matches_order(self, order: Order):
		'''
		Returns True if the photofile matches the order, False otherwise.
		Checks if it's a match by comparing self.order_searchable_name to what it should be based on the order form
		'''
		return self.order_searchable_name == order.data[CSV_cols.customer].replace(' ','_') + '_' + order.data[CSV_cols.farm].replace(' ','_') + '_' + order.data[CSV_cols.field_name].replace(' ','_')
	
	def __str__(self) -> str:
		return self.filename
	
	def __eq__(self, other):
		'''
		Compare two PhotoFiles for equality.
		'''
		if isinstance(other, PhotoFile):
			return (self.filename == other.filename)
		return False

# Class to ineract with the GUI
class FolderFileSelect(tk.Frame):
	def __init__(self, parent=None, folderDescription="", select_file=False, **kw):
		tk.Frame.__init__(self, master=parent, **kw)
		self.select_file = select_file
		self.folderPath = tk.StringVar()
		self.lblName = tk.Label(self, text=folderDescription)
		self.lblName.grid(row=0, column=0, padx=15, pady=15)
		self.entPath = tk.Entry(self, textvariable=self.folderPath, width=65)
		self.entPath.grid(
			row=0,
			column=1,
		)

		button_text = "Select File" if select_file else "Select Folder"
		self.btnFind = ttk.Button(self, text=button_text, command=self.setFolderPath)
		self.btnFind.grid(row=0, column=2, padx=20, pady=15)

	def setFolderPath(self):
		if self.select_file:
			folder_selected = filedialog.askopenfile()
			folder_selected = folder_selected.name
		else:
			folder_selected = filedialog.askdirectory()
		self.folderPath.set(folder_selected)

	def get_path(self):
		return self.folderPath.get()

def write_logfile(location:str, content:str, name:str = f"logfile_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}", warning:str = None):
	'''
	Writes a logfile 
	- Located at: location
	- Contains: content
	- Called: name
	- (optional) The GUI will notify the user that the logfile was created, with the message: warning
	The name of the logfile is optional. If left unspecified it will be "logfile_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}"

	Parameters:
		location (str, PathLike): Path to where the error log will be created.
		content (string or string castable): content will be directly written to the file
		name (str): Optional, name of log file. Default is "logfile_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}"
		warning (str): Warning to show via the GUI that a logfile was created
	'''
	filename =  os.path.join(location, name)
	with open(filename, 'a') as file:
		file.write(content)
	if warning is not None: tk.messagebox.showerror(warning, f"Log file {name} created at {location}")

def handle_overlap_and_nomatches(renamed_files:dict, orders_without_matches:list, order_form_path:str):
	'''
	- Specify image files that matched with multiple orders, and which orders those were
	- Specify orders with no matches
	- Write details to logfile

	Parameters:
		renamed_files (dict; key = filename, val = list of orders that matched that filename)
		orders_without_matches (list of order objects without a match)
	'''
	error_message = ''

	# Notify if there were files matched by multiple orders (overlap)
	for filename in renamed_files:
		if len(renamed_files[filename]) > 1: # Multiple orders match to the file
			error_message += f'The file {filename} was matched by multiple different orders. The following orders matched with the file:\n'
			for order in renamed_files[filename]:
				error_message += f'\t{order}\n'
			error_message += f'\n'
	
	# Notify of orders without matches
	if len(orders_without_matches) > 0:
		error_message += f'The following orders had no matching images:\n'
		for order in orders_without_matches:
			error_message += f'\t{order}\n'
		error_message += f'\n'

	if len(error_message) > 0:
		write_logfile(location=os.path.dirname(order_form_path), name=f"Orderform_errors_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.txt", content=error_message, warning='Warning: orders found without a match, or overlapping matches')

def rename_file(photofile:PhotoFile, order:Order, photo_dir_path:str):
	'''
	Rename file
	- change files from [Date]_[Customer]_[Farm]_[FieldName]_[Product].[extension] to [Date]_[Customer]_[Farm]_[FieldName]_[Product]_p[pk].[extension]
		-- Do this by just adding "_p[pk]" to the end of the filename before the extention
		-- If the filname already has a "p" on the last section, then assume it's already renamed and ignore it

	Parameters:
		photo_dir_path (str, PathLike): Path to the photo directory
		order (Order object): Relevant data from the order form
		photofile (PhotoFile object): Relevant data from the filename

	Raises:
		FileNotFoundError: If the photo directory or target directory does not exist.
	'''
	
	# Determine pk_name
	pk_name = ''
	name, ext = photofile.filename.split('.')
	last_section_of_name = name.split('_')[-1]

	if last_section_of_name.startswith('p'): # Filename is already the pk name, do nothing
		return
	else:	# Create pk name and return it
		pk_name = name + '_p' + f'{order.data[CSV_cols.pk]}' + '.' + ext

	# Rename file to the pk_name
	old_filename = os.path.join(photo_dir_path, photofile.filename)
	new_filename = os.path.join(photo_dir_path, pk_name)
	os.rename(old_filename, new_filename)

def parse_source_data(order_form_path:str, photo_dir_path:str) -> tuple:
	'''
	Parses the order form and source folder into Order and Photofile objects the algorithm can work with.
	Parameters:
		order_form_path (str, PathLike): Path to the order form file (CSV format)
		photo_dir_path (str, PathLike): Path to the directory of photos
	Returns:
		Tuple: (list of order objects, list of photofile objects)
	Raises:
		FileNotFoundError: If the photo directory does not exist.
	'''
	orders = Order.extract_orders_from_order_form(order_form_path) # A list of Order objects, representing the orders from the order form
	photo_files = [PhotoFile(fname) for fname in os.listdir(photo_dir_path) if os.path.isfile(os.path.join(photo_dir_path, fname))] # A list of PhotoFile objects, for all the filenames in the photo_dir_path
	return (orders, photo_files)

def parse_and_process_orders(order_form_path:str, photo_dir_path:str) -> int:
	'''
	Parses the order form, searches the photo directory for matches
	Renames matches
	Handles edge cases (orders with no matches, or unfulfilled orders)
	Returns the number of files that were renamed

	- Create a list of orders from the order form
	- Create a list of photo filenames in the photo directory
	- For every order, find the photo filenames from the list that match

	Parameters:
		order_form_path (str, PathLike): Path to the order form file (CSV format)
		photo_dir_path (str, PathLike): Path to the directory of photos

	Returns:
		Int: Number of files that were renamed
	Raises:
		FileNotFoundError: If the photo directory or target directory does not exist.
	'''
	orders, photo_files = parse_source_data(order_form_path, photo_dir_path) # Lists (Order/Photofile objects) for all orders and photos in source data

	# PROCESS ORDERS
	renamed_files = {} # Keep track of what files have been renamed, to catch if multiple orders are attempting to move the same files. renamed_files: keys = the filename, values = a list of corresponding orders that match that file.
	orders_without_matches = []

	for order in orders: # For every order, search the filenames for matching files, and process them
		matching_photos = []
		for photofile in photo_files:
			if photofile.matches_order(order):
				matching_photos.append(photofile)

		if len(matching_photos) == 0: orders_without_matches.append(order) # Identify orders without matches

		for photofile in matching_photos:
			rename_file(photofile, order, photo_dir_path) # Rename the file, if file is already renamed then skip over it
			renamed_files.setdefault(photofile.filename,[]).append(order)
	
	handle_overlap_and_nomatches(renamed_files, orders_without_matches, order_form_path)
	return len(renamed_files)

def attempt_process(
	photo_selection:FolderFileSelect,
	order_form_selection:FolderFileSelect,
) -> None:# Entry function called by main
	'''
	Attemps to process the renaming order, and handles errors that occur in the process.
	- Checks the validity of the selections, returning if invalid
	- Attempts to rename based on the orders
		-- Call "parse_and_process_orders"
			-- Reads the order form (order_form_selection), and makes a list of orders
			-- renames every photo that matches an order
			-- Returns the number of photos renamed
	- Displays results from attempting to rename
		-- Error if no files were renamed
		-- Sucess if files were renamed, along with how many were renamed
	- Exceptions that are thrown during the process are caught here

	Parameters:
		photo_selection (FolderFileSelect, selection of a file path): Path to the directory containing the photos.
		order_form_selection (FolderFileSelect, selection of a file path): Path to the order form file (CSV format).
	'''
	
	### Extract the paths from the user interface ###
	photo_path = photo_selection.get_path()
	order_form_path = order_form_selection.get_path()

	### Verify that all paths are selected  ###
	if photo_path == "" or photo_path == None:
		tk.messagebox.showerror("Error", "Photo Folder is not selected")
		return
	if order_form_path == "" or order_form_path == None:
		tk.messagebox.showerror("Error", "Order Form is not selected")
		return
	
	### Verify that the order path is a csv ###
	if not os.path.basename(order_form_path).endswith(".csv"):
		tk.messagebox.showerror("Error", "Order form is not a CSV file.")
		return

	# Try to rename the image files, display results and handle relevant exceptions/errors
	try:
		files_renamed = parse_and_process_orders(order_form_path, photo_path)
		if files_renamed == 0:
			tk.messagebox.showerror("No files moved.", "No matching files were found using the given order form and photo folder.")
		else:
			tk.messagebox.showinfo("Success", f"{files_renamed} image files have been renamed")
	except OSError as e:
		tk.messagebox.showerror("Error", f"Error renaming files: {e}")
	except Exception as e:
		exc_type, exc_obj, exc_tb = sys.exc_info()
		fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
		print(exc_type, fname, exc_tb.tb_lineno)
		print(exc_tb)
		tk.messagebox.showerror("Error", f"Error message: {e}")

if __name__ == "__main__":
	# Initialize the user interface
	gui = tk.Tk()
	gui.geometry("800x300")
	gui.title("Order Sorter")

	photo_selection = FolderFileSelect(gui, "Select Source Folder")
	photo_selection.grid(row=0)

	order_form_selection = FolderFileSelect(gui, "Select the Order.csv", select_file=True)
	order_form_selection.grid(row=2)

	# Create a checkbox to mark if we want to move or copy the files
	# copy = tk.IntVar(value=1)  # Binary variable to store checkbox state
	# checkbox = ttk.Checkbutton(gui, text="Copy files", variable=copy)
	# checkbox.grid(row=3)

	# Create a button to start the process
	def start_process():
		attempt_process(photo_selection=photo_selection, order_form_selection=order_form_selection)

	start_button = ttk.Button(gui, text="Rename Image Files", command=start_process)
	start_button.grid(row=4, column=0)

	# Start the user interface
	gui.mainloop()