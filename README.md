
# 🧠 CT Defacer Pipeline (DICOM ⇄ NIfTI)

## 🎯 Pipeline Overview

The **CT-DEFACE pipeline** is a batch processing wrapper that reduces facial re-identification risk in head CT images. It processes DICOM case folders and generates defaced versions while preserving the original DICOM structure.

### What It Does

- Converts DICOM series → NIfTI format
- Runs CTA-DEFACE segmentation model
- Applies facial mask to image volume
- Converts defaced NIfTI → DICOM (preserving headers)

**Note:** Only pixel data are modified. Original DICOM metadata (patient IDs, UIDs) remain unchanged unless separately anonymized.

### Pipeline Steps

| Step | Input | Operation | Output |
|------|-------|-----------|--------|
| 1 | DICOM case folder | Convert to NIfTI | Intermediate NIfTI |
| 2 | NIfTI volume | Run CTA-DEFACE model | Defaced NIfTI |
| 3 | Defaced NIfTI | Replace voxel values | Defaced image |
| 4 | Defaced image + original DICOM | Reconstruct series | Defaced DICOM |

### Input & Output

**Input:** Single case folder or directory with multiple case folders (one series per folder)

**Output:**
- Defaced DICOM series
- Optional defaced NIfTI (for QA/analysis)
- Temporary working files

### Recommended Workflow

1. Organize DICOM data (one series per case folder)
2. Run defacing pipeline
3. Perform visual QA
4. Apply metadata anonymization
5. Upload processed dataset


---

# 📁 Repository Contents

## Core Scripts
```
CT-DEFACE/
│
├── run_CT-DEFACE.py                     # nnUNet CPU/GPU inference + mask application
├── ct_deface_pipeline_multi2.py         # Full multi-case batch pipeline (DICOM→NIfTI→DEFACE→DICOM)
├── ct_deface_pipeline_gpu.py            # GPU-only batch pipeline (DICOM→NIfTI→DEFACE→NIfTI)
├── ct_deface_convert.py                 # Standalone DICOM ↔ NIfTI converter
```

## Platform-Specific Setup & Execution
```
├── 🐧 Linux:
│   ├── setup_ct_deface_cpu.sh           # CPU setup (installs dependencies, downloads model)
│   ├── run_ct_deface_cpu.sh             # Wrapper to force CPU-only inference
│   └── requirements-ct-deface.txt       # Dependencies for Linux
│
└── 🪟 Windows:
    ├── setup_ct_deface_cpu.ps1          # CPU setup (PowerShell)
    ├── download_ct_deface_model.ps1     # Model downloader (Windows only)
    ├── run_ct_deface_batch.ps1          # Batch runner (PowerShell)
    └── requirements_ct_deface_windows.txt  # Dependencies for Windows
```

## Data & Models
```
├── model/Dataset001_DEFACE/              # Pre-trained nnUNet weights (auto-downloaded)
├── dicom_input/                          # Input DICOMs (place your data here)
├── dicom_output/                         # Defaced DICOM output
├── head_ct_samples/                      # Sample test data
└── nnunet_data/                          # nnUNet environment data
```

---

# 🧱 Requirements

## Hardware
- Any **CPU-only** computer  
- RAM 8-16 GB recommended  
- Disk space: ~3× your DICOM dataset

## Software
- Python **3.10-3.12**
- Git
- Windows PowerShell **or** Linux bash

---

# 🐧 Linux Installation (Step by Step)

### 1. Clone repo
```bash
git clone https://github.com/jsfakian/CT-DEFACE.git
cd CT-DEFACE
```

### 2. Run setup
```bash
bash setup_ct_deface_cpu.sh
```

Creates `.venv_ct_deface/` and installs:
- nnUNetv2
- CPU-only PyTorch
- nibabel, SimpleITK, pydicom, tqdm, numpy…

### 3. Activate environment
```bash
source .venv_ct_deface/bin/activate
```

---

# ▶️ Linux: Running the Pipeline

### A. Single-case defacing
```bash
python ct_deface_pipeline_multi2.py     -i dicom_input     -o dicom_output
```

### B. Multi-case defacing
Input layout:
```
dicom_input/
 ├── case01/
 ├── case02/
 └── case03/
```

Run:
```bash
python ct_deface_pipeline_multi2.py     -i dicom_input     -o dicom_output     --nifti-root-out nifti_output
```

---

# 🪟 Windows Installation (Step by Step)

## 1. Install Git (Only once)

