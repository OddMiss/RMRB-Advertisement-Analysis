import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from datetime import datetime, timedelta
import numpy as np
import pdfplumber
import fitz
from collections import defaultdict
from collections import Counter
import matplotlib.pyplot as plt
from pdf2image import convert_from_path
from RMRBCore.RMRB_PDF_v5 import Check_PDF_Exist
from RMRBCore.RMRB_Image_v5 import CV_Detect_Ads
from Config.Config import Advertisement_Text, Cipher_AD
from Utils.main import PrintUtils, FileUtils, JsonUtils, TimeUtils, TextUtils
Create_Date = TimeUtils.Create_Date
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
Compare_File_Sizes = FileUtils.Compare_File_Sizes
Update_File_Lists = FileUtils.Update_File_Lists
Get_File_Size = FileUtils.Get_File_Size
Get_Full_Path = FileUtils.Get_Full_Path
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict
Dict_to_JsonFile = JsonUtils.Dict_to_JsonFile
Format_Num = TextUtils.Format_Num
Terminal_Clickable_Text = TextUtils.Terminal_Clickable_Text

def Terminal_Clickable_Text(original_text, display_text, is_cmd=False):
    if is_cmd: return f"\033]8;;file://{original_text}\a{display_text}\033]8;;\a"
    else: return original_text

def Genetare_AD_Image(YEAR, Folder_Path, Poppler_Path="", Begin_date="0101", End_date="1231", Text_Range=34, Log_File_Path=""):
    """
    - Core function of AD image generation
    - Generate image for all ad pages
    - Suppose each PDF contains just one version content
    """
    PDF_CHECK = Check_PDF_Exist(
        YEAR=YEAR, Folder_Path=Folder_Path, 
        Begin_date=Begin_date, End_date=End_date,
        Log_File_Path=Log_File_Path)
    if PDF_CHECK: 
        THREAD_SAFE_PRINT("Generate AD Image", f"PDF lackage! ({PDF_CHECK})", Log_File_Path)
        return
    AD_PATH = Folder_Path + f"{YEAR}_AD/" # Advertisement Data Path
    Check_Folder(Folder_Path=AD_PATH, Log_File_Path=Log_File_Path)
    start_date, end_date = Create_Date(YEAR, Begin_date), Create_Date(YEAR, End_date)
    THREAD_SAFE_PRINT("Generate AD Image", f"Begin date: {YEAR + Begin_date}, End date: {YEAR + End_date}", Log_File_Path)
    current_date = start_date
    while current_date <= end_date:
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        PDF_DATE_PATH = Folder_Path + f"{YEAR}/{YEAR}{MONTH}{DAY}/"
        AD_DATE_PATH = AD_PATH + f"{YEAR}{MONTH}{DAY}/"
        THREAD_SAFE_PRINT("Generate AD Image", f"AD PATH: {PDF_DATE_PATH}", Log_File_Path)
        for filename in os.listdir(PDF_DATE_PATH):
            File_Name_No_Suffix = filename.split(".")[0] # without suffix
            Suffix = filename.split(".")[1]
            PDF_Name_Without_Version = File_Name_No_Suffix[:8] # keep only date, not version
            Version = filename.split(".")[0][-2:]
            File_Path = PDF_DATE_PATH + filename
            if Suffix == "pdf":
                with pdfplumber.open(File_Path) as PDF:
                    # PDF = PdfReader(file)
                    if Poppler_Path: IMAGE = convert_from_path(pdf_path=File_Path, poppler_path=Poppler_Path)
                    else: IMAGE = convert_from_path(pdf_path=File_Path)
                    text_original = PDF.pages[0].extract_text().replace(" ", "") # use index 0
                    text = text_original[:Text_Range+1]
                    if Advertisement_Text in text: # First filter: plaintext "广告"
                        Check_Folder(Folder_Path=AD_DATE_PATH, Log_File_Path=Log_File_Path)
                        # Attension: first_page and last_page starts at 1
                        IMAGE_PATH = AD_DATE_PATH + f"{PDF_Name_Without_Version}_{Version}_FAD.png"
                        IMAGE[0].save(IMAGE_PATH, "PNG") # use index 0
                        THREAD_SAFE_PRINT("Generate AD Image", f"Full Ad: {IMAGE_PATH}", Log_File_Path)
                    # elif Advertisement in text_original:
                    #     Remove_File_If_Exists(IMAGE_PATH)
                    elif Cipher_AD in text_original: # Second filter: ciphertext "广告"
                        Check_Folder(Folder_Path=AD_DATE_PATH, Log_File_Path=Log_File_Path)
                        # Attension: first_page and last_page starts at 1
                        # IMAGE = convert_from_path(PDF_PATH, first_page=page_num+1, last_page=page_num+1)
                        IMAGE_PATH = AD_DATE_PATH + f"{PDF_Name_Without_Version}_{Version}_HAD.png"
                        IMAGE[0].save(IMAGE_PATH, "PNG") # use index 0
                        THREAD_SAFE_PRINT("Generate AD Image", f"Half Ad {IMAGE_PATH}", Log_File_Path)
                    else:
                        CV_Detect_Ads(
                            root_path=AD_DATE_PATH, pdf_name=File_Name_No_Suffix, 
                            pdf_version=Version, image_element=IMAGE[0])
        current_date += timedelta(days=1)
