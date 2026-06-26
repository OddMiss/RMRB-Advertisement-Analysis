from PyPDF2 import PdfReader, PdfWriter
import requests
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
import time
import os
from Config.Config import WEEKDAY_DICT
from RMRBCore.RMRB_PDF_v6 import PDF_Split_All
from Utils.main import PrintUtils, FileUtils, TextUtils
THREAD_SAFE_PRINT = PrintUtils.THREAD_SAFE_PRINT
Check_Folder = FileUtils.Check_Folder
Format_Num = TextUtils.Format_Num

def Extract_Version_Num(YEAR, MONTH, DAY, Log_File_Path=""):
    """
    - Get versions by visiting original website
    - Exclusively designed for http://paper.people.com.cn/rmrb
    """
    # Use web scraping to obtain
    THREAD_SAFE_PRINT("Extract Version Num", f"YEAR: {YEAR}, MONTH: {MONTH}, DAY: {DAY}", Log_File_Path)
    RMRB_url = f"http://paper.people.com.cn/rmrb/pc/layout/{YEAR}{MONTH}/{DAY}/node_01.html"
    # RMRB_url_old = "http://paper.people.com.cn/rmrb/html/2024-11/18/nbs.D110000renmrb_01.htm"
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
                    if link: versions += 1
                return versions
            else:
                THREAD_SAFE_PRINT("Extract Version Num", "❗❗❗No swiper-container found", Log_File_Path)
                return None
        else:
            THREAD_SAFE_PRINT("Extract Version Num", "❗❗❗No swiper-box found", Log_File_Path)
            THREAD_SAFE_PRINT("Extract Version Num", f"URL: {RMRB_url}", Log_File_Path)
            Version_Num = input("Please input version number by hand: ")
            return int(Version_Num)
    except requests.exceptions.RequestException as e:
        THREAD_SAFE_PRINT("Extract Version Num", f"Error fetching the page: {e}", Log_File_Path)
        return None

# Function to extract the PDF link from the HTML
def Get_PDF_Link(url):
    """
    - Get RMRB PDF links by visiting original website
    - Exclusively designed for http://paper.people.com.cn/rmrb
    """
    try:
        # Fetch the webpage content
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP request errors

        # Properly decode the response content
        # Use response.apparent_encoding to handle Chinese characters if needed
        response.encoding = response.apparent_encoding or response.encoding

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        # print(soup.prettify())
        
        # Locate the <a> tag with the "PDF下载" text
        pdf_tag = soup.find('a', string='PDF下载')
        if pdf_tag:
            # Construct the absolute URL for the PDF link
            pdf_url = urljoin(url, pdf_tag['href'])
            return pdf_url
        else: return "PDF link not found❌"
    except requests.exceptions.RequestException as e:
        return f"Error occurred: {e}❌"

def PDF_Link_Downloader_Official(PDF_Link, Store_Path, Max_Retries=3, Log_File_Path=""):
    """
    - The output can only accept valid  PDF link
    - Store_Path should be full PDF absolute local non-version path D:/RMRB/2025/20250102/20250102.pdf
    - Note that official website can only download single version PDF, not complete daily PDF (so it doesn't contain Custom_Versions)
    - Exclusively designed for http://paper.people.com.cn/rmrb
    """
    for attempt in range(Max_Retries):
        try:
            # Send a GET request to the URL
            response = requests.get(PDF_Link)
            # Raise an exception if the request was unsuccessful
            response.raise_for_status()
            
            pdf_reader = PdfReader(BytesIO(response.content))
            THREAD_SAFE_PRINT("PDF Link Downloader Official", f"Number of pages: {len(pdf_reader.pages)}", Log_File_Path)
            
            # Open the file in binary write mode and write the contents to it
            with open(Store_Path, 'wb') as pdf_file:
                pdf_file.write(response.content)
            THREAD_SAFE_PRINT("PDF Link Downloader Official", f"✅Successfully Downloaded to {Store_Path}", Log_File_Path)
            time.sleep(2)
            return True
        except requests.exceptions.RequestException as e:
            flag = "❗" if attempt >= 1 else ""
            THREAD_SAFE_PRINT("PDF Link Downloader Official", f"Attempt {attempt + 1}{flag} failed: due to {e}", Log_File_Path)
            if attempt == Max_Retries - 1:
                THREAD_SAFE_PRINT("PDF Link Downloader Official", f"❌Error downloading {Store_Path} ({e})", Log_File_Path)
                return False
        time.sleep(10)
    return False

