import sys
import os
# Get the folder where THIS script is running
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add that folder to the system path
if script_dir not in sys.path:
    sys.path.append(script_dir)

from RMRB_Main import Genetare_AD_Image, Genetare_AD_Image_New, Extract_AD_Block, Check_Duplicated_Images, AD_Shape_Analysis
from Config.Config import EXTERNAL_PATH_LIST, EXTERNAL_PATH
from datetime import datetime
from Utils.main import PrintUtils, JsonUtils, FileUtils, TimeUtils, InputUtils
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
NowTime = TimeUtils.NowTime
Get_Subfolders = FileUtils.Get_Subfolders
Choose_A_Year = InputUtils.Choose_A_Year
Sleeping = InputUtils.Sleeping
Choose_Date = InputUtils.Choose_Date

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
        LogFilePath = EXTERNAL_PATH + "Log/" + datetime.now().strftime("%Y-%m") + "/RMRB-AD-Image-Generator-" + NowTime(LogFormat=True) + ".log"
        THREAD_SAFE_PRINT("RMRB AD Image Generator", "Invalid input ❌❌❌", LogFilePath)
        exit()
    LOG_PATH = External_Path + "Log/" + datetime.now().strftime("%Y-%m") + "/"
    LogFilePath = LOG_PATH + "RMRB-AD-Image-Generator" + "-" + NowTime(LogFormat=True) + ".log"
    THREAD_SAFE_PRINT("RMRB AD Image Generator", sys.path, LogFilePath)
    
    # Display exist folders
    PDF_PATH_ALL = [External_Path] + Get_Subfolders(External_Path)
    MSG = "Exist Folders.\n"
    for path in PDF_PATH_ALL:
        MSG += f"{path}\n"
    THREAD_SAFE_PRINT("RMRB AD Image Generator", MSG, LogFilePath)
    
    while True:
        # Choose options
        OPTIONS = ["Generate AD Image", "Extract AD Block", "Check Duplicated Images"]
        OPTIONS_MSG = "Choose the options.\n"
        OPTIONS_MSG_CHOICE_DICT = {}
        for num, option in enumerate(OPTIONS):
            OPTIONS_MSG += f"{num + 1}: {option}\n"
            OPTIONS_MSG_CHOICE_DICT[str(num + 1)] = path
        Options_Choice = input(OPTIONS_MSG)
        if not Options_Choice in list(OPTIONS_MSG_CHOICE_DICT.keys()): 
            THREAD_SAFE_PRINT("RMRB AD Image Generator", "Invalid input ❌❌❌", LogFilePath)
            continue
        
        if Options_Choice == "1":
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            BEGIN_DATE, END_DATE = Choose_Date(INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            Sleeping(INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            NEW_OLD = input("New or Old? (n/o) ")
            if NEW_OLD == "n":
                Genetare_AD_Image_New(
                    YEAR=YEAR, Folder_Path=External_Path,
                    Begin_date=BEGIN_DATE, End_date=END_DATE, 
                    Log_File_Path=LogFilePath)
            elif NEW_OLD == "o":
                Genetare_AD_Image(
                    YEAR=YEAR, Folder_Path=External_Path,
                    Begin_date=BEGIN_DATE, End_date=END_DATE, 
                    Log_File_Path=LogFilePath)
            else:
                THREAD_SAFE_PRINT("RMRB AD Image Generator", "Invalid input ❌❌❌", LogFilePath)
                continue
        elif Options_Choice == "2":
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            BEGIN_DATE, END_DATE = Choose_Date(INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            Sleeping(INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            Extract_AD_Block(
                YEAR=YEAR, Folder_Path=External_Path, 
                Begin_date=BEGIN_DATE, End_date=END_DATE, 
                Log_File_Path=LogFilePath)
        elif Options_Choice == "3":
            YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            Sleeping(INFO="RMRB AD Image Generator", Log_File_Path=LogFilePath)
            AD_Shape_Analysis(YEAR=YEAR, Folder_Path=External_Path, IS_CMD=True, Log_File_Path=LogFilePath)
            Check_Duplicated_Images(YEAR=YEAR, Folder_Path=External_Path, IS_CMD=True, Log_File_Path=LogFilePath)