# Genetare_AD_Image("2015")
# PDF lackage! ['D:/AI_data_analysis/RMRB/2015/20150307.pdf']

def Genetare_AD_Image_New(YEAR, Folder_Path, Begin_date="0101", End_date="1231", Text_Range=34, Log_File_Path=""):
    """
    - Core function of AD image generation (New)
    - Use fitz (PyMuPDF)
    - Generate image for all ad pages
    - Suppose each PDF contains just one version content
    """
    PDF_CHECK = Check_PDF_Exist(
        YEAR=YEAR, Folder_Path=Folder_Path, 
        Begin_date=Begin_date, End_date=End_date,
        Log_File_Path=Log_File_Path)
    if PDF_CHECK: 
        THREAD_SAFE_PRINT("Generate AD Image", f"PDF lackage! ({PDF_CHECK})", Log_File_Path)
        return
    AD_PATH = Folder_Path + f"{YEAR}_AD/" # Advertisement Data Path
    Check_Folder(Folder_Path=AD_PATH, Log_File_Path=Log_File_Path)
    start_date, end_date = Create_Date(YEAR, Begin_date), Create_Date(YEAR, End_date)
    THREAD_SAFE_PRINT("Generate AD Image", f"Begin date: {YEAR + Begin_date}, End date: {YEAR + End_date}", Log_File_Path)
    current_date = start_date
    while current_date <= end_date:
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        PDF_DATE_PATH = Folder_Path + f"{YEAR}/{YEAR}{MONTH}{DAY}/"
        AD_DATE_PATH = AD_PATH + f"{YEAR}{MONTH}{DAY}/"
        THREAD_SAFE_PRINT("Generate AD Image", f"AD PATH: {PDF_DATE_PATH}", Log_File_Path)
        for filename in os.listdir(PDF_DATE_PATH):
            File_Name_No_Suffix = filename.split(".")[0] # without suffix
            Suffix = filename.split(".")[1]
            Version = filename.split(".")[0][-2:]
            File_Path = PDF_DATE_PATH + filename
            if Suffix == "pdf":
                with pdfplumber.open(File_Path) as PDF:
                    # PDF = PdfReader(file)
                    text_original = PDF.pages[0].extract_text().replace(" ", "") # use index 0
                    text = text_original[:Text_Range+1]
                    # Open the PDF (pymupdf)
                    pymupdf = fitz.open(File_Path)
                    # Loop through pages (here we just take the first page: index 0)
                    page = pymupdf.load_page(0)
                    # Render the page to an image (Pixmap)
                    # matrix = fitz.Matrix(3, 3) makes it 3x higher resolution (cleaner text)
                    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
                    if Advertisement_Text in text: # First filter: plaintext "广告"
                        Check_Folder(Folder_Path=AD_DATE_PATH, Log_File_Path=Log_File_Path)
                        # Attension: first_page and last_page starts at 1
                        IMAGE_PATH = AD_DATE_PATH + f"{File_Name_No_Suffix}_{Version}_FAD.png"
                        pix.save(IMAGE_PATH)
                        THREAD_SAFE_PRINT("Generate AD Image", f"Full Ad: {IMAGE_PATH}", Log_File_Path)
                    # elif Advertisement in text_original:
                    #     Remove_File_If_Exists(IMAGE_PATH)
                    elif Cipher_AD in text_original: # Second filter: ciphertext "广告"
                        Check_Folder(Folder_Path=AD_DATE_PATH, Log_File_Path=Log_File_Path)
                        # Attension: first_page and last_page starts at 1
                        # IMAGE = convert_from_path(PDF_PATH, first_page=page_num+1, last_page=page_num+1)
                        IMAGE_PATH = AD_DATE_PATH + f"{File_Name_No_Suffix}_{Version}_HAD.png"
                        pix.save(IMAGE_PATH)
                        THREAD_SAFE_PRINT("Generate AD Image", f"Half Ad {IMAGE_PATH}", Log_File_Path)
                    else:
                        IMAGE_ARRAY = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                        CV_Detect_Ads(
                            root_path=AD_DATE_PATH, pdf_name=File_Name_No_Suffix, 
                            pdf_version=Version, image_element=IMAGE_ARRAY)
        current_date += timedelta(days=1)

