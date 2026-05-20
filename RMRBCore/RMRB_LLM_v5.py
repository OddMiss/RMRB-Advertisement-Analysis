import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import time
import re
import ast
import glob
from collections import defaultdict
from google import genai
from datetime import datetime, timedelta
import random
# from requests.exceptions import RequestException
import requests
from Config.Config import WEEKDAY_CHINESE_DICT, API_USAGE_PATH, EXIT_ERRORS
from Config.API import MODEL
from Config.Prompt import Industry_Text, System_Prompt
from Utils.main import PrintUtils, FileUtils, JsonUtils, TextUtils
from RMRBCore.RMRB_Error_v5 import Exit_Error_Detector
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
Check_Folder = FileUtils.Check_Folder
Check_File = FileUtils.Check_File
Dict_to_JsonFile = JsonUtils.Dict_to_JsonFile
JsonFile_to_Dict = JsonUtils.JsonFile_to_Dict
Format_Num = TextUtils.Format_Num

def Industry_Text_to_Dict(text):
    """
    - Parse the industry classification text and return a dictionary.
    """
    def split_ignore_parentheses(s, delimiter):
        """
        - Split the string, ignoring the separators within parentheses.
        """
        parts = []
        current = ""
        depth = 0
        for char in s:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            if char == delimiter and depth == 0:
                parts.append(current.strip())
                current = ""
            else:
                current += char
        if current:
            parts.append(current.strip())
        return parts
    
    # Separate the first-level categories by semicolons and remove empty strings
    first_level_entries = [entry.strip() for entry in text.split('；') if entry.strip()]
    industry_dict = {}
    
    for entry in first_level_entries:
        # Separate the first-level names from the second-level lists using Chinese colons.
        if '：' not in entry:
            continue
        first_level, second_list_str = entry.split('：', 1)
        first_level = first_level.strip()
        # Divide the secondary categories and ignore the commas within the parentheses.
        second_parts = split_ignore_parentheses(second_list_str, '、')
        second_dict = {}
        for part in second_parts:
            # Parse the secondary name and the tertiary content
            if '(' in part and part.endswith(')'):
                second_name, third_content = part.split('(', 1)
                second_name = second_name.strip()
                third_content = third_content.rstrip(')').strip()
            else:
                # If there are no parentheses, the third-level content will be an empty list.
                second_name = part.strip()
                third_content = []
            second_dict[second_name] = third_content.split("、")
        industry_dict[first_level] = second_dict
    return industry_dict

def Industry_Dict_to_List(Industry_Dict):
    Industry_List = []
    for first in Industry_Dict:
        Industry_List.append(f"{first}")
        for second in Industry_Dict[first]:
            Industry_List.append(f"{first}-{second}")
            for thrid in Industry_Dict[first][second]:
                Industry_List.append(f"{first}-{second}-{thrid}")
    return Industry_List

Industry_Dict = Industry_Text_to_Dict(Industry_Text)
Industry_List = Industry_Dict_to_List(Industry_Dict)

def Remove_Think_Content(text):
    # Using regex to find and remove content between <think> and </think> (including markers)
    # re.DOTALL makes . match newlines as well
    pattern = r'<think>.*?</think>'
    result = re.sub(pattern, '', text, flags=re.DOTALL)
    return result

def Extract_Braced_Content(text):
    # Find all substrings that start with '{' and end with '}'
    matches = re.findall(r'\{.*?\}', text)
    
    # If matches are found, return them concatenated
    if matches: return ''.join(matches)
    # Otherwise, return the original text
    else: return text

def Is_A_String_Dict(s):
    """Check if string is a valid Python dict using ast.literal_eval"""
    try:
        result = ast.literal_eval(s)
        return isinstance(result, dict)
    except (ValueError, SyntaxError):
        return False

def Result_to_Dict(Result: str):
    Result = str(Result)
    Output = Remove_Think_Content(Result) # Remove think content
    Output = Output.replace("```python", "").replace("```json", "").replace("```", "") # remove code block sign
    Output = Output.replace("\\n", "").replace("\n", "") # Remove line
    Output = Extract_Braced_Content(Output) # Find all substrings that start with '{' and end with '}'
    if Is_A_String_Dict(Output): Output = ast.literal_eval(Output) # Turn to dict if it is a dict
    return Output

