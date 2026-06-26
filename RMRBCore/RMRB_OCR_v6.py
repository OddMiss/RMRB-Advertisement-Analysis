import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from datetime import datetime, timedelta
import time
import os
from Utils.main import PrintUtils, FileUtils, JsonUtils, TimeUtils, TextUtils
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict
Dict_to_JsonFile = JsonUtils.Dict_to_JsonFile
Generate_Dates = TimeUtils.Generate_Dates
Format_Num = TextUtils.Format_Num

def OCR(Pipeline, Image_Path, OCR_Model="Paddeocr_V3", Log_File_Path=""):
    """
    - OCR funtion using pipeline
    - Default Model for current project is Paddeocr V3
    - Exclusively designed for Paddle OCR
    """
    try:
        THREAD_SAFE_PRINT(f"OCR-{OCR_Model}", f"{Image_Path} Generating...", Log_File_Path)
        result = Pipeline.predict(input=Image_Path) # format like [{}]
        time.sleep(2) # have a rest
        result_dict = result[0]
        Content = []
        for block in result_dict["parsing_res_list"]:
            Content.append(block.content)
        Output = "".join(Content).replace("\n\n", "\n")
        Output_Print = Output.replace("\n", "")
        THREAD_SAFE_PRINT(f"OCR-{OCR_Model}", f"✅ {Output_Print[:60]}... (Length: {len(Output)})", Log_File_Path)
        return True, Output
    except Exception as e:
        error_msg = f"❌OCR Error: {type(e).__name__} ({str(e)}) with {Image_Path}"
        THREAD_SAFE_PRINT(f"OCR-{OCR_Model}", error_msg, Log_File_Path)
        return False, e

def Check_OCR_Completion(YEAR, Folder_Path, OCR_Model="Paddeocr_V3", Begin_date="0101", End_date="1231", Log_File_Path=""):
    """
    - Check OCR completion by checking json file content
    """
    Complete_Date_List = set()
    Incomplete_Date_List = set()
    AD_PATH = Folder_Path + f"{YEAR}_AD/"
    Check_Folder(Folder_Path=AD_PATH, Log_File_Path=Log_File_Path)
    Filter_Path = f"{AD_PATH}{YEAR}_Shape_Dict_Final_Filter_Outlier.json"
    Filter_File_Bool = Check_File(File_Path=Filter_Path, Create_New=False)
    if not Filter_File_Bool: THREAD_SAFE_PRINT("Check OCR Completion", f"{Filter_Path} does not exist! Please run 'Check_Duplicated_Images'", Log_File_Path)
    Filter_List = JsonFile_to_Dict(filename=Filter_Path, Log_File_Path=Log_File_Path).get("Final_Filter", [])
    if not Filter_List: THREAD_SAFE_PRINT("Check OCR Completion", f"{Filter_Path} is empty! Please run 'Check_Duplicated_Images'", Log_File_Path)
    start_date = datetime(int(YEAR), int(Begin_date[:2]), int(Begin_date[2:]))
    end_date = datetime(int(YEAR), int(End_date[:2]), int(End_date[2:]))
    THREAD_SAFE_PRINT("Check OCR Completion", f"Checking {YEAR} completion...", Log_File_Path)
    current_date = start_date
    while current_date <= end_date:
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        AD_Folder_PATH = AD_PATH + f"{YEAR}{MONTH}{DAY}/"
        if os.path.exists(AD_Folder_PATH): # Note that the path may not exist
            for filename in os.listdir(AD_Folder_PATH):
                file_path = AD_Folder_PATH + filename
                name = filename.split(".")[0]
                suffix = filename.split(".")[1]
                # Check if it is a file (not a directory)
                if os.path.isfile(file_path) and suffix == "png": # Ensure it is a png file
                    name_split_list = name.split('_')
                    # Ensure the image is an ad block or full ad
                    FAD_BOOL = "FAD" in name_split_list
                    BLOCK_BOOL = "Block" in name_split_list
                    FILTER_BOOL = filename in Filter_List
                    if FAD_BOOL or (BLOCK_BOOL and FILTER_BOOL):
                        Text_Dict_Path = f"{AD_Folder_PATH}{name}.json"
                        Check_File(Text_Dict_Path)
                        Text_Dict = JsonFile_to_Dict(Text_Dict_Path, Log_File_Path=Log_File_Path)
                        if Text_Dict.get(f"OCR_{OCR_Model}", ""): Complete_Date_List.update({f"{MONTH}{DAY}"})
                        else: Incomplete_Date_List.update({f"{MONTH}{DAY}"})
        current_date += timedelta(days=1)
    # Convert to sorted list
    Complete_Date_List_Sort = sorted(Complete_Date_List)
    Incomplete_Date_List_Sort = sorted(Incomplete_Date_List)
    THREAD_SAFE_PRINT("Check OCR Completion", f"Complete: {Complete_Date_List_Sort}", Log_File_Path)
    THREAD_SAFE_PRINT("Check OCR Completion", f"Incomplete: {Incomplete_Date_List_Sort}", Log_File_Path)
    if Incomplete_Date_List: return False
    else: return True

