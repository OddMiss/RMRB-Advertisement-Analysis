from datetime import datetime, timedelta
import time
import shutil
import threading
import os
import sys
import psutil
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import os
import json
from Config.Config import LOG_PATH

# Create thread-safe printing
print_lock = threading.Lock()

class FileUtils:
    @staticmethod
    def Check_Folder(Folder_Path, Log_File_Path=""):
        # Check if the folder exists
        if not os.path.exists(Folder_Path):
            os.makedirs(Folder_Path)  # Creates the folder (and parent folders if needed)
            PrintUtils.THREAD_SAFE_PRINT(
                f"Check Folder", 
                f"Folder '{Folder_Path}' created successfully.", 
                Log_File_Path
            )

    @staticmethod
    def Check_File(File_Path, Json_Bool=True, Create_New=True):
        # Check if the file exists
        if not os.path.exists(os.path.dirname(File_Path)): os.makedirs(os.path.dirname(File_Path))
        if not os.path.exists(File_Path) and Create_New:
            with open(File_Path, "w") as file:
                if Json_Bool: file.write("{}")
                else: file.write("")  # Create an empty file
            return False
        else: return True

    @staticmethod
    def COUNT_ALL_FILES_NUM(PATH):
        TOTAL = 0
        for _, _, files in os.walk(PATH):
            TOTAL += len(files)
        return TOTAL

    @staticmethod
    def Milestone(Interval_Times, Total_Num):
        Result = {}
        for i in range(1, Interval_Times + 1):
            Num = int(i * Total_Num / Interval_Times)
            Result[str(Num)] = f"{100 * i / Interval_Times:.2f}%"
        return Result

    @staticmethod
    def Get_Subfolders(PATH, Iteration=False):
        subfolders_list = []
        if Iteration:
            for root, _, _ in os.walk(PATH):
                subfolders_list.append(root)
        else:
            for name in os.listdir(PATH): 
                if os.path.isdir(os.path.join(PATH, name)):
                    path = os.path.join(PATH, name).replace("\\", "/")
                    if not path.endswith("/"): path += "/"
                    subfolders_list.append(path)
        return subfolders_list

    # def Count_Files(folder_path):
    #     # Create a Path object for the folder
    #     folder = Path(folder_path)
    #     # Count all files in the folder
    #     file_count = sum(1 for file in folder.iterdir() if file.is_file())
    #     return file_count

    @staticmethod
    def Delete_File(file_path, Log_File_Path=""):
        if os.path.isfile(file_path):
            os.remove(file_path)
            PrintUtils.THREAD_SAFE_PRINT("Delete File", f"{file_path} has been deleted.", Log_File_Path)

    @staticmethod
    # Function to rename a file
    def Rename_File(current_path, new_path, info="", Log_File_Path=""):
        try:
            # Renaming the file
            os.rename(current_path, new_path)
            PrintUtils.THREAD_SAFE_PRINT("Rename File", f"{info}: Old File {current_path} renamed to: {new_path}", Log_File_Path)
        except FileNotFoundError:
            PrintUtils.THREAD_SAFE_PRINT("Rename File", f"Error: The file {current_path} does not exist.", Log_File_Path)
        except PermissionError:
            PrintUtils.THREAD_SAFE_PRINT("Rename File", f"Error: You do not have permission to rename {current_path}.", Log_File_Path)
        except Exception as e:
            PrintUtils.THREAD_SAFE_PRINT("Rename File", f"Unexpected error: {e}", Log_File_Path)

    @staticmethod
    def Get_File_Size(file_path, Log_File_Path=""):
        """Returns the size of the file in bytes or -1 if the file does not exist."""
        if os.path.isfile(file_path): return os.path.getsize(file_path)
        else:
            PrintUtils.THREAD_SAFE_PRINT("Get File Size", f"File not found: {file_path}", Log_File_Path)
            return -1

    @staticmethod
    def Compare_File_Sizes(file1, file2, Log_File_Path=""):
        """Compares the sizes of two files and returns the larger one."""
        size1 = FileUtils.Get_File_Size(file1, Log_File_Path)
        size2 = FileUtils.Get_File_Size(file2, Log_File_Path)
        if (size1 == -1) or (size2 == -1): return None  # Both files do not exist
        if size1 > size2: return file1
        elif size2 > size1: return file2
        else: return None  # Files are the same size

    @staticmethod
    def Update_File_Lists(list_A, list_B, files_to_remove):
        """Updates list_A by removing specified files and adds them to list_B.
        
        Args:
            list_A (list): The list containing all files.
            list_B (list): The list to store removed files.
            files_to_remove (list): The list of files to be removed from list_A.
        """

        # Convert list_A to set for faster membership checking
        set_A = set(list_A)

        # Create a set from files_to_remove for quick access
        set_remove = set(files_to_remove)

        # Identify which files to remove that exist in list_A
        to_remove = set_A.intersection(set_remove)
        
        # Remove identified files and add them to list_B
        list_B.extend(to_remove)
        set_A.difference_update(to_remove)

        # Convert back to list if needed
        updated_list_A = list(set_A)
        updated_list_A.sort()
        list_B.sort()

        return updated_list_A, list_B

    @staticmethod
    def Get_Full_Path(ad_path, file_name):
        """
        - file_name is like "20240104_02_CV.png"
        - Exlusively designed for `AD_Shape_Analysis` and `Check_Duplicated_Images`
        """
        date_str = file_name.split("_")[0]
        return f"{ad_path}{date_str}/{file_name}"