def PDF_Link_Downloader_JOJO(PDF_Link, Store_Path, Custom_Versions=[], Max_Retries=3, Log_File_Path=""):
    """
    - Download PDF from a URL that redirects to SharePoint
    - Custom_Versions should begin with 1
    - Store_Path should be full PDF absolute local non-version path like D:/RMRB/2025/20250102/20250102.pdf
    - Exclusively designed for https://reader.jojokanbao.cn/rmrb/
    """
    # Browser-like headers to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }
    for attempt in range(Max_Retries):
        try:
            THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"Requesting PDF from: {PDF_Link} ...", Log_File_Path)
            # Set a longer timeout for large files
            response = requests.get(
                PDF_Link, 
                headers=headers, 
                timeout=30,
                allow_redirects=True  # This is True by default
            )
            response.raise_for_status()  # Raise exception for 4xx/5xx responses
            pdf_reader = PdfReader(BytesIO(response.content))
            num_of_pages = len(pdf_reader.pages)
            pages_list = [str(num + 1) for num in range(num_of_pages)]
            THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"Number of pages: {num_of_pages}", Log_File_Path)
            if Custom_Versions:
                pdf_base_name = os.path.basename(Store_Path)
                pdf_name = pdf_base_name.split(".")[0] 
                pdf_folder = os.path.dirname(Store_Path) + "/"
                for custom_version in Custom_Versions:
                    if str(custom_version) in pages_list:
                        pdf_writer = PdfWriter()
                        pdf_writer.add_page(pdf_reader.pages[int(custom_version) - 1]) # The index starts with 0
                        pdf_path = f"{pdf_folder}{pdf_name}{custom_version}.pdf"
                        with open(pdf_path, 'wb') as f:
                            pdf_writer.write(f)
                            THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"✅Successfully Downloaded to {Store_Path}", Log_File_Path)
                    else: THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"❌Version {custom_version} does not exist", Log_File_Path)
            else:
                with open(Store_Path, 'wb') as f:
                    f.write(response.content)
                    THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"✅Successfully Downloaded to {Store_Path}", Log_File_Path)
            return True
        # except requests.exceptions.Timeout:
        #     THREAD_SAFE_PRINT("PDF Link Downloader JOJO", "❌Request timed out. The server might be slow or the file is large.", Log_File_Path)
        # except requests.exceptions.HTTPError as e:
        #     THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"❌HTTP Error: {e}", Log_File_Path)
        #     THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"❌Response: {response.text[:500]}...", Log_File_Path)
        # except requests.exceptions.RequestException as e:
        #     THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"❌Request failed: {e}", Log_File_Path)
        except Exception as e:
            flag = "❗" if attempt >= 1 else ""
            THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"Attempt {attempt + 1}{flag} failed: due to {e} ({response.text})", Log_File_Path)
            if attempt == Max_Retries - 1:
                THREAD_SAFE_PRINT("PDF Link Downloader JOJO", f"❌Error downloading {Store_Path} ({e})", Log_File_Path)
                return False
        time.sleep(10)

def RMRB_PDF_Downloader(Begin_date: str, End_date: str, Download_Path, Custom_Versions=[], Log_File_Path=""):
    """
    - Core function of RMRB downloader
    - Begin_date, End_date: formatted string date like "19491001"
    - Custom_Version: This is custom download feature, only supported for single day
    """
    start_date = datetime(int(Begin_date[:4]), int(Begin_date[4:6]), int(Begin_date[6:8]))
    end_date = datetime(int(End_date[:4]), int(End_date[4:6]), int(End_date[6:8]))
    THREAD_SAFE_PRINT("RMRB PDF Downloader", f"Begin date: {Begin_date}, End date: {End_date}", Log_File_Path)
    THREAD_SAFE_PRINT("RMRB PDF Downloader", "Stript Start...", Log_File_Path)
    current_date = start_date
    while current_date <= end_date:
        DATE = current_date.strftime("%Y%m%d")
        # Get the weekday (0=Monday, 6=Sunday) and adjust it so that Monday is 1 and Sunday is 7
        Weekday = current_date.weekday() + 1  # weekday() returns 0=Monday, 6=Sunday, so add 1 to make Monday=1
        THREAD_SAFE_PRINT("RMRB PDF Downloader", "*" * 80, Log_File_Path)
        THREAD_SAFE_PRINT("RMRB PDF Downloader", f"Date: {DATE}, Weekday: {WEEKDAY_DICT[str(Weekday)]}", Log_File_Path)
        YEAR = str(current_date.year)
        MONTH = Format_Num(str(current_date.month))
        DAY = Format_Num(str(current_date.day))
        Download_Date_Path = Download_Path + f"{YEAR}/{YEAR}{MONTH}{DAY}/"
        Check_Folder(Download_Date_Path, Log_File_Path)
        if int(YEAR) >= 2023: # use official channel
            Version_num = Extract_Version_Num(YEAR, MONTH, DAY, Log_File_Path)
            if not Version_num: 
                THREAD_SAFE_PRINT("RMRB PDF Downloader", f"❌No Version Info", Log_File_Path)
                return
            THREAD_SAFE_PRINT("RMRB PDF Downloader", f"All version: {Version_num}", Log_File_Path)
            if not Custom_Versions: Custom_Versions = [Format_Num(Version) for Version in range(1, Version_num + 1)]
            for Version in Custom_Versions:
                Version_str = Format_Num(Version)
                THREAD_SAFE_PRINT("RMRB PDF Downloader", f"Version num: {Version_str}", Log_File_Path)
                # pdf_url_old = f"http://paper.people.com.cn/rmrb/images/{YEAR}-{MONTH}/{DAY}/{Version_str}/rmrb{DATE}{Version_str}.pdf"
                RMRB_url = f"http://paper.people.com.cn/rmrb/pc/layout/{YEAR}{MONTH}/{DAY}/node_{Version_str}.html" # it can only download after 2023
                pdf_url = Get_PDF_Link(RMRB_url)
                File_Name = Download_Date_Path + f"{DATE}{Version_str}.pdf"
                THREAD_SAFE_PRINT("RMRB PDF Downloader", f"Online link: {pdf_url}", Log_File_Path)
                PDF_Link_Downloader_Official(PDF_Link=pdf_url, Store_Path=File_Name, Log_File_Path=Log_File_Path)
        else: # use other channle
            # Currently this link can only download complete daily PDF
            # Therefore, use `PDF_Split_All` to split PDF. Make sure each PDF contains only 1 version
            pdf_url = f"https://1314955862-79a3hvoqxc-bj.scf.tencentcs.com/RMRB/{YEAR}/{YEAR}{MONTH}{DAY}.pdf"
            File_Name = Download_Date_Path + f"{DATE}.pdf"
            Success = PDF_Link_Downloader_JOJO(PDF_Link=pdf_url, Store_Path=File_Name, Log_File_Path=Log_File_Path)
            if Success: PDF_Split_All(pdf_path=File_Name, delete_original=True, Log_File_Path=Log_File_Path)
            time.sleep(5)
        current_date += timedelta(days=1)
    THREAD_SAFE_PRINT("RMRB PDF Downloader", "Stript End...", Log_File_Path)
    THREAD_SAFE_PRINT("RMRB PDF Downloader", "*" * 80, Log_File_Path)