Git is required to download (clone) the project from GitHub.
Steps

    1. Go to: https://git-scm.com/download/win
    2. Download Git for Windows
    3. Run the installer
    4. During installation:
        Keep the default options
        Make sure "Git from the command line and also from 3rd-party software" is selected
    5. Finish installation

### Git Installation Screenshots

<img src="screenshots/git_install.png" width="400">
<img src="screenshots/git_install2.png" width="400">
<img src="screenshots/git_install3.png" width="400">
<img src="screenshots/git_install4.png" width="400">
<img src="screenshots/git_install5.png" width="400">
<img src="screenshots/git_install6.png" width="400">
<img src="screenshots/git_install7.png" width="400">
<img src="screenshots/git_install8.png" width="400">
<img src="screenshots/git_install9.png" width="400">
<img src="screenshots/git_install10.png" width="400">
<img src="screenshots/git_install11.png" width="400">
<img src="screenshots/git_install12.png" width="400">
<img src="screenshots/git_install13.png" width="400">
<img src="screenshots/git_install14.png" width="400">
<img src="screenshots/git_install15.png" width="400">
<img src="screenshots/git_install16.png" width="400">
<img src="screenshots/git_install17.png" width="400">

## 2. Verify Git installation

Open PowerShell and run: git --version

You should see something like: git version 2.x.x

### How to open PowerShell

1. Click the **Start** button (or press the **Windows key**)
2. Type **PowerShell**
3. Click **Windows PowerShell**

![Open PowerShell](screenshots/powershell.png)

## 3. Install python 3.12

### 🐍 Step 1: Go to the official Python website

Open your browser and visit:

👉 https://www.python.org

![Go to Python website](screenshots/python-website.png)

Then:

Hover over Downloads

Click Windows

![Select Windows](screenshots/click-windows.png)

### 🐍 Step 2: Download Python 3.12 installer

On the Windows downloads page:

Find Python 3.12.x

Click "Download Python 3.12.x"

![Get Python 3.12](screenshots/find-python-3.12.png)

This downloads a file like:

```
python-3.12.x-amd64.exe
```

### 🐍 Step 3: Run the installer (IMPORTANT)

Double-click the downloaded .exe file.

⚠️ Before clicking Install, do this:

✅ Check "Add Python 3.12 to PATH"
✅ Then click "Install Now"

This step is critical.

![Install Python](screenshots/python-installer.png)

### 🐍 Step 4: Finish installation

Wait for installation to complete

Click Close

If prompted about long path support → Allow

### 🧪 Step 5: Verify Python installation

Open PowerShell and run:

```
python --version
```

You should see:
```
Python 3.12.x
```

## 4. Clone this repo (one time)

1. Select a directory to clone the repo (e.g., documents)
2. Clone the repo

In the Powershell terminal run:
```
cd C:\Users\<username>\Documents
```
```
git clone https://github.com/jsfakian/CT-DEFACE.git
```

## 5. Run setup and download `CTA_DEFACE` model from google

1. Create the virtual environment
2. Setup CT-DEFACE (installs dependencies)
3. Download CT-DEFACE model

In the PowerShell terminal run:

```
python -m venv .venv_ct_deface
powershell -ExecutionPolicy Bypass -File .\setup_ct_deface_cpu.ps1
powershell -ExecutionPolicy Bypass -File .\download_ct_deface_model.ps1
```

---

# Prerequisites for run 

## Prepare the required directories and the dicom images for defacing

In the PowerShell terminal run:
```
mkdir dicom_input
mkdir dicom_output
mkdir work_deface_batch
```

Then place the dicom images you want to deface in `dicom_input`

---

# ▶️ Windows: Running the Pipeline

### Multi-case batch defacing

1. Open a PowerShell terminal
2. Go to the directory of the CT-DEFACE
3. Activate the virtual environment of CT-DEFACE
4. Run the `ct_deface_pipeline_multi2.py` script

Open a PowerShell terminal and run:

```
cd C:\Users\<username>\Documents\CT-DEFACE
Set-ExecutionPolicy -Scope Process Bypass
.\.venv_ct_deface\Scripts\Activate.ps1
python .\ct_deface_pipeline_multi2.py -i .\dicom_input\ -o .\dicom_output\ --nifti-root-out .\nifti_out\
```

---

# 🛠️ Troubleshooting

## PowerShell script execution error

If you see an error like:

```
File cannot be loaded because running scripts is disabled on this system.
```

Run this in your PowerShell terminal before executing any `.ps1` script:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

This temporarily allows script execution for the current PowerShell session only. It resets automatically when you close the terminal.

