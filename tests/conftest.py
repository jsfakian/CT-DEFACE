"""
Shared pytest fixtures for CT-DEFACE test suite.

All file I/O uses tmp_path; no hardcoded /tmp paths.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
import nibabel as nib
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian

# ---------------------------------------------------------------------------
# Import run_CT-DEFACE.py (hyphen in filename requires importlib)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent

def _import_run_ct_deface():
    module_path = _PROJECT_ROOT / "run_CT-DEFACE.py"
    spec = importlib.util.spec_from_file_location("run_CT_DEFACE", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_CT_DEFACE"] = mod
    spec.loader.exec_module(mod)
    return mod

# Register the module once at collection time so tests can do:
#   import run_CT_DEFACE as run_deface
_import_run_ct_deface()


# ---------------------------------------------------------------------------
# Synthetic DICOM series
# ---------------------------------------------------------------------------

SERIES_UID = "1.2.3.4.5.6.7.8.9"
STUDY_UID = "9.8.7.6.5.4.3.2.1"
ROWS = 64
COLS = 64
N_SLICES = 5


def _make_dicom_slice(
    dicom_dir: Path,
    index: int,
    series_uid: str = SERIES_UID,
    rows: int = ROWS,
    cols: int = COLS,
    pixel_value: int = 0,
) -> Path:
    """Create a single synthetic DICOM file and return its path."""
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()

    ds.is_implicit_VR = False
    ds.is_little_endian = True

    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = generate_uid()
    ds.SeriesInstanceUID = series_uid
    ds.StudyInstanceUID = STUDY_UID
    ds.PatientID = "TEST001"
    ds.PatientName = "Test^Patient"
    ds.Modality = "CT"

    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = -1024.0

    ds.InstanceNumber = index + 1
    ds.ImagePositionPatient = [0.0, 0.0, float(index)]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 1.0

    data = np.full((rows, cols), pixel_value, dtype=np.int16)
    ds.PixelData = data.tobytes()

    out_path = dicom_dir / f"slice_{index:04d}.dcm"
    ds.save_as(str(out_path), write_like_original=False)
    return out_path


@pytest.fixture
def synthetic_dicom_dir(tmp_path):
    """Minimal valid DICOM series with N_SLICES files."""
    dicom_dir = tmp_path / "dicom_in"
    dicom_dir.mkdir()
    for i in range(N_SLICES):
        _make_dicom_slice(dicom_dir, i, pixel_value=100)
    return dicom_dir


@pytest.fixture
def synthetic_dicom_dir_multi_series(tmp_path):
    """
    DICOM directory containing two different series:
      - series_a: N_SLICES slices  (matching the reference NIfTI)
      - series_b: N_SLICES + 2 slices  (non-matching)
    """
    dicom_dir = tmp_path / "dicom_multi"
    dicom_dir.mkdir()

    series_a_uid = "1.2.3.4.SERIES_A"
    series_b_uid = "1.2.3.4.SERIES_B"

    for i in range(N_SLICES):
        _make_dicom_slice(dicom_dir, i, series_uid=series_a_uid, pixel_value=200)

    for i in range(N_SLICES + 2):
        # Give series_b a different InstanceNumber range to avoid collisions
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.is_implicit_VR = False
        ds.is_little_endian = True
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.SeriesInstanceUID = series_b_uid
        ds.StudyInstanceUID = STUDY_UID
        ds.PatientID = "TEST001"
        ds.Modality = "CT"
        ds.Rows = ROWS
        ds.Columns = COLS
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.RescaleSlope = 1.0
        ds.RescaleIntercept = -1024.0
        ds.InstanceNumber = 100 + i + 1
        ds.ImagePositionPatient = [0.0, 0.0, float(100 + i)]
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.PixelSpacing = [1.0, 1.0]
        ds.SliceThickness = 1.0
        data = np.zeros((ROWS, COLS), dtype=np.int16)
        ds.PixelData = data.tobytes()
        path = dicom_dir / f"slice_b_{i:04d}.dcm"
        ds.save_as(str(path), write_like_original=False)

    return dicom_dir, series_a_uid, series_b_uid


# ---------------------------------------------------------------------------
# Synthetic NIfTI volumes
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_nifti(tmp_path):
    """Zero-filled 3D NIfTI with shape (N_SLICES, ROWS, COLS), nnUNet naming."""
    data = np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32)
    nii = nib.Nifti1Image(data, np.eye(4))
    path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
    nib.save(nii, str(path))
    return path


@pytest.fixture
def synthetic_nifti_nonzero(tmp_path):
    """Non-zero NIfTI (distinct from zero-filled defaced output)."""
    data = np.ones((N_SLICES, ROWS, COLS), dtype=np.float32) * 100.0
    nii = nib.Nifti1Image(data, np.eye(4))
    path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
    nib.save(nii, str(path))
    return path


# ---------------------------------------------------------------------------
# Mock nnUNet subprocess
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_nnunet(monkeypatch, tmp_path):
    """
    Replace subprocess.run so that nnUNet-style calls produce a synthetic
    mask NIfTI in the output directory without needing a real model.

    The fake also simulates run_CT-DEFACE.py creating *_defaced.nii.gz files
    by placing them directly in the output dir.
    """

    def fake_run(cmd, **kwargs):
        cmd_list = list(cmd)

        # Locate -i and -o arguments
        try:
            out_dir = cmd_list[cmd_list.index("-o") + 1]
            in_dir = cmd_list[cmd_list.index("-i") + 1]
        except (ValueError, IndexError):
            class Result:
                returncode = 0
            return Result()

        out_path = Path(out_dir)
        in_path = Path(in_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # For each input NIfTI, write a *_defaced.nii.gz with different values
        for nii_file in sorted(in_path.glob("*.nii.gz")):
            stem = nii_file.name
            # Strip _0000.nii.gz -> base
            if stem.endswith("_0000.nii.gz"):
                base = stem[:-12]
            elif stem.endswith(".nii.gz"):
                base = stem[:-7]
            else:
                base = stem

            # Write a defaced NIfTI (all voxels = -1000, distinct from input)
            defaced_data = np.full(
                (N_SLICES, ROWS, COLS), -500.0, dtype=np.float32
            )
            defaced_img = nib.Nifti1Image(defaced_data, np.eye(4))
            nib.save(defaced_img, str(out_path / f"{base}_defaced.nii.gz"))

            # Write mask
            mask_data = np.ones((N_SLICES, ROWS, COLS), dtype=np.uint8)
            mask_img = nib.Nifti1Image(mask_data, np.eye(4))
            nib.save(mask_img, str(out_path / f"{base}_mask.nii.gz"))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    return fake_run