# def RMRB_PDF_Specific_Version(DATE: str, Version: str, Download_Path, Log_File_Path=""):
#     """
#     - DATE: formatted string date like "19491001"
#     - Version: version number like "01"
#     """
#     THREAD_SAFE_PRINT("RMRB Specific Version", f"DATE: {DATE}, Version: {Version}", Log_File_Path)
#     YEAR = DATE[:4]
#     MONTH = DATE[4:6]
#     DAY = DATE[6:8]
#     RMRB_url = f"http://paper.people.com.cn/rmrb/pc/layout/{YEAR}{MONTH}/{DAY}/node_{Version}.html"
#     Download_Date_Path = Download_Path + f"{YEAR}/{YEAR}{MONTH}{DAY}/"
#     Check_Folder(Download_Date_Path, Log_File_Path)
#     pdf_url = Get_PDF_Link(RMRB_url)
#     File_Name = Download_Date_Path + f"{DATE}{Version}.pdf"
#     THREAD_SAFE_PRINT("RMRB Specific Version", f"Online link: {pdf_url}", Log_File_Path)
#     try:
#         # Send a GET request to the URL
#         response = requests.get(pdf_url)
#         # Raise an exception if the request was unsuccessful
#         response.raise_for_status()
#         # Open the file in binary write mode and write the contents to it
#         with open(File_Name, 'wb') as pdf_file:
#             pdf_file.write(response.content)
#         THREAD_SAFE_PRINT("RMRB Specific Version", f"Successfully Downloaded to {File_Name} ✅", Log_File_Path)
#     except requests.exceptions.RequestException as e:
#         THREAD_SAFE_PRINT("RMRB Specific Version", f"Error downloading the PDF {DATE + Version}: {e}", Log_File_Path)
#     time.sleep(2)

def Check_RMRB_Exist(Begin_date: str, End_date: str, Download_Path, Log_File_Path=""):
    """
    Begin_date, End_date: formatted string date like "19491001"
    """
    start_date = datetime(int(Begin_date[:4]), int(Begin_date[4:6]), int(Begin_date[-2:]))
    end_date = datetime(int(End_date[:4]), int(End_date[4:6]), int(End_date[-2:]))
    current_date = start_date
    missing_dates = []
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        year = current_date.strftime("%Y")
        month = current_date.strftime("%m")
        day = current_date.strftime("%d")
        Download_Date_Path = Download_Path + f"{year}/{year}{month}{day}/"
        Check_Folder(Download_Date_Path, Log_File_Path)
        file_name = date_str + "01" + ".pdf"
        file_path = Download_Date_Path + file_name
        if not os.path.exists(file_path):
            missing_dates.append(date_str)
        current_date += timedelta(days=1)
    return missing_dates
# Example usage
# RMRB_PDF_Download(Today_Bool=True)