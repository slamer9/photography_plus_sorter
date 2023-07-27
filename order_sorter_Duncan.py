# Order sorter by Duncan Reeves
# Modified sorter based on a sorter by Dallin Hutchison
# File runs a gui and lets you select an order form, a destination folder, and a source folder
    # filenames in the source folder should be in the format [Date]_[Customer]_[Farm]_[FieldName]_[Product].[extension]. An '_' is also used within attribute names if there are spaces inside of them
# When run, the order form will be read and transfer files from the source folder, to the destination folder, based on the order form

import os
import shutil
import csv
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Tuple, List
import sys

# Filename variables
TIF_FOLDER_NAME, JPG_FOLDER_NAME = "GeoTiff", "JPG"
PRODUCT_NAME_TRANSLATIONS = {
    # "EVI_Values": "Bioindex_Report",
    "FCIR": "Infrared",
    "RGB": "Color",
}

# Classes used to create the user interface
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

# Order class to make sure that orders read from the order form are standardized
class Order:
    # At the moment only customer, farm, and field_name are relevant data for the algorith, but that may change so I'm inluding more order data
    def __init__(self, row):
        '''
        Initiates an Order object from the details in a row of an order form
        Replaces spaces with underscores for data that appears in filenames

        NOTE
        - The information is designated here by the order the columns show up. If that should be changed to be based on the names of the columns, then this needs to be changed here
        - Right now the only relevant information from the order form that the sorter needs are: field_name, crop, customer, farm, and manager. Other data is discarded, but can easily be added below
        '''
        self.pk = row[0]
        self.field_name = row[1].replace(' ','_')
        self.crop = row[2]
        self.customer = row[3].replace(' ','_')
        self.farm = row[4].replace(' ','_')
        # self.variety = row[5] # Not used in algorithm, so not included
        self.manager = row[6]
        # self.zone = row[7] # Not used in algorithm, so not included
    
    def to_csv_format(self):
        '''
        Return a string of the order information, in a CSV format. (Simmilar to what was read in. An identical Order object should be created if initiated by the result of this function)
        '''
        return f'{self.pk},{self.field_name},{self.crop},{self.customer},{self.farm},,{self.manager},,,,'
    
    def __eq__(self, other):
        '''
        Compare two orders for equality.
        '''
        if isinstance(other, Order):
            return (
                # self.pk == other.pk
                self.field_name == other.field_name
                # and self.crop == other.crop
                and self.customer == other.customer
                and self.farm == other.farm
                # and self.variety == other.variety
                # and self.manager == other.manager
                # and self.zone == other.zone
            )
        return False
    
    def __str__(self):
        """
        Return a string representation of the Order object.
        """
        # return f'pk: {self.pk}, field_name: {self.field_name}, crop: {self.crop}, customer: {self.customer}, farm: {self.farm}, variety: {self.variety}, manger: {self.manager}, zone: {self.zone}'
        return f'pk: {self.pk}, field_name: {self.field_name}, crop: {self.crop}, customer: {self.customer}, farm: {self.farm}, manager: {self.manager}'

# PhotoFile class to make sure that photo filenames are read in a standarized way
class PhotoFile:
    def __init__(self, fname):
        # fname should look like: [Date]_[Customer]_[Farm]_[FieldName]_[Product].[extension]. Unfortunately the '_' is also used within customer/farm names (and potentially field names in the future), so the aspects need to be removed before we can split by '_'
        self.filename = fname
        split_name = fname.split('_')
        
        self.date = split_name[0]
        self.field_name = split_name[-2]
        self.product, self.ext = split_name[-1].split('.')
        self.ext = self.ext.lower()
    
    def matches_order(self, order: Order):
        if order.field_name == self.field_name:
            if order.customer in self.filename and order.farm in self.filename: # Order matches file
                # self.date, _, _, _, _ = self.filename.replace(order.customer, '').replace(order.farm, '').replace(order.field_name, '').split('_') # Currently redundant, and not general 
                self.customer = order.customer
                self.farm = order.farm
                return True
        return False
    
    def __str__(self) -> str:
        return self.filename
    
    def __eq__(self, other):
        '''
        Compare two PhotoFiles for equality.
        '''
        if isinstance(other, PhotoFile):
            return (
                # self.customer == other.customer
                # and self.farm == other.farm
                self.filename == other.filename
                # and self.product == other.product
                # and self.ext == other.ext
            )
        return False

# Error class to give better log messages when things go wrong
class DataException(Exception):
    """Custom exception class."""
    pass

