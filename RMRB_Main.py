from RMRBCore.RMRB_AD_v6 import AD_Shape_Analysis, Genetare_AD_Image, Genetare_AD_Image_New, Extract_AD_Block, Check_Duplicated_Images
from RMRBCore.RMRB_Downloader_v2 import Extract_Version_Num, Get_PDF_Link, RMRB_PDF_Downloader, Check_RMRB_Exist
from RMRBCore.RMRB_Image_v6 import CV_Detect_Ads
from RMRBCore.RMRB_PDF_v6 import Check_Mac, Check_PDF_Exist, PDF_Split_All, Fix_PDF_Name
from RMRBCore.RMRB_OCR_v6 import Text_Recognition, OCR, Check_OCR_Completion
from RMRBCore.RMRB_LLM_v6 import Check_Summary_Completion, Text_Summary, Get_All_Models, API_Usage_Recorder, Exit_Error_Detector

if __name__ == "__main__":
    # Analysis_AD_Position()
    # Genetare_AD_Image()
    # Extract_Ad_Block()
    AD_Shape_Analysis()
    Extract_Version_Num()
    Get_PDF_Link()
    RMRB_PDF_Downloader()
    Check_RMRB_Exist()
    CV_Detect_Ads()
    Genetare_AD_Image()
    Genetare_AD_Image_New()
    Check_Duplicated_Images()
    Extract_AD_Block()
    Check_Mac()
    Check_PDF_Exist()
    PDF_Split_All()
    Fix_PDF_Name()
    Text_Recognition()
    OCR()
    Check_OCR_Completion()
    Check_Summary_Completion()
    Text_Summary()
    Get_All_Models()
    API_Usage_Recorder()
    Exit_Error_Detector()