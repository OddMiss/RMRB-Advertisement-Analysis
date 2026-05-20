import os
import sys
# Get the folder where THIS script is running
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add that folder to the system path
if script_dir not in sys.path:
    sys.path.append(script_dir)

from RMRB_Main import Check_Summary_Completion, Text_Summary, Get_All_Models
from Config.Config import EXTERNAL_PATH_LIST, EXTERNAL_PATH, MODEL_PATH
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
Sleeping = InputUtils.Sleeping

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
        LogFilePath = EXTERNAL_PATH + "Log/" + datetime.now().strftime("%Y-%m") + "/LLM-Main-" + NowTime(LogFormat=True) + ".log"
        THREAD_SAFE_PRINT("LLM Main", "Invalid input ❌❌❌", LogFilePath)
        exit()
    LOG_PATH = External_Path + "Log/" + datetime.now().strftime("%Y-%m") + "/"
    API_USAGE_PATH = External_Path + "Log/API-Usage/"
    API_USAGE_FILE = API_USAGE_PATH + "Success-Fail-Num-" + NowTime(LogFormat=True) + ".json"
    Check_File(File_Path=API_USAGE_FILE, Json_Bool=False)
    LogFilePath = LOG_PATH + "LLM-Main" + "-" + NowTime(LogFormat=True) + ".log"
    
    # Display exist folders
    PDF_PATH_ALL = [External_Path] + Get_Subfolders(External_Path)
    MSG = "Exist Folders.\n"
    for path in PDF_PATH_ALL:
        MSG += f"{path}\n"
    THREAD_SAFE_PRINT("LLM Main", MSG, LogFilePath)
    
    # Get all models
    All_Models = Get_All_Models(API_Usage_Path=API_USAGE_PATH, Log_File_Path=LogFilePath)
    
    RAM_USAGE(Log_File_Path=LogFilePath)
    # Input threshold number
    Threshold_Num = int(input("Please input threshold number (int): "))
    
    # Choose year
    YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="LLM Main", AD=True, Log_File_Path=LogFilePath)
    Sleeping(INFO="LLM Main", Log_File_Path=LogFilePath)
    Complete, Number_Dict = Check_Summary_Completion(YEAR=YEAR, Folder_Path=External_Path, Threshold_Num=Threshold_Num, Log_File_Path=LogFilePath)
    All_Num = Number_Dict["ALL_NUM"]
    Exist_All_Num = Number_Dict["EXIST_ALL_NUM"]
    if not Complete: 
        Text_Summary(YEAR=YEAR, Folder_Path=External_Path, All_Models=All_Models, API_Usage_File_Path=API_USAGE_FILE, All_Num=All_Num, Exist_All_Num=Exist_All_Num, Threshold_Num=Threshold_Num, Log_File_Path=LogFilePath)