class TimeUtils:
    @staticmethod
    def NowTime(LogFormat=False, Only_Month=False):
        # Get current time
        now = datetime.now()
        if Only_Month: 
            formatted_time = now.strftime("%Y-%m")
            return formatted_time
        if LogFormat: formatted_time = now.strftime("%y-%#m-%#d %#H.%#M.%#S")  # Windows alternative
        else: formatted_time = now.strftime("%y/%#m/%#d %#H:%#M:%#S")  # Windows alternative
        # Format as '25/6/5 12:12' (Year 2025, Month 6, Day 5)
        return formatted_time # str format
    
    @staticmethod
    def Generate_Dates(year):
        # Generate whole dates of one year
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1)
        current_date = start_date
        
        dates = []
        while current_date < end_date:
            dates.append(current_date.strftime('%Y%m%d'))
            current_date += timedelta(days=1)
        return dates

    @staticmethod
    def Create_Date(YEAR, DATE):
        """
        - YEAR: like 2025
        - DATE: like 1225
        - return datetime format
        """
        return datetime(int(YEAR), int(DATE[:2]), int(DATE[2:]))

class PrintUtils:
    # Define our thread-safe print function (Log)
    @staticmethod
    def THREAD_SAFE_PRINT(source, message: str, logfile_path=""):
        """
        Thread-safe print function that prints the 
        source and arguments with a timestamp.
        Args:
            source (str): The source of the print statement.
            message: output information, can be any type.
            logfile_path (str): Path to the log file.
        
        What is with the print_lock?
            The print_lock is used to ensure that only one thread 
            can execute the print statement at a time.
        """
        with print_lock:
            TIME = TimeUtils.NowTime()
            log_body = str(message).strip()
            INFO = f"[{TIME}][{source}] {log_body}"
            # print(f"[{TIME}][{source}]", *args)
            # INFO = f"[{TIME}][{source}] " + " ".join(map(str, args))
            print(INFO)
            try:
                # Add Logging to a file
                if not logfile_path: 
                    logfile_path = LOG_PATH + datetime.now().strftime("%Y-%m-%d %H") + ".log"
                FileUtils.Check_File(logfile_path, Json_Bool=False)  # Ensure the log file exists
                with open(logfile_path, "a", encoding='utf-8', errors='replace') as log_file:
                    log_file.write(INFO + "\n")
            except IOError as e:
                # Basic error handling for file writing
                print(f"❌LOG FAILED [{e}] !! Original: {log_body}", flush=True)
            except Exception as e:
                print(f"❌CRITICAL LOG ERROR [{type(e).__name__}] {e}", flush=True)