def extract_orders_from_order_form(order_form_path: str) -> list:
    '''
    Reads the order form and returns a list of Order objects, detailing what the order form wanted

    Parameters:
        order_form_path (str, PathLike): Path to the order form file (CSV format)

    Returns:
        list: A list of orders

    Raises:
        FileNotFoundError: If the order form does not exist.
        DataException: If there are duplicate orders
    '''
    orders = []
    with open(order_form_path) as csvfile:
        readCSV = csv.reader(csvfile, delimiter=",") # Returns a reader object that will iterate over each line in the CSV, returning it as a list
        header = next(readCSV) # Moves the header out of the reader, so now we're working with the data we want

        # Translate all orders in the order form, into the orders list. Raise an exception if an identical order already exists
        for row in readCSV:
            new_order = Order(row)
            if new_order in orders:
                raise DataException(f'Two orders contain duplicate information\nThe following order was a duplicate: {new_order}')
            else:
                orders.append(Order(row))
    
    return orders

def move_file(target_dir: str, photo_dir_path: str, order: Order, photofile: PhotoFile):
    '''
    Move file according to instructions
    - Determine the destination directory (up to date algorithm goes here), and new name (if applicable); from the order and filename information
    - Move the file to the destination directory

    Parameters:
        target_dir (str, PathLike): Path to the target directory
        photo_dir_path (str, PathLike): Path to the photo directory
        order (Order object): Relevant data from the order form
        photofile (PhotoFile object): Relevant data from the filename

    Raises:
        FileNotFoundError: If the photo directory or target directory does not exist.

    NOTE
    -This function moves files based on a specific algorithm dependent on the filenames of the images, and an order form. If the filenames, or order form, changes, the algorithm may no longer work
    -This algorithm expects file names in the form of subfields separated by underscores: [Date]_[Customer]_[Farm]_[FieldName]_[Product].[extension]
        -- The extension is expected to be either 'tif' or 'jpg'
        -- Subfields can also have underscores '_' in them (ie, if the customer is two words then they will be separated by '_')
    - The order form is a csv, where every row is an order with the format: pk, FieldName, Crop, Customer, Farm, Variety, Manager, Zone, Acres, Region, Product (only FieldName, Crop, Customer, Farm, and Manager are used by the current algorithm)
    '''
    ### Get relevant information from the photo_filename ###
    photo_filename = photofile.filename
    original_img_path = os.path.join(photo_dir_path, photo_filename) # get the path where the image is right now
    product = photofile.product
    if product in PRODUCT_NAME_TRANSLATIONS: product = PRODUCT_NAME_TRANSLATIONS[product]
    

    ### Determine the destination directory of files, and change the photo_filename if needed. Up to date algorithm here ###
    # Special cases first
    if order.customer == 'RD_Offutt':
        if order.farm != 'Inland':
            destination_dir = os.path.join(target_dir, 'Anderson Geographics', TIF_FOLDER_NAME if photofile.ext == 'tif' else JPG_FOLDER_NAME)
            photo_filename = f'{photofile.date}_{order.field_name}_{photofile.product}.{photofile.ext}'
        else:
            destination_dir = os.path.join(target_dir, order.customer.replace('_',' '), '3 Mile', order.manager, order.crop, product)
            if photofile.ext == 'tif': destination_dir = os.path.join(destination_dir, TIF_FOLDER_NAME)
    elif (order.customer == 'Agri_NW' or order.customer == 'Washington_Onion' or order.customer == 'Paterson_Ferry') and photofile.ext == 'tif':
        destination_dir = os.path.join(target_dir, 'Agri Server', order.farm.replace('_',' '))
    elif order.customer == 'Canyon_falls':
        if photofile.ext == 'tif':
            destination_dir = os.path.join(target_dir, 'Canyon Falls Server')
        else:
            destination_dir = os.path.join(target_dir, order.customer.replace('_',' '), order.manager, order.crop, product)
    else: # Not a special case
        destination_dir = os.path.join(target_dir, order.customer.replace('_',' '), order.farm.replace('_',' '), order.manager, order.crop, product)
        if photofile.ext == 'tif': destination_dir = os.path.join(destination_dir, TIF_FOLDER_NAME)
        
    
    ### Now that destination_dir is determined, move the file ###
    destination = os.path.join(destination_dir, photo_filename) # destination is the destination directory + filename

    if os.path.exists(destination): # if the name already exists in the destination directory, create a modified name 
        print(f'File already exists: {photo_filename} already exists in {destination_dir}. Giving a modifier "name_conflict_" to begining of file name')
        photo_filename = f'name_conflict_{photo_filename}'
        destination = os.path.join(destination_dir, photo_filename)

    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir) # Ensure the parent directories to the destination exist
    shutil.move(original_img_path, destination)