def Text_Recognition(YEAR, Folder_Path, Pipeline, OCR_Model="Paddeocr_V3", Begin_date="0101", End_date="1231", Log_File_Path=""):
    """
    - Each image has its own Text_Dict, which contains OCR content/length and summary content
    - For OCR content, the key format are f"OCR_{Model_Name}" and f"OCR_{Model_Name}_Len"
    - Pipeline is for Paddle OCR
    """
    AD_PATH = Folder_Path + f"{YEAR}_AD/"
    Check_Folder(Folder_Path=AD_PATH, Log_File_Path=Log_File_Path)
    Filter_Path = f"{AD_PATH}{YEAR}_Shape_Dict_Final_Filter_Outlier.json"
    Filter_File_Bool = Check_File(File_Path=Filter_Path, Create_New=False)
    if not Filter_File_Bool: THREAD_SAFE_PRINT("Text Recognition", f"{Filter_Path} does not exist! Please run 'Check_Duplicated_Images'", Log_File_Path)
    Filter_List = JsonFile_to_Dict(filename=Filter_Path, Log_File_Path=Log_File_Path).get("Final_Filter", [])
    if not Filter_List: THREAD_SAFE_PRINT("Text Recognition", f"{Filter_Path} is empty! Please run 'Check_Duplicated_Images'", Log_File_Path)
    start_date = datetime(int(YEAR), int(Begin_date[:2]), int(Begin_date[2:]))
    end_date = datetime(int(YEAR), int(End_date[:2]), int(End_date[2:]))
    THREAD_SAFE_PRINT("Text Recognition", f"Begin date: {YEAR + Begin_date}, End date: {YEAR + End_date}", Log_File_Path)
    current_date = start_date
    while current_date <= end_date:
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        AD_Folder_PATH = AD_PATH + f"{YEAR}{MONTH}{DAY}/"
        if os.path.exists(AD_Folder_PATH): # Note that the path may not exist
            for filename in os.listdir(AD_Folder_PATH):
                file_path = AD_Folder_PATH + filename
                name = filename.split(".")[0]
                suffix = filename.split(".")[1]
                # Check if it is a file (not a directory)
                if os.path.isfile(file_path): # Ensure it is a file
                    if suffix == "png":
                        name_split_list = name.split('_')
                        # Ensure the image is an ad block or full ad
                        FAD_BOOL = "FAD" in name_split_list
                        BLOCK_BOOL = "Block" in name_split_list
                        FILTER_BOOL = filename in Filter_List
                        if FAD_BOOL or (BLOCK_BOOL and FILTER_BOOL):
                            Text_Dict_Path = f"{AD_Folder_PATH}{name}.json"
                            Check_File(Text_Dict_Path)
                            Text_Dict = JsonFile_to_Dict(Text_Dict_Path, Log_File_Path=Log_File_Path)
                            if not Text_Dict.get(f"OCR_{OCR_Model}", ""): # Avoid repeat generation if it exists.
                                Success, Content = OCR(
                                    Pipeline=Pipeline, OCR_Model=OCR_Model, 
                                    Image_Path=file_path, Log_File_Path=Log_File_Path)
                                if Success:
                                    Text_Dict[f"OCR_{OCR_Model}"] = Content
                                    Text_Dict[f"OCR_{OCR_Model}_Len"] = len(Content)
                                    Dict_to_JsonFile(Text_Dict, Text_Dict_Path)
                                    THREAD_SAFE_PRINT("Text Recognition", f"OCR text is stored in {Text_Dict_Path}", Log_File_Path)
                                else: continue
        current_date += timedelta(days=1)

if __name__ == "__main__":
    from Config.Config import MAIN_PATH
    Check_OCR_Completion(YEAR="2025", Folder_Path=MAIN_PATH)