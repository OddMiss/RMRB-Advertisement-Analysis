# RMRB Analysis

## Overview
Analyze People’s Daily (人民日报, RMRB) advertisements by detecting ad pages, extracting ad blocks, running OCR, and generating LLM-based industry classification and commentary.

## Workflow
Get original RMRB PDF  
→ Detect advertisements by computer vision/text rules  
→ Generate advertisement images (full/half/CV)  
→ Extract ad blocks and filter duplicates  
→ Convert images to text using OCR  
→ Use AI to classify industry + ad type + region + analysis

## Setup
1. Install dependencies:
   - `pip install -r requirements.txt`
2. Configure data paths in `Config/Config.py`:
   - `MAIN_PATH` / `EXTERNAL_PATH` / `EXTERNAL_PATH_LIST`
   - `MODEL_PATH` for PaddleOCR models
3. Download PaddleOCR model folders into `MODEL_PATH` (see PaddleOCR model list/releases):
   - https://github.com/PaddlePaddle/PaddleOCR/blob/main/doc/doc_en/models_list_en.md
   - https://github.com/PaddlePaddle/PaddleOCR/releases
   - `PP-DocLayout_plus-L_infer/`
   - `PP-OCRv5_server_det_infer/`
   - `PP-OCRv5_server_rec_infer/`
   - `PP-Chart2Table_infer/`
4. Create `Config/API.py` (gitignored) with your LLM providers and keys:
   - Required by `RMRBCore/RMRB_LLM_v5.py` (`MODEL` dict with URL/Models/Keys)
   - Example:
     ```python
     MODEL = {
       "GEMINI": {
         "URL": "",  # Not used for GEMINI; required for most other APIs
         "Models": ["gemini-2.5-flash"],
         "Keys": ["<api-key>"]
       }
     }
     ```

## Data Layout
The analysis pipeline reads/writes under the data root (from `Config/Config.py`).

```
{DATA_ROOT}/
  {YEAR}/
    {YYYYMMDD}/
      {YYYYMMDD}.pdf or {YYYYMMDD}{VV}.pdf
  {YEAR}_AD/
    {YYYYMMDD}/
      {YYYYMMDD}_{VV}_FAD.png          # full-page ad
      {YYYYMMDD}_{VV}_HAD.png          # half-page ad
      {YYYYMMDD}_{VV}_CV.png           # CV-detected page
      {YYYYMMDD}_{VV}_{TYPE}_Block_{i}.png
      {image}.json                     # OCR + LLM outputs
    {YEAR}_Shape_Dict*.json            # shape filters & dedupe lists
```

## Run Analysis (CLI)
Windows users can use the `.bat` scripts in `Scripts/` (or `PortableScripts/`).

1. **Prepare PDFs (optional tools)**
   - `python RMRB_PDFTools.py`
   - Includes: MAC checker, folder formatter, existence check, PDF splitter, name fixer.
2. **Generate ad images / blocks**
   - `python RMRB_AD_Image_Generator.py`
   - Options:
     - Generate AD Image (FAD/HAD/CV)
     - Extract AD Block (creates `*_Block_*.png`)
     - AD Shape Analysis + Duplicate Check (writes final filter lists)
3. **OCR**
   - `python RMRB_OCR.py`
   - Writes OCR content into per-image JSON files.
4. **LLM summary & classification**
   - `python RMRB_LLM.py`
   - Generates `Summary~...` fields in the same JSON files.
5. **Notebooks**
   - `RMRB_Analysis_v5.ipynb`
   - `RMRBCore/AD-Quant-Analysis.ipynb`, `AD_Text_Analysis.ipynb`, etc.

# RMRB Online Downloader

CMD interface (RMRB_Online_v1):

![image](./Figs/RMRB_Online_v1.png)

(RMRB_Online_v1.1):

![image](./Figs/RMRB_Online_v1.1.png)

(RMRB_Downloader_v2) (Old name `RMRB_Online`)

![1764331181508](Figs/Downloaderv2.png)
