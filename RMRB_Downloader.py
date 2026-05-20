import os
import sys
# Get the folder where THIS script is running
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add that folder to the system path
if script_dir not in sys.path:
    sys.path.append(script_dir)

from RMRB_Main import RMRB_PDF_Downloader, Check_RMRB_Exist
from Config.Config import EXTERNAL_PATH_LIST, EXTERNAL_PATH, WEEKDAY_DICT
# from Config.Config import LOG_PATH
from datetime import datetime
from Utils.main import FileUtils, PrintUtils, TimeUtils
Check_Folder = FileUtils.Check_Folder
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
NowTime = TimeUtils.NowTime

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
        LogFilePath = EXTERNAL_PATH + "Log/" + datetime.now().strftime("%Y-%m") + "/RMRB-Downloader-" + NowTime(LogFormat=True) + ".log"
        THREAD_SAFE_PRINT("RMRB Downloader Main", "Invalid input ❌❌❌", LogFilePath)
        exit()
    LOG_PATH = External_Path + "Log/" + datetime.now().strftime("%Y-%m") + "/"
    LogFilePath = LOG_PATH + "RMRB-Downloader-" + "-" + NowTime(LogFormat=True) + ".log"
    Check_Folder(LOG_PATH, LogFilePath)
    
    # Choose functions
    THREAD_SAFE_PRINT("RMRB Downloader Main", "#" * 10 + "Welcome to RMRB download stript" + "#" * 10, LogFilePath)
    TODAY = datetime.today().strftime("%Y%m%d")
    # Get the weekday (0=Monday, 6=Sunday) and adjust it so that Monday is 1 and Sunday is 7
    WEEKDAY = datetime.today().weekday() + 1  # weekday() returns 0=Monday, 6=Sunday, so add 1 to make Monday=1
    THREAD_SAFE_PRINT("RMRB Downloader Main", 
          f"Today's date: {TODAY}. Today's weekday: {WEEKDAY_DICT[str(WEEKDAY)]}", 
          LogFilePath)
    THREAD_SAFE_PRINT("RMRB Downloader Main", 
          """Download type: \n C: Customized Dates \n T: Download Today's RMRB \n U: Download RMRB from 20250101 Until Today \n S: Download RMRB for specific date of version (like 2024122401)""", 
          LogFilePath)
    
    while True:
        TYPE = input("Please input type: ")
        # C: Customized Dates
        if TYPE == "C": 
            while True:
                BEGIN_DATE = input("Please input start date: (Format like YYYYMMDD: 19491001): ")
                # Basic validation
                if not (len(BEGIN_DATE) == 8 and BEGIN_DATE.isdigit()):
                    THREAD_SAFE_PRINT("RMRB Downloader Main", "Invalid date format. Please make sure it's in YYYYMMDD format.", LogFilePath)
                else: break
            while True:
                END_DATE = input("Please input end date: (Format like YYYYMMDD: 19491001): ")
                if not (len(END_DATE) == 8 and END_DATE.isdigit()):
                    THREAD_SAFE_PRINT("RMRB Downloader Main", "Invalid date format. Please make sure it's in YYYYMMDD format.", LogFilePath)
                else: break
            RMRB_PDF_Downloader(Begin_date=BEGIN_DATE, End_date=END_DATE, Download_Path=External_Path, Log_File_Path=LogFilePath)
        # T: Download Today's RMRB
        elif TYPE == "T": 
            today = datetime.today().strftime('%Y%m%d')
            RMRB_PDF_Downloader(Begin_date=today, End_date=today, Download_Path=External_Path, Log_File_Path=LogFilePath)
        # U: Download RMRB from 20260101 Until Today
        elif TYPE == "U":
            Missing_Dates = Check_RMRB_Exist(Begin_date="20260101", End_date=TODAY, Download_Path=External_Path, Log_File_Path=LogFilePath)
            if len(Missing_Dates):
                THREAD_SAFE_PRINT("RMRB Downloader Main", "The missing dates:", LogFilePath)
                for date in Missing_Dates:
                    THREAD_SAFE_PRINT("RMRB Downloader Main", date, LogFilePath)
                Download = input("Download (Y/N)? ")
                if Download == "Y":
                    for date in Missing_Dates:
                        RMRB_PDF_Downloader(Begin_date=date, End_date=date, Download_Path=External_Path, Log_File_Path=LogFilePath)
                elif Download == "N": exit()
                else: THREAD_SAFE_PRINT("RMRB Downloader Main", "Invalid input, please input Y or N.", LogFilePath)
            else: 
                THREAD_SAFE_PRINT("RMRB Downloader Main", "There is no missing date from 20260101 until today", LogFilePath)
                exit()
        # S: Download RMRB for specific date of version (like 2024122401)
        elif TYPE == "S":
            while True:
                DATE = input("Please input date and version (like 2024122401): ")
                if not (len(DATE) == 10 and DATE.isdigit()):
                    THREAD_SAFE_PRINT("RMRB Downloader Main", "Invalid date format. Please make sure it's in YYYYMMDDVV format.", LogFilePath)
                # else: RMRB_PDF_Specific_Version(DATE=DATE[:8], Version=DATE[8:], Download_Path=External_Path, Log_File_Path=LogFilePath)
                else: 
                    Custom_Version = DATE[-2:]
                    RMRB_PDF_Downloader(Begin_date=DATE[:8], End_date=DATE[:8], Custom_Versions=[Custom_Version], Download_Path=External_Path)
        else: THREAD_SAFE_PRINT("RMRB Downloader Main", "Invalid input, please input C or Y or U or S.", LogFilePath)