def Extract_AD_Block(
    YEAR, Folder_Path, Begin_date="0101", 
    End_date="1231", Ad_Shape_Analysis=True,
    Log_File_Path=""
):
    """
    - Used after `Genetare_AD_Image` 
    - All image names are formated like this: YYYYMMDD_Version_Type.png
    - Type is in {FAD, HAD, CV}
    - For example: 20220101_8_FAD.png, 20220104_16_CV.png

    - Ad block extraction rules:
    - 1. For "FAD": Igored;
    - 2. For "HAD": Use `CV_Detect_Ads` to detect ad area
    """
    if Ad_Shape_Analysis: SHAPE_DICT = {}
    AD_PATH = Folder_Path + f"{YEAR}_AD/"
    start_date, end_date = Create_Date(YEAR, Begin_date), Create_Date(YEAR, End_date)
    THREAD_SAFE_PRINT("Extract AD Block", f"Begin date: {YEAR + Begin_date}, End date: {YEAR + End_date}", Log_File_Path)
    current_date = start_date
    while current_date <= end_date:
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        AD_Folder_PATH = AD_PATH + f"{YEAR}{MONTH}{DAY}/"
        if os.path.exists(AD_Folder_PATH): # Note that the path may not exist
            THREAD_SAFE_PRINT("Extract AD Block", f"AD PATH: {AD_Folder_PATH}", Log_File_Path)
            for filename in os.listdir(AD_Folder_PATH):
                file_path = os.path.join(AD_Folder_PATH, filename)
                name = filename.split(".")[0]
                suffix = filename.split(".")[1]
                # Check if it is a file (not a directory)
                if os.path.isfile(file_path):  # Ensure it is a file
                    if suffix == "png": # Ensure it is an image
                        # Ensure the image is original (Avoid repeated extraction)
                        name_split_list = name.split("_")
                        if len(name_split_list) == 3:
                            if name_split_list[2] in {"CV", "HAD"}:  # "FAD" ads don't need to extract
                                # Attention that the file names include suffix like '20220104_13_HAD.png'
                                PDF_NAME = name_split_list[0]
                                IMAGE_PATH = os.path.join(AD_Folder_PATH, filename)
                                VERSION = name_split_list[1]
                                TYPE = name_split_list[2]
                                # For result correction, we use original thershold [0.4, 0.6]
                                Shape_Dict = CV_Detect_Ads(
                                    root_path=AD_Folder_PATH,
                                    image_type=TYPE,
                                    pdf_name=PDF_NAME,
                                    pdf_version=VERSION,
                                    image_path=IMAGE_PATH,
                                    Image_Path_Bool=True,
                                    Image_Clip_Bool=True,
                                    Whole_Image_Bool=False,
                                    AD_SHAPE_ANALYSIS=Ad_Shape_Analysis,
                                    Log_File_Path=Log_File_Path
                                )
                                if Ad_Shape_Analysis: SHAPE_DICT.update(Shape_Dict)
        current_date += timedelta(days=1)
    if Ad_Shape_Analysis and SHAPE_DICT: 
        # Saving to a pickle file
        Dict_to_JsonFile(SHAPE_DICT, f"{AD_PATH}{YEAR}_Shape_Dict.json")
        return SHAPE_DICT
    else: return None
