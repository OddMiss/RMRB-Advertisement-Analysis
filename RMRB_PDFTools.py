import os
import shutil
import sys
# Get the folder where THIS script is running
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add that folder to the system path
if script_dir not in sys.path:
    sys.path.append(script_dir)

from RMRB_Main import Check_Mac, Check_PDF_Exist, PDF_Split_All, Fix_PDF_Name
from Config.Config import EXTERNAL_PATH_LIST, EXTERNAL_PATH
from datetime import datetime
from Utils.main import PrintUtils, JsonUtils, FileUtils, TimeUtils, SystemUtils, InputUtils
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
NowTime = TimeUtils.NowTime
Get_Subfolders = FileUtils.Get_Subfolders
RAM_USAGE = SystemUtils.RAM_USAGE
Choose_A_Year = InputUtils.Choose_A_Year

def PDF_Splitter(Folder_Path, Delete_Original=False, Log_File_Path=""):
    for root, _, filenames in os.walk(Folder_Path):
        for filename in filenames:
            if len(filename.split(".")[0]) == 8: # ensure it is single day's file
                file_path = f"{root}/{filename}"
                PDF_Split_All(pdf_path=file_path, delete_original=Delete_Original, Log_File_Path=Log_File_Path)

def Folder_Formatter(YEAR, Folder_Path, Log_File_Path=""):
    PATH = f"{Folder_Path}{YEAR}/"
    # Get all files in current folder
    for filename in os.listdir(PATH):
        if os.path.isfile(f"{PATH}{filename}"):
            if filename[:8].isdigit():
                # Extract date part (first 8 digits)
                date_part = filename[:8]
                
                # Create folder if it doesn't exist
                if not os.path.exists(PATH + date_part):
                    os.makedirs(PATH + date_part)
                
                file_path = PATH + filename
                # Move file to folder
                shutil.move(file_path, os.path.join(PATH, date_part))
                THREAD_SAFE_PRINT("Folder Formatter", f"Moved {filename} to {date_part}/", Log_File_Path)

if __name__ == "__main__":
    # Choose external path
    EXTERNAL_MSG = "Choose the external path.\n"
    EXTERNAL_PATH_CHOICE_DICT = {}
    for num, path in enumerate(EXTERNAL_PATH_LIST):
        if num + 1 == 1: EXTERNAL_MSG += f"(Default) {num + 1}: {path}\n"
        else: EXTERNAL_MSG += f"{num + 1}: {path}\n"
        EXTERNAL_PATH_CHOICE_DICT[str(num + 1)] = path
    External_Path_Choice = input(EXTERNAL_MSG)
    if External_Path_Choice in list(EXTERNAL_PATH_CHOICE_DICT.keys()): 
        External_Path = EXTERNAL_PATH_CHOICE_DICT[External_Path_Choice]
    else: 
        LogFilePath = EXTERNAL_PATH + "Log/" + datetime.now().strftime("%Y-%m") + "/PDFTools-" + NowTime(LogFormat=True) + ".log"
        THREAD_SAFE_PRINT("PDFTools", "Invalid input ❌❌❌", LogFilePath)
        exit()
    LOG_PATH = External_Path + "Log/" + datetime.now().strftime("%Y-%m") + "/"
    LogFilePath = LOG_PATH + "PDFTools" + "-" + NowTime(LogFormat=True) + ".log"
    
    THREAD_SAFE_PRINT("PDFTools", sys.path, LogFilePath)
    
    # Display exist folders
    PDF_PATH_ALL = [External_Path] + Get_Subfolders(External_Path)
    MSG = "Exist Folders.\n"
    for path in PDF_PATH_ALL:
        MSG += f"{path}\n"
    THREAD_SAFE_PRINT("PDFTools", MSG, LogFilePath)

    # Candidate tools
    # Check and delte mac pdf
    # Exist checker
    # Splitter
    TOOL_LIST = ["MAC PDF Checker", "Folder Formatter", "Exist Checker", "PDF Splitter", "Fix PDF Name"]
    TOOL_HELP_DICT = {
        "MAC PDF Checker": "Check and delete PDF file contains MAC.",
        "Folder Formatter": "Format the folder structure by moving files into date-named folders.",
        "Exist Checker": "Check for missing or incomplete PDF files in the specified year folder.",
        "PDF Splitter": "Split multi-page PDF files into single-page files.",
        "Fix PDF Name": "Fix erroneous PDF file names with extra date digits. (e.g., 2024010412_12_FAD.png to 20240104_12_FAD.png)",
    }
    
    while True:
        RAM_USAGE(Log_File_Path=LogFilePath)
        
        # Choose tools
        TOOL_MSG = "Choose the external path.\n"
        TOOL_CHOICE_DICT = {}
        for num, tool in enumerate(TOOL_LIST):
            TOOL_MSG += f"{num + 1}: {tool} {TOOL_HELP_DICT[tool]}\n"
            TOOL_CHOICE_DICT[str(num + 1)] = tool
        Tool_Choice = input(TOOL_MSG)
        if Tool_Choice in list(TOOL_CHOICE_DICT.keys()): 
            Tool = TOOL_CHOICE_DICT[Tool_Choice]
        else: 
            THREAD_SAFE_PRINT("PDFTools", "Invalid input ❌❌❌", LogFilePath)
            continue
        if Tool in ["MAC PDF Checker"]:
            # Choose year
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="PDFTools", Log_File_Path=LogFilePath)
            Folder_Path = External_Path + YEAR + "/"
            Check_Mac(Folder_Path=Folder_Path, Delete=True, Log_File_Path=LogFilePath)
        elif Tool in ["Folder Formatter"]:
            # Choose year
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="PDFTools", Log_File_Path=LogFilePath)
            Folder_Path = External_Path + YEAR + "/"
            Folder_Formatter(YEAR=YEAR, Folder_Path=External_Path, Log_File_Path=LogFilePath)
        elif Tool in ["Exist Checker"]:
            # Choose year
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="PDFTools", Log_File_Path=LogFilePath)
            Folder_Path = External_Path + YEAR + "/"
            Check_PDF_Exist(YEAR=YEAR, Folder_Path=External_Path, Log_File_Path=LogFilePath)
        elif Tool in ["PDF Splitter"]:
            # Choose year
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="PDFTools", Log_File_Path=LogFilePath)
            Folder_Path = External_Path + YEAR + "/"
            PDF_Splitter(Folder_Path=Folder_Path, Delete_Original=True, Log_File_Path=LogFilePath)
        elif Tool in ["Fix PDF Name"]:
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="PDFTools", AD=True, Log_File_Path=LogFilePath)
            Folder_Path = f"{External_Path}{YEAR}_AD/"
            Fix_PDF_Name(Folder_Path=Folder_Path, Log_File_Path=LogFilePath)
        else: 
            THREAD_SAFE_PRINT("PDFTools", "Tool not implemented ❌❌❌", LogFilePath)
            continue