class JsonUtils:
    @staticmethod
    def Dict_to_JsonFile(Dict, filename):
        # Attention that add `ensure_ascii=False` for encoding Chinese correctly
        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(Dict, json_file, ensure_ascii=False, indent=4)

    @staticmethod
    def JsonFile_to_Dict(filename, Log_File_Path=""):
        try:
            # JSON file to Dict
            with open(filename, "r", encoding="utf-8") as json_file: Dict = json.load(json_file)
            return Dict
        except Exception as e:
            PrintUtils.THREAD_SAFE_PRINT(f"Json to Dict", f"Invalid json file format with {e}", Log_File_Path)
            return {}

class StorageUtils:
    def IS_DISK_LOW(file_path="", threshold_gb=0.5, Log_File_Path=""):
        """
        Check if the available storage space on the disk containing the specified file 
        (or current directory if no file specified) is less than the threshold.
        
        Args:
            file_path (str, optional): Path to a file or directory. If None, uses current directory.
            threshold_gb (float, optional): Threshold in GB. Default is 1 GB.
        
        Returns:
            bool: True if free space is less than threshold_gb, False otherwise.
        """
        try:
            # Determine which path to check
            if not file_path: check_path = os.getcwd()  # Current working directory
            else:
                check_path = os.path.abspath(file_path)
                # If it's a file, use its directory
                if os.path.isfile(check_path):
                    check_path = os.path.dirname(check_path)
            
            # Get the root directory of the drive containing the path
            # if os.name == 'nt':  # Windows
            # Extract drive letter (e.g., 'C:' from 'C:\\path\\to\\file')
            drive = os.path.splitdrive(check_path)[0]
            if not drive:
                # If no drive letter (unlikely), use current drive
                drive = os.path.splitdrive(os.getcwd())[0]
            root_dir = drive + '\\'
            # else:  # Unix/Linux/Mac
            #     root_dir = '/'
            
            # Get disk usage statistics
            disk_usage = shutil.disk_usage(root_dir)
            
            # Calculate free space in GB
            free_space_gb = disk_usage.free / (1024 ** 3)  # 1024^3 = 1,073,741,824 bytes
            PrintUtils.THREAD_SAFE_PRINT("IS DISK LOW", f"Free Space: {free_space_gb:.2f} GB", Log_File_Path)
            
            # Return True if free space is less than threshold
            return free_space_gb < threshold_gb
            
        except Exception as e:
            PrintUtils.THREAD_SAFE_PRINT("IS DISK LOW", f"Error checking disk space: {e}", Log_File_Path)
            return False  # Return False on error to avoid false alarms

class TextUtils:
    @staticmethod
    def Modify_Chars(
        input_string,
        remove_chars_list=[""],
        replace_dict={"": ""},
    ):
        # Create a remove translation table with str.maketrans
        Remove = str.maketrans("", "", "".join(remove_chars_list))

        # Create a replace translation table
        Replace = str.maketrans(replace_dict)
        # Use str.translate to remove the specified characters
        return input_string.translate(Remove).translate(Replace)
    
    @staticmethod
    def Format_Num(num):
        """
        - Ensure output num has 2 characters
        - for example, is num = 5, the formatted num is 05
        """
        num = str(num)
        return ("0" + num) if len(num) == 1 else num

    @staticmethod
    def Terminal_Clickable_Text(original_text, display_text, is_cmd=False):
        if is_cmd: return f"\033]8;;file://{original_text}\a{display_text}\033]8;;\a"
        else: return original_text