# Shape_list = Extract_Ad_Block("2022", Ad_Shape_Analysis=True)
# 2022: 12 mins

def Analysis_AD_Position(YEAR, Folder_Path, Begin_date="0101", End_date="1231", Log_File_Path=""):
    """
    - Analysis ad Advertisement test position
    - Suppose each PDF contains just one version content
    """
    PDF_PATH = Folder_Path + f"{YEAR}/"
    Check_Folder(PDF_PATH)
    Position_Dict = {}
    start_date = datetime(int(YEAR), int(Begin_date[:2]), int(Begin_date[2:]))
    end_date = datetime(int(YEAR), int(End_date[:2]), int(End_date[2:]))
    THREAD_SAFE_PRINT("Analysis of AD Position", f"Begin date: {YEAR + Begin_date}, End date: {YEAR + End_date}", Log_File_Path)
    current_date = start_date
    while current_date <= end_date:
        DATE = current_date.strftime("%Y%m%d")
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        PDF_Folder_PATH = PDF_PATH + f"{YEAR}{MONTH}{DAY}/"
        # PDF_PATH = PATH_FUN(YEAR, MONTH, DAY, "", ".pdf", NAME_bool=False)
        temp_dict = {}
        version_list = []
        for filename in os.listdir(PDF_Folder_PATH):
            PDF_PATH = PDF_Folder_PATH + filename
            Version = filename.split(".")[0][-2:]
            with pdfplumber.open(PDF_PATH) as PDF:
                # PDF = PdfReader(file)
                text = PDF.pages[0].extract_text().replace(" ", "")
                if Advertisement_Text in text:
                    Position = text.find(Advertisement_Text)
                    DICT = {Version: Position}
                    version_list.append(DICT)
        temp_dict[DATE] = version_list
        THREAD_SAFE_PRINT("Analysis of AD Position", temp_dict, Log_File_Path)
        Position_Dict[DATE] = version_list
        current_date += timedelta(days=1)
    
    # Initialize a Counter to keep track of version distributions
    version_distribution = Counter()

    # Iterate over each date and its corresponding list of dictionaries
    for _, versions in Position_Dict.items():
        for version_dict in versions:
            for _, count in version_dict.items():
                version_distribution[count] += 1
    # Prepare data for histogram
    # Get the count values for histogram
    counts = list(version_distribution.elements())

    # Plotting the histogram
    plt.figure(figsize=(10, 6))
    plt.hist(counts, bins=30, color='skyblue', alpha=0.7, edgecolor='black')
    plt.xlabel('Counts')
    plt.ylabel('Frequency')
    plt.title('Histogram of Version Counts')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.show()
# Analysis_AD_Position(YEAR="2025", Folder_Path=EXTERNAL_PATH, Begin_date="1201")

