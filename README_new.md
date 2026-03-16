CPU-only, idempotent setup pipeline

requirements-ct-deface.txt

setup_ct_deface_cpu.sh (main installer, safe to re-run)

run_ct_deface_cpu.sh wrapper so inference is always forced to CPU

Notes:

It reuses the venv if it already exists.

It will only install torch if missing, and uses the CPU wheel index URL.

It creates/uses a local nnunet_data structure and exports nnUNet_* for the duration of the script.

It downloads the Google Drive model folder into ./model/Dataset001_DEFACE 

It is safe to re-run any time; it just skips already-done steps.

DICOM ➜ NIfTI (for CT-DEFACE input): 

python ct_deface_convert.py dicom2nii -i dicom_input -o nii_input

NIfTI ➜ DICOM (defaced volume back to DICOM)

python ct_deface_convert.py nii2dicom -n nii_output/mycase_0000.nii.gz -r dicom_input -o dicom_defaced

where

>> -r dicom_input is the original series you used for conversion.

>> Output DICOMs appear in dicom_defaced/, with:

>> new SeriesInstanceUID and SOPInstanceUIDs

>> same geometry/spacing as reference

>> SeriesDescription appended with CT-DEFACE

FULL pipeline: DICOM → NIfTI → CT-DEFACE → NIfTI → DICOM (fully reuse the original DICOM headers (no anonymization, same UIDs, same patient info) — only PixelData is replaced)

python ct_deface_pipeline_fullref.py -i /path/to/dicom_original -o /path/to/dicom_defaced

DICOM → NIfTI: Reads the single series in /path/to/dicom_original / Writes NIfTI to work_deface_single/nifti_in/SeriesUID_0000.nii.gz

CT-DEFACE (CPU): Calls run_CT-DEFACE.py -i work_deface_single/nifti_in -o work_deface_single/nifti_out

NIfTI → DICOM (full header reuse): Loads the defaced NIfTI from nifti_out / Loads original DICOMs from /path/to/dicom_original

Saves to /path/to/dicom_defaced with the same filenames as original

Cleans up the work_deface_single/ folder unless  flag added:  --keep-intermediate