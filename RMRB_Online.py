import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
import os

"""
Author: OddMiss
Github: https://github.com/OddMiss
"""

'''
To make running your Python command more convenient and simple in the command prompt (cmd), you can use one of the following methods:
### Method: Create a Shortcut in CMD

If you want an even shorter command in the command line without creating a batch file, you can use `doskey` to create a shortcut for that session, although this method is temporary and will only last for the duration of the command prompt session.

1. **Open Command Prompt**.
2. **Enter This Command**:

   ```cmd
   doskey RMRB=D:/anaconda3/python.exe d:/OneDrive/Jupyter_Cloud/Quant/CCTV_AD_Analysis/RMRB_Online.py
   ```

3. **Run Your Script**:
   - Now, whenever you want to run your script, you just type:

   ```cmd
   RMRB
   ```
'''

'''
`How to solve the problem of the temporary shortcut doskey?`

### Creating the Registry Key for DOSKEY Macro

1. **Open the Registry Editor**:
   - Press `Win + R` to open the Run dialog.
   - Type `regedit` and press Enter. If prompted by User Account Control, click **Yes**.

2. **Navigate to the Correct Location**:
   - In the Registry Editor, you need to navigate to the following location:
     ```
     HKEY_CURRENT_USER\Software\Microsoft
     ```
   - You can do this by expanding the folders in the left pane.

3. **Create the `Command Processor` Key**:
   - Right-click on the `Microsoft` key (folder).
   - Select **New** -> **Key**.
   - Name the new key **Command Processor**.

4. **Create the `AutoRun` String Value**:
   - With the new `Command Processor` key selected, right-click on the right pane.
   - Select **New** -> **String Value**.
   - Name the string value **AutoRun**.

5. **Set the Value of `AutoRun`**:
   - Double-click on the `AutoRun` string you just created.
   - In the Value data field, enter your `doskey` command:
     ```
     doskey RMRB=D:\anaconda3\python.exe d:\OneDrive\Jupyter_Cloud\Quant\CCTV_AD_Analysis\RMRB_Online.py
     ```
   - Click **OK** to save the changes.

6. **Close the Registry Editor**:
   - After you finished, you can close the Registry Editor.

### Verifying Your Setup

1. **Open Command Prompt**:
   - Press `Win + R`, type `cmd`, and press Enter.

2. **Test the Macro**:
   - In the Command Prompt, type `RMRB` and press Enter.
   - It should run your script just as you defined in the AutoRun entry.

### Important Note

- **Be Careful**: Modifying the registry can affect your system, so ensure that you follow the steps carefully. If you're unsure, consider backing up the registry before making changes.
- **Reboot**: If the changes do not take effect immediately, consider rebooting your computer.

### Technical explanation

The reason why creating a `doskey` macro through the Windows Registry works is rooted in how the Windows Command Processor (cmd.exe) functions and how it reads configurations and settings.

### Technical Explanation

1. **Understanding `doskey`**:
   - `doskey` is a utility that allows users to create macros (shortcuts for commands) and to recall previously entered commands in the Windows command line interface.
   - When you define a macro with `doskey`, it only exists in the current session of the command prompt. When the command prompt closes, all defined macros (like `RMRB` in your case) are lost.

2. **The Role of the Windows Registry**:
   - The Windows Registry is a hierarchical database that stores low-level settings for the operating system and for applications.
   - The `AutoRun` registry key is a special feature in Windows that allows you to specify commands that should automatically run every time a new command prompt session starts.
   - When a new command prompt window is opened, the Windows Command Processor checks for the `AutoRun` key and executes any commands specified there.

3. **Creating the Registry Entry**:
   - By creating the `HKEY_CURRENT_USER\Software\Microsoft\Command Processor\AutoRun` key and setting its value to your `doskey` command, you are effectively telling Windows to execute that command each time you open a new instance of the Command Prompt.
   - This allows your custom `doskey` macro to be recreated automatically for every command prompt session, thus maintaining its presence even after reboots.

4. **Execution Flow**:
   - When cmd.exe starts, it checks for the existence of the `AutoRun` key in the registry:
     - If the key exists, it retrieves the command configured (in this case, your `doskey` command).
     - The command is then executed, which recreates the specified macros for that session.
   - As a result, every new command prompt that you open will have the `RMRB` macro available without any additional manual setup required.

5. **User Context**:
   - The path `HKEY_CURRENT_USER` is significant because it applies to the current user profile. This means that each user can have their own set of macros, and changes made in this registry location will not affect other users on the same machine. 

### Benefits of This Approach

- **Persistence**: This method provides persistence of your `doskey` macro, allowing you to access it in any new command prompt session without needing to redefine it manually.
- **Convenience**: It simplifies workflow for users who frequently use long or complex commands.
- **Customization**: Each user on the machine can customize their command prompt experience without impacting others.

In summary, by leveraging the Windows Registry's ability to run commands automatically upon the initialization of the command prompt, you can create a robust method for preserving your `doskey` macros across sessions and reboots.
'''

