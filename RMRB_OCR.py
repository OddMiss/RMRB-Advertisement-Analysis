import os
import sys
# Get the folder where THIS script is running
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add that folder to the system path
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Allow multiple OpenMP libraries to coexist
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# os.environ["FLAGS_use_mkldnn"] = "0" 
# os.environ["FLAGS_allocator_strategy"] = "auto_growth" # Helps prevent reserving too much RAM at once

# Limit this process to use only half threads (to reduce CPU usage)
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["PADDLE_NUM_THREADS"] = "4"

import faulthandler
faulthandler.enable()

from RMRB_Main import Text_Recognition, Check_OCR_Completion
from paddleocr import PPStructureV3
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
Choose_Date = InputUtils.Choose_Date

def PPStructureV3_Pipeline(Model_Path):
    pipeline_v3 = PPStructureV3(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_region_detection=False,
        use_seal_recognition=False,
        use_textline_orientation=False,
        use_formula_recognition=False,
        use_table_recognition=False,
        use_chart_recognition=False,
        layout_detection_model_dir=Model_Path + "PP-DocLayout_plus-L_infer/",
        text_detection_model_dir=Model_Path + "PP-OCRv5_server_det_infer/",
        text_recognition_model_dir=Model_Path + "PP-OCRv5_server_rec_infer/",
        chart_recognition_model_dir=Model_Path + "PP-Chart2Table_infer/",
        
        # These go into **kwargs and control the C++ backend
        # use_mkldnn=False  # This is the most important one for "Access Violation"
        # Limit the image size specifically for text detection to save RAM
        text_det_limit_side_len=960,  
        text_det_limit_type='max',
    )
    return pipeline_v3

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
        LogFilePath = EXTERNAL_PATH + "Log/" + datetime.now().strftime("%Y-%m") + "/OCR-Main-" + NowTime(LogFormat=True) + ".log"
        THREAD_SAFE_PRINT("OCR Main", "Invalid input ❌❌❌", LogFilePath)
        exit()
    LOG_PATH = External_Path + "Log/" + datetime.now().strftime("%Y-%m") + "/"
    LogFilePath = LOG_PATH + "OCR-Main" + "-" + NowTime(LogFormat=True) + ".log"
    
    # Show Python interpreter path
    THREAD_SAFE_PRINT("OCR Main", f"Python Interpreter Path: {os.sys.executable}", LogFilePath)
    THREAD_SAFE_PRINT("OCR Main", sys.path, LogFilePath)
    
    # Display exist folders
    PDF_PATH_ALL = [External_Path] + Get_Subfolders(External_Path)
    MSG = "Exist Folders.\n"
    for path in PDF_PATH_ALL:
        MSG += f"{path}\n"
    THREAD_SAFE_PRINT("OCR Main", MSG, LogFilePath)
    
    RAM_USAGE(Log_File_Path=LogFilePath)
    # pipeline_v3 = PPStructureV3_Pipeline(Model_Path=MODEL_PATH)

    # Choose year
    YEAR = Choose_A_Year(Folder_Path=External_Path, INFO="OCR Main", AD=True, Log_File_Path=LogFilePath)
    Sleeping(INFO="OCR Main", Log_File_Path=LogFilePath)
    Complete = Check_OCR_Completion(YEAR=YEAR, Folder_Path=External_Path, Log_File_Path=LogFilePath)
    if not Complete: 
        pipeline_v3 = PPStructureV3_Pipeline(Model_Path=MODEL_PATH)
        RAM_USAGE(Log_File_Path=LogFilePath)
        Text_Recognition(YEAR=YEAR, Folder_Path=External_Path, Pipeline=pipeline_v3, Log_File_Path=LogFilePath)