> **Note:** Do not use `powershell -ExecutionPolicy Bypass -File` to activate the virtual environment — that runs in a subprocess and will not activate the venv in your current shell.

---

# 🔧 What the Pipeline Does Internally

## 1️⃣ DICOM → NIfTI
- SimpleITK reads series
- Writes:  
  `work_deface_batch/<case>/nifti_in/<SeriesUID>_0000.nii.gz`

## 2️⃣ nnUNetv2 (CPU) defacing
`run_CT-DEFACE.py` performs:
- Mask prediction (`*_mask.nii.gz`)
- Defaced reconstruction (`*_defaced.nii.gz`)  
  (face replaced by safe background intensity)

## 3️⃣ Selecting correct defaced NIfTI
Pipeline ensures:
- Picks `*_defaced.nii.gz`
- Verifies it differs pixel-wise from original

## 4️⃣ NIfTI → DICOM reconstruction
- Looks for best-matching SeriesInstanceUID
- Reuses **all** DICOM metadata:
  - PatientID
  - StudyInstanceUID
  - SeriesInstanceUID
  - Orientation
  - Slice geometry  
- Only `PixelData` is replaced

Output is written to:
```
dicom_output/<case>/<slice>.dcm
```

---

# 💻 Command Reference

## Individual Commands for Advanced Usage

### A. DICOM → NIfTI Conversion Only
Convert DICOM series to NIfTI format without defacing:

**Linux/Windows (same command):**
```bash
python ct_deface_convert.py dicom2nii -i dicom_input -o nii_input
```

### B. NIfTI → DICOM Conversion Only  
Convert defaced NIfTI back to DICOM format. Reuses original DICOM metadata:

**Command:**
```bash
python ct_deface_convert.py nii2dicom -n nii_output/mycase_0000.nii.gz -r dicom_input -o dicom_defaced
```

**Parameters:**
- `-n`: Path to defaced NIfTI file
- `-r`: Original DICOM directory (for metadata reuse)
- `-o`: Output DICOM directory

**Output:**
- Defaced DICOMs in `dicom_defaced/` with:
  - New SeriesInstanceUID and SOPInstanceUIDs
  - Same geometry/spacing as original
  - SeriesDescription appended with "CT-DEFACE"
  - **Original patient info preserved** (not anonymized)

---

# ⚡ GPU Acceleration

While this pipeline is optimized for **CPU-only** inference, you can enable **GPU acceleration** for faster processing:

## Prerequisites
- NVIDIA GPU with CUDA 11.8+ or ROCm support
- CUDA/cuDNN drivers installed

## GPU Installation (Linux/WSL)

### 1. Install GPU-enabled PyTorch

Instead of the CPU setup, activate your venv and install GPU PyTorch:

```bash
source .venv_ct_deface/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

For **ROCm** (AMD GPUs):
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

### 2. nnUNet will auto-detect GPU

The `run_CT-DEFACE.py` script will automatically detect and use available GPUs. No additional configuration needed.

### 3. Run as normal

```bash
# Linux
python ct_deface_pipeline_multi2.py -i dicom_input -o dicom_output

# Windows (with GPU torch installed)
python .\ct_deface_pipeline_multi2.py -i .\dicom_input\ -o .\dicom_output\
```

## Performance Notes

- **GPU speedup**: 5-10× faster on typical NVIDIA RTX GPUs
- **VRAM requirement**: ~4-6 GB for inference
- **Backward compatible**: CPU fallback automatically if GPU unavailable
- **Mixed precision**: For even faster inference, nnUNet supports automatic mixed precision (AMP)

## Troubleshooting GPU Issues

```bash
# Verify CUDA is available in PyTorch
python -c "import torch; print(torch.cuda.is_available())"

# Check CUDA version
python -c "import torch; print(torch.version.cuda)"

# Check available GPUs
python -c "import torch; print(torch.cuda.device_count())"
```

If GPU is not detected:
1. Verify NVIDIA drivers installed: `nvidia-smi`
2. Reinstall PyTorch with correct CUDA version
3. Check environment variables (especially on WSL)

---

# 💻 CLI Reference

```
python ct_deface_pipeline_multi2.py     -i <dicom_root_in>     -o <dicom_root_out>     [--nifti-root-out PATH]     [-w work_deface_batch]     [--ct-extra-args ...]
```

---

# 📚 Citation

Please cite:

**Mahmutoglu et al. (2024), CTA-DEFACE — Deep learning-based CT defacing**  
_European Radiology Experimental_

---