ROOT_PATH = "D:/AI_data_analysis/RMRB/Online_Download/" # Change it based on your fold
WEEKDAY_DICT = {"1": "Monday", "2": "Tuesday", 
                "3": "Wednesday", "4": "Thursday", 
                "5": "Friday", "6": "Saturday", 
                "7": "Sunday"}

def Extract_Version_Num(YEAR, MONTH, DAY):
    print(f"YEAR: {YEAR}, MONTH: {MONTH}, DAY: {DAY}")
    RMRB_url = f"http://paper.people.com.cn/rmrb/html/{YEAR}-{MONTH}/{DAY}/nbs.D110000renmrb_01.htm"
    # RMRB_url = "http://paper.people.com.cn/rmrb/html/2024-11/18/nbs.D110000renmrb_01.htm"
    versions = 0
    try:
        # Send a GET request to the URL
        response = requests.get(RMRB_url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        # Find the swiper-box container
        swiper_box = soup.find('div', class_='swiper-box')
        
        if swiper_box:
            # Find the swiper-container within the swiper-box
            swiper_container = swiper_box.find('div', class_='swiper-container')
            if swiper_container:
                # Find all the 'a' tags within the swiper-slide divs
                swiper_slides = swiper_container.find_all('div', class_='swiper-slide')
                for slide in swiper_slides:
                    link = slide.find('a')  # Find the <a> tag
                    if link:
                        versions += 1
                return versions
            else:
                print("No swiper-container found.")
                return None
        else:
            print("No swiper-box found.")
            print(f"URL: {RMRB_url}")
            Version_Num = input("Please input version number by hand: ")
            return int(Version_Num)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the page: {e}")
        return None

def RMRB_PDF_Download(Begin_date: str, End_date: str, Today_Bool: bool=False):
    """
    Begin_date, End_date: formatted string date like "19491001"
    """
    if Today_Bool: 
        today = datetime.today()
        start_date = datetime(today.year, today.month, today.day)
        end_date = start_date
        print(f"Today: {start_date.strftime('%Y%m%d')}")
    else:
        start_date = datetime(int(Begin_date[:4]), int(Begin_date[4:6]), int(Begin_date[6:8]))
        end_date = datetime(int(End_date[:4]), int(End_date[4:6]), int(End_date[6:8]))
        print(f"Begin date: {Begin_date}, End date: {End_date}")
    print("Stript Start...")
    current_date = start_date
    while current_date <= end_date:
        DATE = current_date.strftime("%Y%m%d")
        # Get the weekday (0=Monday, 6=Sunday) and adjust it so that Monday is 1 and Sunday is 7
        Weekday = current_date.weekday() + 1  # weekday() returns 0=Monday, 6=Sunday, so add 1 to make Monday=1
        print("*" * 80)
        print(f"Date: {DATE}, Weekday: {WEEKDAY_DICT[str(Weekday)]}")
        YEAR = str(current_date.year)
        MONTH = str(current_date.month)
        MONTH = ("0" + MONTH) if len(MONTH) == 1 else MONTH
        DAY = str(current_date.day)
        DAY = ("0" + DAY) if len(DAY) == 1 else DAY
        Version_num = Extract_Version_Num(YEAR, MONTH, DAY)
        if not Version_num: return
        print("All version:", Version_num)
        for Version in range(1, Version_num + 1):
            Version_str = ("0" + str(Version)) if len(str(Version)) == 1 else str(Version)
            print("Version num:", Version_str)
            pdf_url = f"http://paper.people.com.cn/rmrb/images/{YEAR}-{MONTH}/{DAY}/{Version_str}/rmrb{DATE}{Version_str}.pdf"
            File_Name = ROOT_PATH + f"{DATE}{Version_str}.pdf"
            print("Online link:", pdf_url)
            try:
                # Send a GET request to the URL
                response = requests.get(pdf_url)
                # Raise an exception if the request was unsuccessful
                response.raise_for_status()
                
                # Open the file in binary write mode and write the contents to it
                with open(File_Name, 'wb') as pdf_file:
                    pdf_file.write(response.content)
                print(f"Successfully Downloaded to {File_Name}")
            except requests.exceptions.RequestException as e:
                print(f"Error downloading the PDF: {e}")
            time.sleep(2)
        current_date += timedelta(days=1)
        time.sleep(2)
    print("Stript End...")
    print("*" * 80)

def Check_RMRB_Exist(Begin_date: str, End_date: str):
    """
    Begin_date, End_date: formatted string date like "19491001"
    """
    start_date = datetime(int(Begin_date[:4]), int(Begin_date[4:6]), int(Begin_date[-2:]))
    end_date = datetime(int(End_date[:4]), int(End_date[4:6]), int(End_date[-2:]))
    current_date = start_date
    missing_dates = []
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        file_name = date_str + "01" + ".pdf"
        file_path = ROOT_PATH + file_name
        if not os.path.exists(file_path):
            missing_dates.append(date_str)
        current_date += timedelta(days=1)
    return missing_dates
# Example usage
# RMRB_PDF_Download(Today_Bool=True)

if __name__ == "__main__":
    print("#" * 10 + "Welcome to RMRB download stript" + "#" * 10)
    TODAY = datetime.today().strftime("%Y%m%d")
    # Get the weekday (0=Monday, 6=Sunday) and adjust it so that Monday is 1 and Sunday is 7
    WEEKDAY = datetime.today().weekday() + 1  # weekday() returns 0=Monday, 6=Sunday, so add 1 to make Monday=1
    print(f"Today's date: {TODAY}. Today's weekday: {WEEKDAY_DICT[str(WEEKDAY)]}")
    print("""Download type: \n C: Customized dates \n T: Download today's RMRB \n U: Download RMRB from 20240709 until today""")
    TYPE = input("Please input type: ")
    TODAY_BOOL = False
    DATE_BOOL = False
    if TYPE == "C": 
        while True:
            BEGIN_DATE = input("Please input start date: (Format like YYYYMMDD: 19491001): ")
            # Basic validation
            if not (len(BEGIN_DATE) == 8 and BEGIN_DATE.isdigit()):
                print("Invalid date format. Please make sure it's in YYYYMMDD format.")
            else: break
        while True:
            END_DATE = input("Please input end date: (Format like YYYYMMDD: 19491001): ")
            if not (len(END_DATE) == 8 and END_DATE.isdigit()):
                print("Invalid date format. Please make sure it's in YYYYMMDD format.")
            else: break
        RMRB_PDF_Download(Begin_date=BEGIN_DATE, End_date=END_DATE, Today_Bool=TODAY_BOOL)
    elif TYPE == "T": 
        TODAY_BOOL = True
        RMRB_PDF_Download(Today_Bool=TODAY_BOOL)
    elif TYPE == "U":
        Missing_Dates = Check_RMRB_Exist("20240709", TODAY)
        if len(Missing_Dates):
            print("The missing dates:")
            for date in Missing_Dates:
                print(date)
            Download = input("Download (Y/N)? ")
            if Download == "Y":
                for date in Missing_Dates:
                    RMRB_PDF_Download(Begin_date=date, End_date=date, Today_Bool=False)
            elif Download == "N": exit()
            else: print("Invalid input, please input Y or N.")
        else: 
            print("There is no missing date from 20240709 until today")
            exit()
    else: print("Invalid input, please input C or Y or U.")