def process_orders(order_form_path: str, photo_dir_path: str, target_dir: str) -> Tuple[int, str]:
    '''
    Parses the order form, and searches the photo directory for matches. Processes matches, and creates a CSV of unfulfilled orders, if any (orders with no matches). Returns list of unfulfilled orders and the number of files that were moved
    - Create a list of orders from the order form
    - Create a list of photo filenames in the photo directory
    - For every order, find the photo filename(s) from the list that match, and process them
    - Compile orders that were unable to complete, return them in CSV format

    Parameters:
        order_form_path (str, PathLike): Path to the order form file (CSV format)
        photo_dir_path (str, PathLike): Path to the directory of photos
        target_dir (str, PathLike): Path to the target directory

    Returns:
        Tuple[int, str]: Number of files that were moved, and a string of unfulfilled orders in csv format (empty string if no unfulfilled orders)

    Raises:
        FileNotFoundError: If the photo directory or target directory does not exist.
        DataException: If the photo files don't meet order form specifications (duplicates, no matching files, etc)
    '''
    orders = extract_orders_from_order_form(order_form_path) # A list of Order objects, representing the orders from the order form
    photo_filenames = [PhotoFile(fname) for fname in os.listdir(photo_dir_path) if os.path.isfile(os.path.join(photo_dir_path, fname))] # A list of PhotoFiles for filenames which should be in the format [Date]_[Customer]_[Farm]_[FieldName]_[Product].[extension]. An '_' is also used within customer/farm names if there are multiple words in those names, instead of spaces

    unfulfilled_orders = [] # Keep track of any orders that didn't have any matching files to move
    moved_files = [] # Keep track of what files have been moved, to catch if duplicate files are attempting to be moved
    for order in orders: # For every order, search the filenames for matching files, and move them
        found_match = False
        for photofile in photo_filenames:
            if photofile.matches_order(order):
                if photofile.filename in moved_files:
                    raise DataException(f'Error. Attempt to move an already moved file.\nOrder: {order}\nAttempted to move the file {photofile.filename}, which has already been moved.')
                moved_files.append(photofile.filename)
                found_match = True

                move_file(target_dir, photo_dir_path, order, photofile)
        if not found_match:
            # raise DataException(f'Error. No matching file found.\nAn order did not find a matching file to move: {order}')
            unfulfilled_orders.append(order.to_csv_format())
    
    return (len(moved_files), str.join('\n',unfulfilled_orders))

# Entry function called by main
def attempt_process(
    target_selection: FolderFileSelect,
    photo_selection: FolderFileSelect,
    order_form_selection: FolderFileSelect,
) -> None:
    '''
    Attemps to process the order, and handles errors that occur in the process.
    - Checks the validity of the selections, returning if invalid
    - Attempts to fulfill the orders
        -- Call "process_orders"
            -- Reads the order form (order_form_selection), and process each order from photos inside the photo directory (photo_selection)
	        -- Returns the number of photos moved
    - Displays results from attempting to fulfill the orders
        -- Error if no files were moved
        -- Sucess if files were moved, along with how many were moved
    - Exceptions that are thrown during the process are caught here

    Parameters:
        target_selection (FolderFileSelect, selection of a file path): Path to the target directory, where the files should be moved.
        photo_selection (FolderFileSelect, selection of a file path): Path to the directory containing the photos.
        order_form_selection (FolderFileSelect, selection of a file path): Path to the order form file (CSV format).
    '''
    
    ### Extract the paths from the user interface ###
    target_path = target_selection.get_path()
    photo_path = photo_selection.get_path()
    order_form_path = order_form_selection.get_path()

    ### Verify that all paths are selected  ###
    if target_path == "" or target_path == None:
        tk.messagebox.showerror("Error", "Destination Folder is not selected")
        return
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

    # Try to move the image files, display results and handle relevant exceptions/errors
    try:
        files_moved, unfulfilled_orders = process_orders(order_form_path, photo_path, target_path)

        if files_moved == 0:
            tk.messagebox.showerror("No files moved.", "No matching files were found using the given order form and photo folder.")
        else:
            tk.messagebox.showinfo("Success", f"{files_moved} image files have been moved to {target_path}")
            # TODO write unfulfilled_orders to file
    except OSError as e:
        tk.messagebox.showerror("Error", f"Error moving files: {e}")
    except DataException as e:
        tk.messagebox.showerror("Error", f"Data has invalid attributes: {e}")
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        print(exc_tb)
        tk.messagebox.showerror("Error", f"Other error: {e}")

if __name__ == "__main__":
    # Initialize the user interface
    gui = tk.Tk()
    gui.geometry("800x300")
    gui.title("Image File Organizer")

    # Create places to specifiy the directories and order form
    target_selection = FolderFileSelect(gui, "Select Destination Folder")
    target_selection.grid(row=1)

    photo_selection = FolderFileSelect(gui, "Select Source Folder")
    photo_selection.grid(row=0)

    order_form_selection = FolderFileSelect(gui, "Select the Order.csv", select_file=True)
    order_form_selection.grid(row=2)

    # Create a button to start the process
    def start_process():
        attempt_process(target_selection=target_selection, photo_selection=photo_selection, order_form_selection=order_form_selection)

    start_button = ttk.Button(gui, text="Move Image Files", command=start_process)
    start_button.grid(row=4, column=0)

    # Start the user interface
    gui.mainloop()