def Result_Format_Checker(Result: str):
    """
    - The result should like: 
    {"industry": "一级-二级-三级" (or "一级-二级", "一级"), "ad_type": "公益广告" (或商业广告等), "analysis": ""}
    """
    Result = str(Result)
    if not Result: return False, "Empty"
    Result_Dict = Result_to_Dict(Result=Result)
    if not isinstance(Result_Dict, dict): return False, f"Not a dict but {type(Result_Dict)}"
    required_keys = ["industry", "ad_type", "region", "analysis"]
    # Check for all required keys
    for key in required_keys:
        if key not in Result_Dict:
            return False, f"Missing required key: '{key}'"
    Industry = Result_Dict["industry"]
    Industry_Split_List = Industry.split(",")
    for insutry in Industry_Split_List:
        if not insutry.replace(" ", "") in Industry_List: return False, "Industry format incorrect"
    Ad = Result_Dict["ad_type"]
    if not "广告" in Ad: return False, "Advertisement format incorrect"
    return True, ""

def API_Online_Default(Prompt, URL, Model, API_KEY, API_Name, Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
    """
    - API online function (defalut)
    - usage example: {'completion_tokens': 1814, 'prompt_tokens': 2048, 'total_tokens': 3862}}
    - Timeout: (connect timeout, read timeout), defalut (30, 120)
    """
    for attempt in range(Max_Retries):
        try:
            result = None
            THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"{Model} Generating...", Log_File_Path)
            # Added 300-second timeout (connect timeout, read timeout)
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            payload = {"model": Model, "messages": [{"role": "user", "content": f"{Prompt}"}]}
            response = requests.post(URL, headers=headers, json=payload, timeout=Timeout)
            return_output = {}
            if response.status_code == 200:
                result = response.json()
                usage = result.get("usage", {})
                THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"✅Usage: {usage}", Log_File_Path)
                origin = result["choices"][0]["message"]["content"]
                return_output["Usage"] = usage
                return_output["Origin"] = origin
                return True, return_output
            else: raise ValueError(f"Error code: {response.status_code} with {response.text}")
        except Exception as e:
            flag = "❗" if attempt >= 1 else ""
            THREAD_SAFE_PRINT(f"API-Online-Defalut-{API_Name}", f"{flag}Attempt {attempt + 1} failed: due to {e} (Origin: {result})", Log_File_Path)
            if Exit_Error_Detector(e): return False, str(e)
            if attempt == Max_Retries - 1:
                THREAD_SAFE_PRINT(f"API-Online-Defalut-{API_Name}", f"❌Fail to use this API", Log_File_Path)
                return False, str(e)
        time.sleep(5)

def API_Online_Gemini(Prompt, URL, Model, API_KEY, API_Name, Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
    """
    - API online function (defalut)
    - usage example: {'completion_tokens': 1814, 'prompt_tokens': 2048, 'total_tokens': 3862}}
    - Timeout: (connect timeout, read timeout), defalut (30, 120)
    """
    if URL: URL = "" # URL is not applicable in this function
    if Timeout: Timeout = "" # Timeout is not applicable in this function
    # The client gets the API key from the environment variable `GEMINI_API_KEY`.
    client = genai.Client(api_key=API_KEY)
    # Define keys that to extract
    keys_to_extract = [
        'prompt_token_count',
        'candidates_token_count',
        'thoughts_token_count',
        'total_token_count'
    ]
    for attempt in range(Max_Retries):
        try:
            THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"{Model} Generating...", Log_File_Path)
            response = None
            response = client.models.generate_content(model=Model, contents=f"{Prompt}")
            origin = response.candidates[0].content.parts[0].text
            return_output = {}
            if origin:
                usage = dict(response.usage_metadata)
                # Create new dictionary with only the specified keys
                new_usage = {key: usage[key] for key in keys_to_extract if key in usage}
                return_output["Usage"] = usage
                return_output["Origin"] = origin
                THREAD_SAFE_PRINT(f"API-Online-{API_Name}", f"✅Usage: {new_usage}", Log_File_Path)
                return True, return_output
            else: raise ValueError(f"Error code: {response.status_code} with {response.text}")
        except Exception as e:
            flag = "❗" if attempt >= 1 else ""
            THREAD_SAFE_PRINT(f"API-Online-{API_Name}", f"{flag}Attempt {attempt + 1} failed: due to {e} (Origin: {response})", Log_File_Path)
            if Exit_Error_Detector(e): return False, str(e)
            if attempt == Max_Retries - 1:
                THREAD_SAFE_PRINT(f"API-Online-{API_Name}", f"❌Fail to use this API", Log_File_Path)
                return False, str(e)
        time.sleep(5)