def AD_Shape_Analysis(YEAR, Folder_Path, IS_CMD=False, Log_File_Path=""):
    """
    - Used after `Extract_AD_Block` with "Ad_Shape_Analysis" is True
    """
    def Filter(W, H, W_Divide_H):
        #  Output is True means the picture is correct
        if int(W):
            if int(H):
                if 1.4 <= float(W_Divide_H) <= 1.5: return True
    AD_PATH = Folder_Path + f"{YEAR}_AD/"
    Shape_Dict = JsonFile_to_Dict(f"{AD_PATH}{YEAR}_Shape_Dict.json", Log_File_Path=Log_File_Path)
    Filter_Num = 0
    Outlier_Num = 0
    Output_Dict = {} # Store output
    Filter_list = []
    Outlier_list = []
    Filter_list_With_Shape = []
    Outlier_list_With_Shape = []
    for pdf_name_version in Shape_Dict:
        link = Shape_Dict[pdf_name_version]["output_block_path"] # note that this is relative path like 20250101_1_CV.png
        link_full = Get_Full_Path(AD_PATH, link)
        w = Shape_Dict[pdf_name_version]["w"]
        h = Shape_Dict[pdf_name_version]["h"]
        w_divide_h = Shape_Dict[pdf_name_version]["w_divide_h"]
        if Filter(w, h, w_divide_h):
            # THREAD_SAFE_PRINT("AD Shape Analysis", f"{link_full}, {w}, {h}, {w_divide_h}", Log_File_Path)
            Filter_list_With_Shape.append([link_full, w, h, w_divide_h])
            Filter_list.append(link)
            Filter_Num += 1
        else: 
            Outlier_list_With_Shape.append([link_full, w, h, w_divide_h])
            Outlier_list.append(link)
            Outlier_Num += 1
    for filter_list in Filter_list_With_Shape:
        clickable_text = Terminal_Clickable_Text(filter_list[0], filter_list[0], is_cmd=IS_CMD)
        THREAD_SAFE_PRINT("AD Shape Analysis", f"{clickable_text}, {filter_list[1]}, {filter_list[2]}, {filter_list[3]}", Log_File_Path)
    THREAD_SAFE_PRINT("AD Shape Analysis", f"Filter num: {Filter_Num}", Log_File_Path)
    THREAD_SAFE_PRINT("AD Shape Analysis", "*" * 80, Log_File_Path)
    for outlier_list in Outlier_list_With_Shape:
        clickable_text = Terminal_Clickable_Text(outlier_list[0], outlier_list[0], is_cmd=IS_CMD)
        THREAD_SAFE_PRINT("AD Shape Analysis", f"{clickable_text}, {outlier_list[1]}, {outlier_list[2]}, {outlier_list[3]}", Log_File_Path)
    THREAD_SAFE_PRINT("AD Shape Analysis", f"Outlier num: {Outlier_Num}", Log_File_Path)
    THREAD_SAFE_PRINT("AD Shape Analysis", "*" * 80, Log_File_Path)
    
    Output_Dict["Filter"] = Filter_list
    Output_Dict["Outlier"] = Outlier_list
    Dict_to_JsonFile(Output_Dict, f"{AD_PATH}{YEAR}_Shape_Dict_Filter_Outlier.json")
    THREAD_SAFE_PRINT("AD Shape Analysis", f"✅{AD_PATH}{YEAR}_Shape_Dict_Filter_Outlier.json Stored", Log_File_Path)
# Ad_Shape_Analysis(YEAR="2025", Folder_Path=EXTERNAL_PATH)

