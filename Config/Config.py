import os
from datetime import datetime
ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/") + "/" # Current Root Path
MAIN_PATH = f"{ROOT_PATH[0]}:/AI_Data/RMRB/" # Local Data Path
EXTERNAL_PATH = "G:/AI_Data/RMRB/" # Custom Data Path
EXTERNAL_PATH_LIST = (
    MAIN_PATH, EXTERNAL_PATH, "Q:/AI_Data/RMRB/", "H:/AI_Data/RMRB/", "G:/AI_Data/RMRB/", "D:/AI_Data/RMRB/", "E:/AI_Data/RMRB/", "F:/AI_Data/RMRB/"
)
ETF_DATA_PATH = MAIN_PATH + "ETF-Data/"
LOG_ROOT_PATH = MAIN_PATH + "Log/"
LOG_PATH = MAIN_PATH + "Log/" + datetime.now().strftime("%Y-%m") + "/"
API_USAGE_PATH = MAIN_PATH + "Log/API-Usage/"
MODEL_PATH = MAIN_PATH + "Models/"
WEEKDAY_DICT = {
    "1": "Monday", "2": "Tuesday", "3": "Wednesday", 
    "4": "Thursday", "5": "Friday", "6": "Saturday", 
    "7": "Sunday"}
WEEKDAY_CHINESE_DICT = {
    "1": "星期一", "2": "星期二", "3": "星期三", 
    "4": "星期四", "5": "星期五", "6": "星期六", 
    "7": "星期天"}
Advertisement_Text = "广告"
Cipher_AD = """!!"!""" # Special encoding in RMRB PDF for "广告"
Remove_Chars_List = [
    " ",
    "@",
    "#",
    "^",
    "&",
    "*",
    "/",
    "\\",
    "+",
    "-",
    "=",
    "}",
    "{",
    "|",
    "~",
    "〉",
    "`",
    "〕",
    "「",
    "_",
    "'",
    "[",
    "]",
    "!",
    "<",
    ">",
    "ˇ",
    "′",
    "￥",
    "¥",
    "$",
]
Replace_Dict = {"“": '"', "”": '"', "‘": "'", "’": "'", ",": "，", ":": "：", ";": "；"}
NO_FOUND_ERROR = "not found"
RATE_LIMIT_ERROR = "limit"
CREDITS_RUN_OUT_ERROR_CHINESE = "用尽"
CREDITS_RUN_OUT_ERROR = "credit"
BALANCE_RUN_OUT_ERROR = "balance"
MAX_RETRIES_EXCEEDED = "exceeded"
TOO_MANY_REQUESTS = "too many requests"
UNKNOWN_ERROR = "unknown"
LOCATION_ERROR = "location"
ERROR = "error"
TIMEOUT_ERROR = "timeout"

EXIT_ERRORS = {
    NO_FOUND_ERROR, RATE_LIMIT_ERROR, CREDITS_RUN_OUT_ERROR, 
    CREDITS_RUN_OUT_ERROR, BALANCE_RUN_OUT_ERROR, 
    MAX_RETRIES_EXCEEDED, TOO_MANY_REQUESTS, UNKNOWN_ERROR, 
    LOCATION_ERROR, ERROR, TIMEOUT_ERROR}