def API_Online_Cloudflare(Prompt, URL, Model, API_KEY, API_Name, Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
    """
    - Exclusively designed for Cloudflare API
    - usage example: {'completion_tokens': 1814, 'prompt_tokens': 2048, 'total_tokens': 3862}}
    - Timeout: (connect timeout, read timeout), defalut (30, 120)
    """
    account_id, api_key = API_KEY # API_KEY is like [(account_id, api_key), ...]
    URL = URL.format(account_id=account_id)
    if Model in {"@cf/openai/gpt-oss-120b"}: 
        URL = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/responses"
        for attempt in range(Max_Retries):
            try:
                result = None
                THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"{Model} Generating...", Log_File_Path)
                # Added 300-second timeout (connect timeout, read timeout)
                headers = {"Authorization": f"Bearer {api_key}"}
                payload = {"model": Model, "input": Prompt}
                response = requests.post(URL, headers=headers, json=payload, timeout=Timeout)
                return_output = {}
                if response.status_code == 200:
                    result = response.json()
                    usage = result.get("usage", {})
                    THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"✅Usage: {usage}", Log_File_Path)
                    output_list = result["output"]
                    for output_dict in output_list:
                        output_type = output_dict["content"][0]["type"]
                        if output_type == "output_text":
                            origin = output_dict["content"][0]["text"]
                    return_output["Usage"] = usage
                    return_output["Origin"] = origin
                    return True, return_output
                else: raise ValueError(f"Error code: {response.status_code} with {response.text}")
            except Exception as e:
                flag = "❗" if attempt >= 1 else ""
                THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"{flag}Attempt {attempt + 1} failed: due to {e} (Origin: {result})", Log_File_Path)
                if Exit_Error_Detector(e): return False, str(e)
                if attempt == Max_Retries - 1:
                    THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"❌Fail to use this API", Log_File_Path)
                    return False, str(e)
            time.sleep(5)
    else: return API_Online_Default(Prompt=Prompt, URL=URL, Model=Model, API_KEY=api_key, API_Name=API_Name, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

def API_Info_Operation(Prompt, URL, Model, API_KEY, API_Name, API_Online_Fun, API_Usage_File_Path, Exist_Num=0, Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
    """
    - API info operation function (same for all API)
    - The output may contain think content in <think> and </think>
    - Timeout: (connect timeout, read timeout), defalut (30, 120)
    """
    for attempt in range(Max_Retries):
        try:
            Result = None
            Success, Result = API_Online_Fun(
                Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, 
                API_Name=API_Name, Timeout=Timeout, Log_File_Path=Log_File_Path
            )
            if Success:
                origin = str(Result["Origin"])
                origin_dict = Result_to_Dict(origin)
                Success_2, Info = Result_Format_Checker(Result=origin)
                Emoji = "✅" if Success_2 else "❌"
                API_Usage_Recorder(
                    API_Name=API_Name, Model=Model, File_Path=API_Usage_File_Path,
                    Success=Success_2, Log_File_Path=Log_File_Path)
                if not Success_2: 
                    THREAD_SAFE_PRINT(f"API-Info-{API_Name}-{Exist_Num}", f"{Emoji}Incorrect Format: {Info} ({origin_dict})", Log_File_Path)
                    raise ValueError("Invalid format")
                # THREAD_SAFE_PRINT(f"Chatbot-{API_Name}", f"Original: {output}", Log_File_Path)
                THREAD_SAFE_PRINT(f"API-Info-{API_Name}-{Exist_Num}", f"{Emoji}Output: {origin_dict}", Log_File_Path)
                return True, origin_dict
            else: return False, Result
        except Exception as e:
            flag = "❗" if attempt >= 1 else ""
            THREAD_SAFE_PRINT(f"API-Info-{API_Name}-{Exist_Num}", f"{flag}Attempt {attempt + 1} failed: due to {e} (Info: {Result})", Log_File_Path)
            if attempt == Max_Retries - 1:
                THREAD_SAFE_PRINT(f"API-Info-{API_Name}-{Exist_Num}", f"❌Fail to use this API", Log_File_Path)
                return False, f"{str(e)} (Info: {Result})"

# def Gongji(Prompt, URL, Model, API_KEY, API_Name="GONGJI", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Moonshot(Prompt, URL, Model, API_KEY, API_Name="MOONSHOT", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

def OpenRouter_Search_Free_Models(Log_File_Path=""):
    url = "https://openrouter.ai/api/frontend/models/find"
    params = {
        "fmt": "cards",
        "input_modalities": "text",
        "max_price": 0,
        "output_modalities": "text"
    }

    # Minimal headers that should work
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()  # Raises exception for 4xx/5xx status codes
        
        data = response.json().get("data", {}).get("models", [])
        THREAD_SAFE_PRINT(
            "OpenRouter Free Models", 
            f"✅Success! Retrieved {len(data) if isinstance(data, list) else 'some'} models", 
            Log_File_Path)
        
        Models_List = []
        # Example: Print model names
        for index, model in enumerate(data): 
            name = model["endpoint"]["model_variant_slug"]
            context_length = model["context_length"]
            Models_List.append(name)
            THREAD_SAFE_PRINT("OpenRouter Free Models", f"{index} - {name} - {context_length}")
        return Models_List
            
    except requests.exceptions.RequestException as e:
        THREAD_SAFE_PRINT("OpenRouter Free Models", f"❌Request failed: {e}", Log_File_Path)
    except ValueError as e:
        THREAD_SAFE_PRINT("OpenRouter Free Models", f"❌Failed to parse JSON: {e}", Log_File_Path)
        THREAD_SAFE_PRINT("OpenRouter Free Models", f"Response text: {response.text}", Log_File_Path)
# OpenRouter_Models_List = OpenRouter_Search_Free_Models()

# def OpenRouter(Prompt, URL, Model, API_KEY, API_Name="OPENROUTER", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     """
#     - [
#         "tngtech/deepseek-r1t-chimera:free", 
#         "tngtech/tng-r1t-chimera:free", 
#         "kwaipilot/kat-coder-pro:free", 
#         "qwen/qwen3-coder:free", 
#         "deepseek/deepseek-r1-0528:free"
#     ]
#     """
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Gemini(Prompt, API_KEY, URL="", API_Name="GEMINI", Model="gemini-2.5-flash", Max_Retries=2, Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Gemini, Max_Retries=Max_Retries, Log_File_Path=Log_File_Path)

# def Baichuang(Prompt, URL, Model, API_KEY, API_Name="BAICHUANG", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     """
#     - [
#         "Baichuan4-Air", # 0.00098/k tokens
#         "Baichuan2-Turbo", # 0.008/k tokens
#     ]
#     """
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Zhipu(Prompt, URL, Model, API_KEY, API_Name="ZHIPU", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Siliconflow(Prompt, URL, Model, API_KEY, API_Name="SILICONFLOW", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Deepseek(Prompt, URL, Model, API_KEY, API_Name="DEEPSEEK", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Github(Prompt, URL, Model, API_KEY, API_Name="GITHUB", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Cloudflare(Prompt, URL, Model, API_KEY, API_Online_Fun, API_Name="CLOUDFLARE", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     account_id, api_key = API_KEY # API_KEY is like [(account_id, api_key), ...]
#     URL = URL.format(account_id=account_id)
#     if Model in {"@cf/openai/gpt-oss-120b"}: 
#         URL = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/responses"
#         return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=api_key, API_Name=API_Name, API_Online_Fun=API_Online_Fun, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)
#     else: return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=api_key, API_Name=API_Name, API_Online_Fun=API_Online_Fun, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Huoshan(Prompt, URL, Model, API_KEY, API_Name="HUOSHAN", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Cohere(Prompt, URL, Model, API_KEY, API_Name="COHERE", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Shambanova(Prompt, URL, Model, API_KEY, API_Name="SHAMBANOVA", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Nvidia(Prompt, URL, Model, API_KEY, API_Name="NVIDIA", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Hunyuan(Prompt, URL, Model, API_KEY, API_Name="HUNYUAN", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Jieyue(Prompt, URL, Model, API_KEY, API_Name="JIEYUE", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

# def Aiml(Prompt, URL, Model, API_KEY, API_Name="AIML", Max_Retries=2, Timeout=(30, 120), Log_File_Path=""):
#     return API_Info_Operation(Prompt=Prompt, URL=URL, Model=Model, API_KEY=API_KEY, API_Name=API_Name, API_Online_Fun=API_Online_Default, Max_Retries=Max_Retries, Timeout=Timeout, Log_File_Path=Log_File_Path)

API_ONLINE_FUNCTION = {
    "MOONSHOT": API_Online_Default,
    "OPENROUTER": API_Online_Default,
    "GEMINI": API_Online_Gemini,
    "BAICHUANG": API_Online_Default,
    "ZHIPU": API_Online_Default,
    "SILICONFLOW": API_Online_Default,
    "DEEPSEEK": API_Online_Default,
    "GITHUB": API_Online_Default,
    "CLOUDFLARE": API_Online_Cloudflare,
    "HUOSHAN": API_Online_Default,
    "COHERE": API_Online_Default,
    "SHAMBANOVA": API_Online_Default,
    "NVIDIA": API_Online_Default,
    "HUNYUAN": API_Online_Default,
    "JIEYUE": API_Online_Default,
    "AIML": API_Online_Default
}

def API_Usage_Recorder(API_Name, Model, File_Path, Success: bool, Log_File_Path=""):
    """
    - Record every model's success and fail times
    - Recorder is like (1, 3) (i.e. (success number, failure number))
    - File_Path is in log root folder with file f"Success-Fail-Num-{time}.json"
    """
    if not File_Path: File_Path = API_USAGE_PATH + "Success-Fail-Num.json"
    Check_File(File_Path=File_Path)
    Recorder_Dict = JsonFile_to_Dict(filename=File_Path, Log_File_Path=Log_File_Path)
    key_name = f"{API_Name}~{Model}"
    if not Recorder_Dict.get(key_name, ""): Recorder_Dict[key_name] = [0, 0]
    if Success: Recorder_Dict[key_name][0] += 1
    else: Recorder_Dict[key_name][1] += 1
    Sorted_Recorder_Dict = dict(sorted(Recorder_Dict.items(), key=lambda item: item[1][0], reverse=True))
    Dict_to_JsonFile(Dict=Sorted_Recorder_Dict, filename=File_Path)

def Chatbot(Prompt, Text_Dict_Path, All_Models, OCR_Model, Threshold_Num, API_Usage_File_Path, Exist_Model_List=[], Log_File_Path=""):
    """
    - All_Models is like [{"Function": ..., "Key": ..., "API_Name": ..., "Model": ...}, {...}, ...]
    - Exist_Num: the exist number of summary text
    - Exist_Model_List: Exist summary name in this file, not including timestamp
    - Threshold_Num: in order to make summary text accurate and objective, use different models to generate text
    - Add timestamp to summary text name to distinguish outputs even API and Model are same
    """
    Exist_Num = len(Exist_Model_List)
    # Success_Num = 0
    # Rest_Num = Threshold_Num - Exist_Num
    for model_dict in All_Models:
        key = model_dict["Key"]
        api_name = model_dict["API_Name"]
        API_Online_Fun = API_ONLINE_FUNCTION[api_name]
        model = model_dict["Model"]
        URL = model_dict["URL"]
        Success, Content = API_Info_Operation(
            Prompt=Prompt, URL=URL, Model=model, API_KEY=key, 
            API_Name=api_name, API_Online_Fun=API_Online_Fun,
            Exist_Num=Exist_Num + 1, API_Usage_File_Path=API_Usage_File_Path, 
            Log_File_Path=Log_File_Path) # Why Exist_Num + 1?
        if Success: 
            current_time = datetime.now().strftime("%Y%m%d %H:%M:%S") # like 20260114 01:27:00
            summary_name = f"Summary~{api_name}~{model}~{OCR_Model}"
            Text_Dict = JsonFile_to_Dict(Text_Dict_Path, Log_File_Path=Log_File_Path)
            Text_Dict[f"{summary_name}~{current_time}"] = Content
            Dict_to_JsonFile(Text_Dict, Text_Dict_Path)
            Exist_Num += 1
            if Exist_Num >= Threshold_Num: return True, ""
    return False, f"❌Unexpected Error. Exist: {Exist_Num}, Rest: {Threshold_Num - Exist_Num}"

def Check_Summary_Completion(
    YEAR, Folder_Path, Begin_date="0101", End_date="1231", 
    OCR_Model="Paddeocr_V3", Threshold_Num=8, Log_File_Path=""):
    Complete_Date_List = set()
    Incomplete_Date_List = set()
    AD_PATH = Folder_Path + f"{YEAR}_AD/"
    Check_Folder(Folder_Path=AD_PATH, Log_File_Path=Log_File_Path)
    Filter_Path = f"{AD_PATH}{YEAR}_Shape_Dict_Final_Filter_Outlier.json"
    Filter_File_Bool = Check_File(File_Path=Filter_Path, Create_New=False)
    if not Filter_File_Bool: THREAD_SAFE_PRINT("Check Summary Completion", f"{Filter_Path} does not exist! Please run 'Check_Duplicated_Images'", Log_File_Path)
    Filter_List = JsonFile_to_Dict(filename=Filter_Path, Log_File_Path=Log_File_Path).get("Final_Filter", [])
    if not Filter_List: THREAD_SAFE_PRINT("Check Summary Completion", f"{Filter_Path} is empty! Please run 'Check_Duplicated_Images'", Log_File_Path)
    start_date = datetime(int(YEAR), int(Begin_date[:2]), int(Begin_date[2:]))
    end_date = datetime(int(YEAR), int(End_date[:2]), int(End_date[2:]))
    THREAD_SAFE_PRINT("Check Summary Completion", f"Checking {YEAR} completion...", Log_File_Path)
    current_date = start_date
    Exist_All_Num = 0
    All_Num = 0
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
                if os.path.isfile(file_path) and (suffix == "png"):
                    name_split_list = name.split('_')
                    # Ensure the image is an ad block or full ad
                    FAD_BOOL = "FAD" in name_split_list
                    BLOCK_BOOL = "Block" in name_split_list
                    FILTER_BOOL = filename in Filter_List
                    if FAD_BOOL or (BLOCK_BOOL and FILTER_BOOL):
                        All_Num += Threshold_Num
                        Text_Dict_Path = f"{AD_Folder_PATH}{name}.json"
                        Check_File(File_Path=Text_Dict_Path)
                        Text_Dict = JsonFile_to_Dict(Text_Dict_Path, Log_File_Path=Log_File_Path)
                        OCR_Content = Text_Dict.get(f"OCR_{OCR_Model}", "")
                        Exist_Num = 0
                        if OCR_Content:
                            for name in Text_Dict:
                                name_split = name.split("~")
                                if "Summary" in name_split: 
                                    # summary_name = "~".join(name_split[:-1]) # exclude timestamp
                                    Exist_Num += 1
                                    Exist_All_Num += 1
                        else: THREAD_SAFE_PRINT("Text Summary", f"❌{name} OCR_{OCR_Model} is empty", Log_File_Path)
                        if Exist_Num >= Threshold_Num: Complete_Date_List.update({f"{MONTH}{DAY}"})
                        else: Incomplete_Date_List.update({f"{MONTH}{DAY}"})
        current_date += timedelta(days=1)
    # Convert to sorted list
    Complete_Date_List_Sort = sorted(Complete_Date_List)
    Incomplete_Date_List_Sort = sorted(Incomplete_Date_List)
    THREAD_SAFE_PRINT("Check Summary Completion", f"Complete: {Complete_Date_List_Sort}", Log_File_Path)
    THREAD_SAFE_PRINT("Check Summary Completion", f"Incomplete: {Incomplete_Date_List_Sort}", Log_File_Path)
    Progress = f"{100 * Exist_All_Num / All_Num:.2f}%"
    THREAD_SAFE_PRINT("Check Summary Completion", f"🔥Progress: {Progress} ({Exist_All_Num}/{All_Num})", Log_File_Path)
    Output = {"ALL_NUM": All_Num, "EXIST_ALL_NUM": Exist_All_Num}
    if Incomplete_Date_List: return False, Output
    else: return True, Output

def API_Usage_Index(Folder_Path, Log_File_Path=""):
    """
    - combined_dict: {name: [success_num, fail_num]}
    - index_dict: {name: success_num ** 2 / (success_num + fail_num)}
    """
    combined_dict = defaultdict(lambda: [0, 0])
    index_dict = {}
    
    file_pattern = os.path.join(Folder_Path, "Success-Fail-Num-*.json")
    
    for file_path in glob.glob(file_pattern):
        try:
            data = JsonFile_to_Dict(filename=file_path, Log_File_Path=Log_File_Path)
            
            for name, values in data.items():
                combined_dict[name][0] += values[0]
                combined_dict[name][1] += values[1]
        except Exception as e:
            THREAD_SAFE_PRINT("API Usage Index", f"Error processing file {file_path}: {e}", Log_File_Path)
    
    for name, values in combined_dict.items():
        success_num, fail_num = values
        if success_num + fail_num > 0:
            index_dict[name] = round(success_num ** 2 / (success_num + fail_num), 3)
        else:
            index_dict[name] = 0.0
    
    return index_dict

def Get_All_Models(API_Usage_Path, API_Names=[], Models_Dict={}, Log_File_Path=""):
    """
    - API_Name: online LLM model used for text summary
    - AI_Model: specific LLM model in the API
    """
    API_Usage_Index_Dict = API_Usage_Index(Folder_Path=API_Usage_Path, Log_File_Path=Log_File_Path)
    if not API_Names: API_Names = list(MODEL.keys())
    All_Models = [] # store all available models (distinguished by api name, model, api)
    for api_name in API_Names:
        if Models_Dict.get(api_name, ""): Model_List = Models_Dict[api_name]
        else: Model_List = MODEL[api_name]["Models"]
        for model in Model_List:
            Keys = MODEL[api_name]["Keys"]
            Name = f"{api_name}~{model}"
            for Key in Keys:
                Result = {}
                Result["API_Name"] = api_name
                Result["Model"] = model
                Result["Key"] = Key
                Result["URL"] = MODEL[api_name]["URL"]
                Result["Index"] = API_Usage_Index_Dict.get(Name, 0.0)
                All_Models.append(Result)
    # Sort All_Models by Index in descending order
    All_Models = sorted(All_Models, key=lambda x: x["Index"], reverse=True)
    THREAD_SAFE_PRINT("Get All Models", f"All Candidate models No: {len(All_Models)}", Log_File_Path)
    return All_Models

def Update_All_Models_API_Usage(All_Models, API_Usage_Path, Log_File_Path=""):
    """
    - Update All_Models' Index based on latest API usage record
    """
    API_Usage_Index_Dict = API_Usage_Index(Folder_Path=API_Usage_Path, Log_File_Path=Log_File_Path)
    for model_dict in All_Models:
        api_name = model_dict["API_Name"]
        model = model_dict["Model"]
        Name = f"{api_name}~{model}"
        model_dict["Index"] = API_Usage_Index_Dict.get(Name, 0.0)
    # Sort All_Models by Index in descending order
    All_Models = sorted(All_Models, key=lambda x: x["Index"], reverse=True)
    THREAD_SAFE_PRINT("Update All Models", f"All Candidate models No: {len(All_Models)}", Log_File_Path)
    return All_Models

def Text_Summary(
    YEAR, Folder_Path, All_Models, API_Usage_File_Path="", 
    Begin_date="0101", End_date="1231", OCR_Model="Paddeocr_V3", 
    All_Num=0, Exist_All_Num=0, Threshold_Num=8, Log_File_Path=""):
    """
    - Core function of text summary
    - API_Names: manual input API, e.g. ["ZHIPU"]
    - Models_Dict: manual input models list for each GIVEN API, e.g. {"ZHIPU": ["GLM-4.6V", "GLM-4.5-Air"]}
    - Different from OCR models, summary models are LLM using online api
    - All_Models: from `Get_All_Models`
    - OCR_Model: output result model used for inputting the summary model (default Paddeocr_V3)
    - Threshold_Num: in order to make summary text accurate and objective, use different models to generate text
    """
    AD_PATH = Folder_Path + f"{YEAR}_AD/"
    Check_Folder(Folder_Path=AD_PATH, Log_File_Path=Log_File_Path)
    
    # Get filter list
    Filter_Path = f"{AD_PATH}{YEAR}_Shape_Dict_Final_Filter_Outlier.json"
    Filter_File_Bool = Check_File(File_Path=Filter_Path, Create_New=False)
    if not Filter_File_Bool: THREAD_SAFE_PRINT("Text Summary", f"{Filter_Path} does not exist! Please run 'Check_Duplicated_Images'", Log_File_Path)
    Filter_List = JsonFile_to_Dict(filename=Filter_Path, Log_File_Path=Log_File_Path).get("Final_Filter", [])
    if not Filter_List: THREAD_SAFE_PRINT("Text Summary", f"{Filter_Path} is empty! Please run 'Check_Duplicated_Images'", Log_File_Path)
    start_date = datetime(int(YEAR), int(Begin_date[:2]), int(Begin_date[2:]))
    end_date = datetime(int(YEAR), int(End_date[:2]), int(End_date[2:]))
    THREAD_SAFE_PRINT("Text Summary", f"Begin date: {YEAR + Begin_date}, End date: {YEAR + End_date}", Log_File_Path)
    
    current_date = start_date
    while current_date <= end_date:
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        Date = f"{YEAR}{MONTH}{DAY}"
        Weekday = datetime.strptime(Date, '%Y%m%d').weekday() # Monday == 0, Sunday == 6
        Weekday_Chinese = WEEKDAY_CHINESE_DICT[str(Weekday + 1)]
        AD_Folder_PATH = AD_PATH + f"{Date}/"
        if os.path.exists(AD_Folder_PATH): # Note that the path may not exist
            for filename in os.listdir(AD_Folder_PATH):
                file_path = AD_Folder_PATH + filename
                name = filename.split(".")[0]
                suffix = filename.split(".")[1]
                # Check if it is a file (not a directory)
                if os.path.isfile(file_path) and (suffix == "png"):  # Ensure it is a file
                    name_split_list = name.split('_')
                    # Ensure the image is an ad block or full ad
                    FAD_BOOL = "FAD" in name_split_list
                    BLOCK_BOOL = "Block" in name_split_list
                    FILTER_BOOL = filename in Filter_List
                    if FAD_BOOL or (BLOCK_BOOL and FILTER_BOOL):
                        Text_Dict_Path = f"{AD_Folder_PATH}{name}.json"
                        Check_File(Text_Dict_Path)
                        while True:
                            Text_Dict = JsonFile_to_Dict(Text_Dict_Path, Log_File_Path=Log_File_Path)
                            OCR_Content = Text_Dict.get(f"OCR_{OCR_Model}", "")
                            if OCR_Content:
                                # store exist summary text
                                Exist_Models = []
                                Exist_Num = 0
                                for name_model in Text_Dict:
                                    name_split = name_model.split("~")
                                    if "Summary" in name_split: 
                                        summary_name = "~".join(name_split[:-1]) # exclude timestamp
                                        Exist_Models.append(summary_name)
                                        Exist_Num += 1
                                if Exist_Num < Threshold_Num:
                                    THREAD_SAFE_PRINT("Text Summary", f"{Text_Dict_Path} (Exist: {Exist_Num})", Log_File_Path)
                                    Size = "整版" if FAD_BOOL else "半版"
                                    Prompt = System_Prompt.format(
                                        Industry_Text=Industry_Text, DATE=Date, Weekday=Weekday_Chinese, 
                                        Size=Size, AD=OCR_Content)
                                    # Shuffle the model list to ensure each model can fairly be selected
                                    API_Usage_Path = os.path.dirname(API_Usage_File_Path) + "/"
                                    All_Models = Update_All_Models_API_Usage(All_Models=All_Models, API_Usage_Path=API_Usage_Path, Log_File_Path=Log_File_Path)
                                    AD_Display = OCR_Content[:50].replace("\n", "")
                                    THREAD_SAFE_PRINT(f"Text Summary-{name}", f"AD Content: {AD_Display}...", Log_File_Path)
                                    Success, Info = Chatbot(
                                        Prompt=Prompt, Text_Dict_Path=Text_Dict_Path, 
                                        All_Models=All_Models, OCR_Model=OCR_Model, 
                                        Threshold_Num=Threshold_Num, API_Usage_File_Path=API_Usage_File_Path,
                                        Exist_Model_List=Exist_Models, Log_File_Path=Log_File_Path)
                                    if Success: 
                                        Exist_All_Num += (Threshold_Num - Exist_Num)
                                        Progress = f"{100 * Exist_All_Num / All_Num:.2f}%"
                                        THREAD_SAFE_PRINT("Text Summary", f"🔥Progress: {Progress} ({Exist_All_Num}/{All_Num})", Log_File_Path)
                                        THREAD_SAFE_PRINT("Text Summary", f"✅Summary text is stored in {Text_Dict_Path}", Log_File_Path)
                                        break
                                    else: 
                                        THREAD_SAFE_PRINT("Text Summary", f"{Info}", Log_File_Path)
                                        time.sleep(2) # avoid too frequent requests
                                else: break
                            else: 
                                THREAD_SAFE_PRINT("Text Summary", f"❌{Text_Dict} OCR_{OCR_Model} is empty", Log_File_Path)
                                THREAD_SAFE_PRINT("Text Summary", f"Waiting 240s for OCR to complete for {Text_Dict_Path}...", Log_File_Path)
                                time.sleep(240) # wait for OCR to complete
        current_date += timedelta(days=1)