class SystemUtils:
    @staticmethod
    def RAM_USAGE(Log_File_Path=""):
        
        # Get the current process ID
        pid = os.getpid()
        # Get the process associated with the current Python process and system
        process = psutil.Process(pid)
        system_mem = psutil.virtual_memory()

        # Get the memory usage of the current process in MB
        # ram_usage_MB = process.memory_info().rss / (1024 * 1024)
        ram_usage_GB = process.memory_info().rss / (1024 * 1024 * 1024)
        system_usage_GB = system_mem.used / (1024 * 1024 * 1024)

        # Get the total system memory
        # total_memory_MB = psutil.virtual_memory().total / (1024 * 1024)
        total_memory_GB = psutil.virtual_memory().total / (1024 * 1024 * 1024)
        total_system_GB = system_mem.total / (1024 * 1024 * 1024)

        # Get RAM usage percentage
        ram_usage_percent = process.memory_percent()
        system_usage_percent = system_mem.percent

        # Get the CPU usage percentage of the current process
        cpu_usage = process.cpu_percent(interval=0.1)  # Added interval for accurate measurement
        system_cpu_usage = psutil.cpu_percent(interval=0.1)

        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", "-" * 80, Log_File_Path)
        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", f"Current RAM Usage: {ram_usage_GB:.2f} / {total_memory_GB:.2f} GB", Log_File_Path)
        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", f"Current RAM Usage percentage: {ram_usage_percent:.2f}%", Log_File_Path)
        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", f"System RAM Usage: {system_usage_GB:.2f} / {total_system_GB:.2f} GB", Log_File_Path)
        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", f"System RAM Usage percentage: {system_usage_percent:.2f}%", Log_File_Path)
        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", f"CPU Usage of this process: {cpu_usage:.2f}%", Log_File_Path)
        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", f"System CPU Usage: {system_cpu_usage:.2f}%", Log_File_Path)
        PrintUtils.THREAD_SAFE_PRINT("RAM USAGE", "-" * 80, Log_File_Path)

class InputUtils:
    @staticmethod
    def Choose_A_Year(Folder_Path, INFO, AD=False, Log_File_Path=""):
        # Choose year
        while True:
            YEAR = input("Please input the year (Format like YYYY: 2025): ")
            if not YEAR.isdigit(): PrintUtils.THREAD_SAFE_PRINT(f"{INFO}", "❌❌❌Input must be digit", Log_File_Path)
            if len(YEAR) != 4: PrintUtils.THREAD_SAFE_PRINT(f"{INFO}", "❌❌❌Incorrect year", Log_File_Path)
            if AD:
                if not os.path.exists(f"{Folder_Path}{YEAR}_AD"): PrintUtils.THREAD_SAFE_PRINT(f"{INFO}", f"❌❌❌Inexist year ({Folder_Path}{YEAR}_AD)", Log_File_Path)
                else: break
            else:
                if not os.path.exists(f"{Folder_Path}{YEAR}"): PrintUtils.THREAD_SAFE_PRINT(f"{INFO}", f"❌❌❌Inexist year ({Folder_Path}{YEAR})", Log_File_Path)
                else: break
        return YEAR
    
    @staticmethod
    def Sleeping(INFO, Log_File_Path=""):
        TIME = input("Please input sleep time (s): ")
        PrintUtils.THREAD_SAFE_PRINT(f"{INFO}", f"Sleeping for {TIME}s...", Log_File_Path)
        time.sleep(int(TIME))

    @staticmethod
    def Choose_Date(INFO, Log_File_Path=""):
        while True:
            BEGIN_DATE = input("Please input start date: (Format like MMDD: 1001): ")
            # Basic validation
            if not (len(BEGIN_DATE) == 4 and BEGIN_DATE.isdigit()):
                PrintUtils.THREAD_SAFE_PRINT(f"{INFO}", "❌❌❌Please make sure it's in MMDD format.", Log_File_Path)
            else: break
        while True:
            END_DATE = input("Please input end date: (Format like MMDD: 1231): ")
            if not (len(END_DATE) == 4 and END_DATE.isdigit()):
                PrintUtils.THREAD_SAFE_PRINT(f"{INFO}", "❌❌❌Please make sure it's in MMDD format.", Log_File_Path)
            else: break
        return BEGIN_DATE, END_DATE
