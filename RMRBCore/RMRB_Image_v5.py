import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import cv2
import numpy as np
from Utils.main import PrintUtils, FileUtils, JsonUtils, TimeUtils, TextUtils
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
Compare_File_Sizes = FileUtils.Compare_File_Sizes
Update_File_Lists = FileUtils.Update_File_Lists
Get_File_Size = FileUtils.Get_File_Size
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict
Dict_to_JsonFile = JsonUtils.Dict_to_JsonFile
Create_Date = TimeUtils.Create_Date
Format_Num = TextUtils.Format_Num

def CV_Detect_Ads(
    root_path: str,
    image_type: str="CV",
    pdf_name: str='', 
    pdf_version: str='1', 
    image_path: str='',
    image_element=None, 
    Threshold: list=[0.4, 0.6], 
    Image_Path_Bool: bool=False,
    Image_Clip_Bool: bool=False,
    Whole_Image_Bool: bool=True,
    AD_SHAPE_ANALYSIS: bool=False,
    Log_File_Path=""
):
    """
    - Core function of computer vision detection
    - root_path: advertisement path
    - image_type: {"FAD", "HAD", "CV"}
    - pdf_name: pdf name (usually with version, like 2023010401)
    - pdf_version: version of a pdf for image conversion, begin with '1'
    - image_element: the image element which generated from `convert_from_path()`
    - Threshold list: [min, max] (area thershold is [min * whole_area, max * whole_area])
    - image_path_bool: if it is True, use image path, or use others path (like pdf path)
    - Image_Clip_Bool: Whether clip the detected image to an individual image. Default False.
    - Whole_Image_Bool: Whether save the marked image
    """
    if Image_Path_Bool:
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            THREAD_SAFE_PRINT("CV Detect Ads", f"Failed to load image: {image_path}", Log_File_Path)
            return False
    else:
        # Convert Pillow image to numpy array
        image_np = np.array(image_element)
        # Convert RGB to BGR since OpenCV uses BGR format
        image = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

    if AD_SHAPE_ANALYSIS: SHAPE_Dict = {}
    pdf_name = pdf_name[:8] # keep only date, not version

    # Get the dimensions of the image
    height, width = image.shape[:2]
    # Calculate the area of the entire image
    image_area = height * width
    Ad_Block_Threshold_Min = Threshold[0] * image_area
    Ad_Block_Threshold_Max = Threshold[1] * image_area

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # Apply edge detection
    edges = cv2.Canny(blurred, 50, 150)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ad_found = False  # Flag to indicate if an ad is detected

    i = 1
    # Iterate through contours
    for contour in contours:
        # print(contour)
        # Get the bounding box of the contour
        x, y, w, h = cv2.boundingRect(contour)
        # Calculate the area of the bounding rectangle
        area_rect = w * h # w is length, h is height

        # Filter based on area and aspect ratio (adjust thresholds as needed)
        if (area_rect >= Ad_Block_Threshold_Min) and (area_rect <= Ad_Block_Threshold_Max):
            ad_found = True

            if Whole_Image_Bool:
                # Draw a rectangle around the detected ad block
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
            if Image_Clip_Bool: 
                # Save the ad block image to local
                Check_Folder(Folder_Path=root_path, Log_File_Path=Log_File_Path)
                ad_block = image[y:y + h, x:x + w] # Clip the ad block
                output_block_path = f"{root_path}{pdf_name}_{pdf_version}_{image_type}_Block_{i}.png"
                cv2.imwrite(output_block_path, ad_block)
                if AD_SHAPE_ANALYSIS: 
                    pdf_name_version = f"{pdf_name}_{pdf_version}_{i}"
                    Result = {}
                    Result["output_block_path"] = os.path.basename(output_block_path) # relative path
                    Result["w"] = f"{w}"
                    Result["h"] = f"{h}"
                    Result["w_divide_h"] = f"{w / h :.3f}"
                    Text = f"{pdf_version}_{i} of {output_block_path} with (w = {w}, h = {h}) (w / h = {w / h :.3f})"
                    THREAD_SAFE_PRINT("CV Detect Ads", Text, Log_File_Path)
                    SHAPE_Dict[pdf_name_version] = Result
                else: THREAD_SAFE_PRINT("CV Detect Ads", f"Version {pdf_version}_{i} Saved ad block to {output_block_path}", Log_File_Path)
                i += 1
    # Display the result or save it for later review
    if ad_found and Whole_Image_Bool:
        Check_Folder(Folder_Path=root_path, Log_File_Path=Log_File_Path)
        output_path = f"{root_path}{pdf_name}_{pdf_version}_CV.png"
        cv2.imwrite(output_path, image)  # Save image with detected ads
        THREAD_SAFE_PRINT("CV Detect Ads", f"Version {pdf_version} Saved whole image to {output_path}", Log_File_Path)
    if AD_SHAPE_ANALYSIS: return SHAPE_Dict
    else: return None
# CV_Detect_Ads("D:/AI_data_analysis/RMRB/", "D:/AI_data_analysis/RMRB/20200117.pdf", "12", IMAGE_TEST[11])