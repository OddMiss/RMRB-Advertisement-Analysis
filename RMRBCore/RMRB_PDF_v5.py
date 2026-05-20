import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from PyPDF2 import PdfReader, PdfWriter
from datetime import timedelta
import os
# from Config.Config import EXTERNAL_PATH
from Utils.main import PrintUtils, FileUtils, JsonUtils, TimeUtils, TextUtils
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
Compare_File_Sizes = FileUtils.Compare_File_Sizes
Update_File_Lists = FileUtils.Update_File_Lists
Get_File_Size = FileUtils.Get_File_Size
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict
Dict_to_JsonFile = JsonUtils.Dict_to_JsonFile
Generate_Dates = TimeUtils.Generate_Dates
NowTime = TimeUtils.NowTime
Get_Subfolders = FileUtils.Get_Subfolders
Create_Date = TimeUtils.Create_Date
Format_Num = TextUtils.Format_Num

def Check_Mac(Folder_Path, Delete=False, Log_File_Path=""):
    """
    - Some files are like "20090104-ITCN000793-MAC.pdf", it should be removed
    - Delete all PDF files ending with "MAC" in the specified folder and all subfolders.
    """
    deleted_count = 0
    error_count = 0
    # Walk through all directories and files
    for foldername, _, filenames in os.walk(Folder_Path):
        for filename in filenames:
            # Check if file ends with "MAC.pdf" (case-sensitive)
            if filename.endswith("MAC.pdf"):
                file_path = os.path.join(foldername, filename).replace("""\\""", "/")
                try:
                    if Delete: 
                        os.remove(file_path)
                        THREAD_SAFE_PRINT("Check Mac", f"Deleted: {file_path}", Log_File_Path)
                    else: THREAD_SAFE_PRINT("Check Mac", f"Abnormal: {file_path}", Log_File_Path)
                    deleted_count += 1
                except Exception as e:
                    THREAD_SAFE_PRINT("Check Mac", f"Error deleting {file_path}: {e}", Log_File_Path)
                    error_count += 1
    # Print summary
    THREAD_SAFE_PRINT("Check Mac", f"\nSummary:", Log_File_Path)
    THREAD_SAFE_PRINT("Check Mac", f"Successfully deleted: {deleted_count} files", Log_File_Path)
    THREAD_SAFE_PRINT("Check Mac", f"Errors: {error_count} files", Log_File_Path)

def Check_PDF_Exist(YEAR, Folder_Path, Begin_date="0101", End_date="1231", Log_File_Path=""):
    """
    - Check whether there is missing PDFs
    - the PDF pages are 4 (before 2013), 8, 20, 16 (infrequent), 12 (early times), 24, 32 (seldom, 20241216),
    28 (seldom, 20150624), 17 (rare and special, 2016018, version 17 to 20 are in single page; Extreme official missing case: 20200528)
    27 (seldom, 20150717)
    """
    MISSING_PDF = []
    Special = ["20160128", "20200528", "20150911"] + [str(num) for num in range(20140101, 20140111)]
    start_date, end_date = Create_Date(YEAR, Begin_date), Create_Date(YEAR, End_date)
    current_date = start_date
    THREAD_SAFE_PRINT("Check PDF Exist", f"Checking {YEAR} PDF Exist ({Folder_Path})", Log_File_Path)
    while current_date <= end_date:
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        DATE = f"{YEAR}{MONTH}{DAY}"
        PATH = Folder_Path + f"{YEAR}/{YEAR}{MONTH}{DAY}/"
        if DATE in Special: 
            current_date += timedelta(days=1)
            continue
        if not os.path.exists(PATH): 
            THREAD_SAFE_PRINT("Check PDF Exist", f"{PATH} is not exist.", Log_File_Path)
            MISSING_PDF.append(PATH)
            current_date += timedelta(days=1)
            continue
        All_Pages_No = 0
        # List all files in the folder
        for filename in os.listdir(PATH):
            if filename.endswith("pdf"):
                file_path = PATH + filename
                with open(file_path, "rb") as file:
                    PDF = PdfReader(file)
                    All_Pages_No += len(PDF.pages)
        if All_Pages_No not in {4, 8, 12, 20, 16, 24, 32, 28}: 
            THREAD_SAFE_PRINT("Check PDF Exist", f"{PATH} is incomplete ({All_Pages_No} pages)", Log_File_Path)
            MISSING_PDF.append(PATH)
        current_date += timedelta(days=1)
    return MISSING_PDF

# Split PDF
def PDF_Split_All(pdf_path, delete_original=False, Log_File_Path=""):
    """
    - Attention: The pages in PyPDF2 start with 0.
    """
    base_path = os.path.dirname(pdf_path) + "/"
    filename = os.path.basename(pdf_path)
    file = filename.split(".")[0]
    suffix = filename.split(".")[1]
    PDF = PdfReader(pdf_path)
    num_of_pages = len(PDF.pages)
    THREAD_SAFE_PRINT("PDF Split All", f"{pdf_path} with {num_of_pages} pages", Log_File_Path)
    if num_of_pages > 1:
        Success = True
        for i in range(num_of_pages):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(PDF.pages[i])
            version = Format_Num(str(i + 1))
            PDF_Output = base_path + f"{file}{version}.{suffix}"
            with open(PDF_Output, "wb") as pdf_output:
                pdf_writer.write(pdf_output)
                Success &= True
                THREAD_SAFE_PRINT("PDF Split All", f"Output path: {PDF_Output}", Log_File_Path)
        if Success and delete_original: 
            os.remove(pdf_path)
            THREAD_SAFE_PRINT("PDF Split All", f"Successfully deleted {pdf_path}", Log_File_Path)

def Fix_PDF_Name(Folder_Path, Log_File_Path=""):
    """
    - Fix error name like 2024010412_12_FAD.png to 20240104_12_FAD.png
    """
    for root, _, files in os.walk(Folder_Path):
        for file in files:
            if file.lower().endswith('.png') or file.lower().endswith('.json'):
                file_split_list = file.split("_")
                filename = file_split_list[0]
                if len(filename) != 8:
                    # Extract parts from the matched groups
                    date_part = filename[:8]  # First 8 digits (YYYYMMDD)
                    file_split_list.remove(file_split_list[0])
                    rest = "_".join(file_split_list)       # Everything between the date and extension (e.g., _1_1)
                    
                    # Construct the new filename
                    new_name = f"{date_part}_{rest}"
                    
                    # Full paths for the old and new names
                    old_path = root.replace("\\", "/") + f"/{file}"
                    new_path = root.replace("\\", "/") + f"/{new_name}"
                    
                    # Rename the file if the new name is different
                    if old_path != new_path:
                        try:
                            os.rename(old_path, new_path)
                            THREAD_SAFE_PRINT("Fix PDF Name", f"Renamed: {old_path} -> {new_path}", Log_File_Path)
                        except OSError as e:
                            THREAD_SAFE_PRINT("Fix PDF Name", f"Error renaming {old_path}: {e}", Log_File_Path)

if __name__ == "__main__":
    Check_PDF_Exist(YEAR="2012", Folder_Path="H:/AI_Data/RMRB/")