def Check_Duplicated_Images(YEAR, Folder_Path, Filter_List_Bool=True, IS_CMD=False, Log_File_Path=""):
    """
    - Filter_List_Bool: If it is True, it means use image paths in Filter_List;
    Or use a whole year's worth of image paths in f"{YEAR}_AD/".
    """
    def get_date_and_version(filepath):
        # Extract the date and the second number from the filename
        filename = os.path.basename(filepath)
        parts = filename.split('_')
        date_part = parts[0]  # 'YYYYMMDD'
        version = parts[1]  # '8', '7', '13', etc.
        return date_part, version

    AD_PATH = Folder_Path + f"{YEAR}_AD/"
    Output_Dict = {}
    Filter_List = []
    Outlier_List = []
    if Filter_List_Bool:
        Filter_Path = f"{AD_PATH}{YEAR}_Shape_Dict_Filter_Outlier.json"
        Filter_File_Bool = Check_File(File_Path=Filter_Path, Create_New=False)
        if Filter_File_Bool:
            Filter_File = JsonFile_to_Dict(Filter_Path, Log_File_Path=Log_File_Path)
            Filter_List = Filter_File["Filter"]
            Outlier_List = Filter_File["Outlier"]
        else:
            THREAD_SAFE_PRINT("Check Duplicated Images", f"{Filter_Path} does not exist!")
            return
    else: 
        for foldername, _, filenames in os.walk(AD_PATH):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                name = filename.split(".")[0]
                suffix = filename.split(".")[1]
                # Check if it is a file (not a directory)
                if os.path.isfile(file_path): # Ensure it is a file
                    if suffix == "png": # Ensure it is an image
                        name_split_list = name.split("_")
                        if "Block" in name_split_list: # Ensure the image is an ad block
                            Filter_List.append(filename)

    # Group images by date and version
    date_version_groups = defaultdict(list)

    for path in Filter_List:
        date_key, version_key = get_date_and_version(path)
        # Use both date and number as the key for grouping
        date_version_groups[(date_key, version_key)].append(path)

    Transfered_Paths = []
    # Display the images grouped by date and second number
    for (date, version), paths in date_version_groups.items():
        if len(paths) > 1:  # Check if there are more than 1 image in the group
            THREAD_SAFE_PRINT("Check Duplicated Images", f"Date: {date}_{version}", Log_File_Path)
            full_largest_path = Get_Full_Path(AD_PATH, paths[0])
            for path in paths:
                full_path = Get_Full_Path(AD_PATH, path)
                full_path_clickable_text = Terminal_Clickable_Text(full_path, full_path, is_cmd=IS_CMD)
                Size = Get_File_Size(file_path=full_path, Log_File_Path=Log_File_Path)
                THREAD_SAFE_PRINT("Check Duplicated Images", f"{full_path_clickable_text} with {(Size / 1024 ** 2):.3f} MB", Log_File_Path)
                Compare = Compare_File_Sizes(file1=full_largest_path, file2=full_path, Log_File_Path=Log_File_Path)
                full_largest_path = Compare if Compare else full_largest_path
            full_largest_path_clickable_text = Terminal_Clickable_Text(full_largest_path, full_largest_path, is_cmd=IS_CMD)
            THREAD_SAFE_PRINT("Check Duplicated Images", f"Largest image: {full_largest_path_clickable_text}", Log_File_Path)
            Transfered_Paths.append(os.path.basename(full_largest_path))
    if not Transfered_Paths:
        THREAD_SAFE_PRINT("Check Duplicated Images", f"There is no duplicated image in {YEAR}", Log_File_Path)
        return
    Final_Filter, Final_Outlier = Update_File_Lists(Filter_List, Outlier_List, Transfered_Paths)
    
    Output_Dict["Final_Filter"] = Final_Filter
    Output_Dict["Final_Outlier"] = Final_Outlier
    Dict_to_JsonFile(Output_Dict, f"{AD_PATH}{YEAR}_Shape_Dict_Final_Filter_Outlier.json")
    THREAD_SAFE_PRINT("Check Duplicated Images", f"✅{AD_PATH}{YEAR}_Shape_Dict_Final_Filter_Outlier.json Stored", Log_File_Path)
    return Final_Filter, Final_Outlier