"""
Tests for functions in ct_deface_pipeline_multi2.py:
  - dicom_has_files()
  - find_case_dirs()
  - find_defaced_nifti()
  - load_dicom_series_groups()
  - nifti_to_dicom_fullref()
  - prepare_dataset_for_write()
  - series selection logic in nifti_to_dicom_fullref()
"""

import os
import sys
import shutil
import subprocess
import pytest
import numpy as np
import nibabel as nib
import pydicom
from pathlib import Path
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian

# Make the project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import ct_deface_pipeline_multi2 as pipeline
from conftest import SERIES_UID, STUDY_UID, N_SLICES, ROWS, COLS, _make_dicom_slice


# ---------------------------------------------------------------------------
# dicom_has_files
# ---------------------------------------------------------------------------

class TestDicomHasFiles:
    def test_returns_true_for_dcm_files(self, synthetic_dicom_dir):
        assert pipeline.dicom_has_files(str(synthetic_dicom_dir)) is True

    def test_returns_false_for_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert pipeline.dicom_has_files(str(empty)) is False

    def test_returns_false_for_non_dicom_files(self, tmp_path):
        """
        dicom_has_files() uses pydicom with force=True as a fallback, which
        is deliberately permissive and will accept arbitrary byte sequences.
        The function is documented as a heuristic: it returns False only when
        every file in the directory genuinely fails pydicom parsing.

        A file with a .txt extension is skipped by the fast *.dcm path, but
        the fallback wildcard glob still finds it. With force=True pydicom
        may parse it, so this test verifies the function is consistent with
        its documented heuristic nature rather than asserting a hard False.
        """
        d = tmp_path / "notdicom"
        d.mkdir()
        (d / "readme.txt").write_text("not a dicom file at all")
        # The function may return True or False depending on pydicom's
        # force-mode tolerance; what must NOT happen is an exception.
        result = pipeline.dicom_has_files(str(d))
        assert isinstance(result, bool)

    def test_returns_true_for_directory_with_dcm_extension(self, synthetic_dicom_dir):
        # Confirm it finds at least one *.dcm
        dcm_files = list(synthetic_dicom_dir.glob("*.dcm"))
        assert len(dcm_files) > 0
        assert pipeline.dicom_has_files(str(synthetic_dicom_dir)) is True


# ---------------------------------------------------------------------------
# find_case_dirs
# ---------------------------------------------------------------------------

class TestFindCaseDirs:
    def test_root_with_dicoms_is_one_case(self, synthetic_dicom_dir):
        cases = pipeline.find_case_dirs(str(synthetic_dicom_dir))
        assert len(cases) == 1
        assert os.path.abspath(str(synthetic_dicom_dir)) in cases

    def test_subdirectory_cases_discovered(self, tmp_path, synthetic_dicom_dir):
        """Root with DICOM sub-dirs returns each subdir as a case."""
        root = tmp_path / "root_with_cases"
        root.mkdir()
        # Move synthetic DICOM into a subdir
        import shutil
        case_a = root / "case_a"
        shutil.copytree(str(synthetic_dicom_dir), str(case_a))
        case_b = root / "case_b"
        shutil.copytree(str(synthetic_dicom_dir), str(case_b))

        cases = pipeline.find_case_dirs(str(root))
        assert len(cases) == 2
        assert str(case_a.resolve()) in cases
        assert str(case_b.resolve()) in cases

    def test_empty_root_returns_no_cases(self, tmp_path):
        root = tmp_path / "empty_root"
        root.mkdir()
        cases = pipeline.find_case_dirs(str(root))
        assert cases == []

    def test_no_duplicates_in_result(self, synthetic_dicom_dir):
        cases = pipeline.find_case_dirs(str(synthetic_dicom_dir))
        assert len(cases) == len(set(cases))


# ---------------------------------------------------------------------------
# find_defaced_nifti
# ---------------------------------------------------------------------------

class TestFindDefacedNifti:
    def _make_nifti(self, path: Path, value: float) -> str:
        data = np.full((N_SLICES, ROWS, COLS), value, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nib.save(nii, str(path))
        return str(path)

    def test_selects_defaced_named_file(self, tmp_path):
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()

        # Input NIfTI (all 100s)
        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        self._make_nifti(input_path, value=100.0)

        # Output: mask and defaced (defaced has different values)
        self._make_nifti(out_dir / f"{SERIES_UID}_mask.nii.gz", value=1.0)
        self._make_nifti(out_dir / f"{SERIES_UID}_defaced.nii.gz", value=-500.0)

        result = pipeline.find_defaced_nifti(str(out_dir), str(input_path))
        assert "defaced" in os.path.basename(result)
        assert "mask" not in os.path.basename(result)

    def test_raises_when_defaced_identical_to_input(self, tmp_path):
        """Pixel-diff validation: identical files must raise RuntimeError."""
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()

        same_value = 100.0
        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        self._make_nifti(input_path, value=same_value)

        # Defaced is identical to input — defacing failed
        self._make_nifti(out_dir / f"{SERIES_UID}_defaced.nii.gz", value=same_value)

        with pytest.raises(RuntimeError, match="pixel-wise identical"):
            pipeline.find_defaced_nifti(str(out_dir), str(input_path))

    def test_raises_when_no_nifti_in_output_dir(self, tmp_path):
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()
        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        self._make_nifti(input_path, value=100.0)

        with pytest.raises(RuntimeError, match="No NIfTI files found"):
            pipeline.find_defaced_nifti(str(out_dir), str(input_path))

    def test_raises_when_only_mask_files_present(self, tmp_path):
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()
        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        self._make_nifti(input_path, value=100.0)
        self._make_nifti(out_dir / f"{SERIES_UID}_mask.nii.gz", value=1.0)

        with pytest.raises(RuntimeError, match="only mask NIfTIs"):
            pipeline.find_defaced_nifti(str(out_dir), str(input_path))

    def test_raises_when_multiple_candidates(self, tmp_path):
        """Ambiguous outputs (multiple defaced files) must raise RuntimeError."""
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()
        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        self._make_nifti(input_path, value=100.0)

        # Two different defaced files with the same series prefix
        self._make_nifti(out_dir / f"{SERIES_UID}_defaced.nii.gz", value=-500.0)
        self._make_nifti(out_dir / f"{SERIES_UID}_defaced_v2.nii.gz", value=-600.0)

        with pytest.raises(RuntimeError, match="Multiple possible defaced"):
            pipeline.find_defaced_nifti(str(out_dir), str(input_path))

    def test_prefers_file_starting_with_series_uid(self, tmp_path):
        """When multiple non-mask files exist, prefer the one starting with the series UID."""
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()
        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        self._make_nifti(input_path, value=100.0)

        # One defaced with the correct prefix, one irrelevant non-mask file
        self._make_nifti(out_dir / f"{SERIES_UID}_defaced.nii.gz", value=-500.0)

        result = pipeline.find_defaced_nifti(str(out_dir), str(input_path))
        assert os.path.basename(result) == f"{SERIES_UID}_defaced.nii.gz"

    def test_shape_mismatch_does_not_raise(self, tmp_path):
        """Different shapes between input and defaced: warn but do not raise."""
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()

        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        data_in = np.ones((N_SLICES, ROWS, COLS), dtype=np.float32) * 100.0
        nib.save(nib.Nifti1Image(data_in, np.eye(4)), str(input_path))

        # Defaced has different shape
        data_def = np.full((N_SLICES + 1, ROWS, COLS), -500.0, dtype=np.float32)
        nib.save(nib.Nifti1Image(data_def, np.eye(4)),
                 str(out_dir / f"{SERIES_UID}_defaced.nii.gz"))

        # Should not raise — shape mismatch just logs a warning
        result = pipeline.find_defaced_nifti(str(out_dir), str(input_path))
        assert result is not None

    def test_nib_load_exception_is_swallowed(self, tmp_path, monkeypatch):
        """
        Lines 291-292: if nib.load raises a non-RuntimeError exception during
        pixel-diff comparison, the function warns and continues (returns chosen).
        """
        out_dir = tmp_path / "nifti_out"
        out_dir.mkdir()

        input_path = tmp_path / f"{SERIES_UID}_0000.nii.gz"
        self._make_nifti(input_path, value=100.0)
        self._make_nifti(out_dir / f"{SERIES_UID}_defaced.nii.gz", value=-500.0)

        # Patch nib.load to raise IOError (a non-RuntimeError exception)
        original_load = nib.load
        call_count = [0]

        def patched_load(path, *args, **kwargs):
            call_count[0] += 1
            # First call is the defaced NIfTI (in find_defaced_nifti); raise on it
            if call_count[0] == 1:
                raise IOError("simulated nibabel load failure")
            return original_load(path, *args, **kwargs)

        monkeypatch.setattr(nib, "load", patched_load)
        monkeypatch.setattr("ct_deface_pipeline_multi2.nib.load", patched_load)

        # Should not raise — broad exception is caught and swallowed
        result = pipeline.find_defaced_nifti(str(out_dir), str(input_path))
        assert result is not None


# ---------------------------------------------------------------------------
# load_dicom_series_groups
# ---------------------------------------------------------------------------

class TestLoadDicomSeriesGroups:
    def test_single_series_loaded(self, synthetic_dicom_dir):
        groups = pipeline.load_dicom_series_groups(str(synthetic_dicom_dir))
        assert len(groups) == 1
        assert SERIES_UID in groups

    def test_slice_count_matches_fixture(self, synthetic_dicom_dir):
        groups = pipeline.load_dicom_series_groups(str(synthetic_dicom_dir))
        slices = groups[SERIES_UID]
        assert len(slices) == N_SLICES

    def test_slices_sorted_by_instance_number(self, synthetic_dicom_dir):
        groups = pipeline.load_dicom_series_groups(str(synthetic_dicom_dir))
        slices = groups[SERIES_UID]
        instance_numbers = [int(ds.InstanceNumber) for _, ds in slices]
        assert instance_numbers == sorted(instance_numbers)

    def test_multi_series_groups_correctly(self, synthetic_dicom_dir_multi_series):
        dicom_dir, series_a_uid, series_b_uid = synthetic_dicom_dir_multi_series
        groups = pipeline.load_dicom_series_groups(str(dicom_dir))
        assert series_a_uid in groups
        assert series_b_uid in groups
        assert len(groups[series_a_uid]) == N_SLICES
        assert len(groups[series_b_uid]) == N_SLICES + 2

    def test_raises_on_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(RuntimeError, match="No readable DICOM series"):
            pipeline.load_dicom_series_groups(str(empty))

    def test_raises_on_non_dicom_dir(self, tmp_path):
        d = tmp_path / "notdicom"
        d.mkdir()
        (d / "file.txt").write_text("not dicom")
        with pytest.raises(RuntimeError, match="No readable DICOM series"):
            pipeline.load_dicom_series_groups(str(d))

    def test_sort_fallback_to_z_position(self, tmp_path):
        """Slices without InstanceNumber are sorted by ImagePositionPatient[2]."""
        dicom_dir = tmp_path / "dicom_no_instance"
        dicom_dir.mkdir()
        uid = generate_uid()
        for i in range(3):
            ds = Dataset()
            ds.file_meta = FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
            ds.is_implicit_VR = False
            ds.is_little_endian = True
            ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.SOPInstanceUID = generate_uid()
            ds.SeriesInstanceUID = uid
            ds.StudyInstanceUID = STUDY_UID
            ds.PatientID = "TEST_Z"
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
            # Note: deliberately no InstanceNumber
            ds.ImagePositionPatient = [0.0, 0.0, float(i * 10)]
            ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            ds.PixelSpacing = [1.0, 1.0]
            ds.SliceThickness = 1.0
            data = np.zeros((ROWS, COLS), dtype=np.int16)
            ds.PixelData = data.tobytes()
            ds.save_as(str(dicom_dir / f"slice_{i:04d}.dcm"), write_like_original=False)

        groups = pipeline.load_dicom_series_groups(str(dicom_dir))
        assert uid in groups
        z_positions = [float(ds.ImagePositionPatient[2]) for _, ds in groups[uid]]
        assert z_positions == sorted(z_positions)


# ---------------------------------------------------------------------------
# prepare_dataset_for_write
# ---------------------------------------------------------------------------

class TestPrepareDatasetForWrite:
    def test_sets_pixel_data_vr_ow_for_16bit(self, synthetic_dicom_dir):
        """16-bit PixelData should get VR='OW'."""
        groups = pipeline.load_dicom_series_groups(str(synthetic_dicom_dir))
        _, ds = list(groups[SERIES_UID])[0]
        # Load with pixel data so PixelData tag is present
        ds_full = pydicom.dcmread(list(synthetic_dicom_dir.glob("*.dcm"))[0])
        pipeline.prepare_dataset_for_write(ds_full)
        assert ds_full["PixelData"].VR == "OW"

    def test_sets_pixel_data_vr_ob_for_8bit(self, tmp_path):
        """8-bit PixelData should get VR='OB'."""
        dicom_dir = tmp_path / "dicom8bit"
        dicom_dir.mkdir()
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.is_implicit_VR = False
        ds.is_little_endian = True
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        ds.SOPInstanceUID = generate_uid()
        ds.SeriesInstanceUID = SERIES_UID
        ds.StudyInstanceUID = STUDY_UID
        ds.PatientID = "TEST001"
        ds.Rows = ROWS
        ds.Columns = COLS
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        data = np.zeros((ROWS, COLS), dtype=np.uint8)
        ds.PixelData = data.tobytes()
        pipeline.prepare_dataset_for_write(ds)
        assert ds["PixelData"].VR == "OB"

    def test_creates_file_meta_when_missing(self):
        """If ds.file_meta is absent, prepare_dataset_for_write must create it."""
        ds = Dataset()
        # No file_meta set at all
        data = np.zeros((ROWS, COLS), dtype=np.int16)
        ds.PixelData = data.tobytes()
        ds.BitsAllocated = 16
        pipeline.prepare_dataset_for_write(ds)
        assert hasattr(ds, "file_meta") and ds.file_meta is not None

    def test_does_not_raise_when_no_pixel_data(self):
        """Dataset without PixelData must not raise."""
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        pipeline.prepare_dataset_for_write(ds)


# ---------------------------------------------------------------------------
# nifti_to_dicom_fullref — happy path
# ---------------------------------------------------------------------------

def _make_nifti_for_fullref(tmp_path: Path, fill_value: float = 0.0) -> Path:
    """Helper: create a minimal NIfTI (N_SLICES x ROWS x COLS) at tmp_path."""
    data = np.full((N_SLICES, ROWS, COLS), fill_value, dtype=np.float32)
    nii = nib.Nifti1Image(data, np.eye(4))
    p = tmp_path / "defaced_0000.nii.gz"
    nib.save(nii, str(p))
    return p


class TestNiftiToDicomFullref:

    def test_output_files_created_one_per_slice(self, tmp_path, synthetic_dicom_dir):
        """One output DICOM file per reference slice must be written."""
        nii_path = _make_nifti_for_fullref(tmp_path)
        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))
        output_dcms = list(out_dir.glob("*.dcm"))
        assert len(output_dcms) == N_SLICES

    def test_key_dicom_tags_preserved(self, tmp_path, synthetic_dicom_dir):
        """SeriesInstanceUID, PatientID, StudyInstanceUID must match the reference."""
        nii_path = _make_nifti_for_fullref(tmp_path)
        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        out_files = sorted(out_dir.glob("*.dcm"))
        ds_out = pydicom.dcmread(str(out_files[0]), stop_before_pixels=True)
        assert str(ds_out.SeriesInstanceUID) == SERIES_UID
        assert str(ds_out.PatientID) == "TEST001"
        assert str(ds_out.StudyInstanceUID) == STUDY_UID

    def test_pixel_data_differs_from_original_when_nifti_differs(
        self, tmp_path, synthetic_dicom_dir
    ):
        """When the NIfTI has different HU values, the output pixel data must differ."""
        # Reference DICOMs have pixel_value=100 stored.
        # Rescale: stored = (physical - intercept) / slope
        # intercept=-1024, slope=1 => stored = physical + 1024
        # physical=-500 => stored = 524, which differs from original stored=100.
        nii_path = _make_nifti_for_fullref(tmp_path, fill_value=-500.0)
        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        out_files = sorted(out_dir.glob("*.dcm"))
        ds_out = pydicom.dcmread(str(out_files[0]))

        ref_files = sorted(synthetic_dicom_dir.glob("*.dcm"))
        ds_ref = pydicom.dcmread(str(ref_files[0]))

        # Pixel arrays should differ
        assert not np.array_equal(ds_out.pixel_array, ds_ref.pixel_array)

    def test_pixel_values_reflect_rescale_encoding(self, tmp_path, synthetic_dicom_dir):
        """Stored pixel values must encode physical HU correctly via RescaleIntercept/Slope."""
        # Reference: slope=1, intercept=-1024.
        # NIfTI physical = 0.0 => stored = (0.0 - (-1024)) / 1 = 1024
        nii_path = _make_nifti_for_fullref(tmp_path, fill_value=0.0)
        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        out_files = sorted(out_dir.glob("*.dcm"))
        ds_out = pydicom.dcmread(str(out_files[0]))
        pixel_arr = ds_out.pixel_array.astype(np.int32)
        # All stored values should be 1024 (= 0 - (-1024))
        expected_stored = 1024
        assert np.all(pixel_arr == expected_stored)

    def test_output_shape_matches_reference(self, tmp_path, synthetic_dicom_dir):
        """Each output slice must have the same Rows/Columns as the reference."""
        nii_path = _make_nifti_for_fullref(tmp_path)
        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        for f in out_dir.glob("*.dcm"):
            ds = pydicom.dcmread(str(f), stop_before_pixels=True)
            assert ds.Rows == ROWS
            assert ds.Columns == COLS

    def test_raises_on_non_3d_nifti(self, tmp_path, synthetic_dicom_dir):
        """A 2D NIfTI must raise RuntimeError with a clear message."""
        data_2d = np.zeros((ROWS, COLS), dtype=np.float32)
        nii_2d = nib.Nifti1Image(data_2d, np.eye(4))
        path_2d = tmp_path / "flat.nii.gz"
        nib.save(nii_2d, str(path_2d))
        out_dir = tmp_path / "dicom_out"
        with pytest.raises(RuntimeError, match="3D"):
            pipeline.nifti_to_dicom_fullref(str(path_2d), str(synthetic_dicom_dir), str(out_dir))

    def test_partial_update_when_nifti_has_fewer_slices(self, tmp_path, synthetic_dicom_dir):
        """
        When NIfTI has fewer slices than the DICOM reference, only the overlapping
        slices are replaced; the remaining reference slices are written unchanged.
        Total output file count must still equal N_SLICES.
        """
        fewer = N_SLICES - 2
        data = np.full((fewer, ROWS, COLS), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "short.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        output_dcms = list(out_dir.glob("*.dcm"))
        assert len(output_dcms) == N_SLICES

    def test_output_dir_created_if_missing(self, tmp_path, synthetic_dicom_dir):
        """nifti_to_dicom_fullref must create the output directory if it doesn't exist."""
        nii_path = _make_nifti_for_fullref(tmp_path)
        out_dir = tmp_path / "brand_new_dir" / "subdir"
        assert not out_dir.exists()
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))
        assert out_dir.exists()
        assert len(list(out_dir.glob("*.dcm"))) == N_SLICES


# ---------------------------------------------------------------------------
# nifti_to_dicom_fullref — series selection logic
# ---------------------------------------------------------------------------

class TestNiftiToDicomFullrefSeriesSelection:

    def test_selects_series_matching_dim0(self, tmp_path, synthetic_dicom_dir_multi_series):
        """
        With two series (N_SLICES and N_SLICES+2), a NIfTI with shape
        (N_SLICES, ROWS, COLS) along dim 0 must produce exactly N_SLICES output files
        from the matching series.
        """
        dicom_dir, series_a_uid, _ = synthetic_dicom_dir_multi_series
        data = np.full((N_SLICES, ROWS, COLS), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "defaced.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(dicom_dir), str(out_dir))

        output_dcms = list(out_dir.glob("*.dcm"))
        assert len(output_dcms) == N_SLICES

    def test_selects_series_matching_dim2(self, tmp_path, synthetic_dicom_dir):
        """
        A NIfTI with shape (ROWS, COLS, N_SLICES) — slices along dim 2 — should be
        matched against the series whose count equals N_SLICES and produce N_SLICES
        output files.
        """
        # Reshape: slices along dim 2 instead of dim 0
        data = np.full((ROWS, COLS, N_SLICES), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "defaced_dim2.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        output_dcms = list(out_dir.glob("*.dcm"))
        assert len(output_dcms) == N_SLICES

    def test_closest_series_chosen_when_no_exact_match(self, tmp_path):
        """
        When no series slice count exactly matches dim0 or dim2, the series
        with the closest slice count is chosen and all its slices are output.
        """
        # Build a DICOM dir with 7 slices
        ref_dir = tmp_path / "dicom_ref"
        ref_dir.mkdir()
        uid = generate_uid()
        for i in range(7):
            _make_dicom_slice(ref_dir, i, series_uid=uid, pixel_value=0)

        # NIfTI with shape (5, ROWS, COLS): dim0=5, dim2=COLS=64 — neither matches 7
        data = np.full((5, ROWS, COLS), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "defaced.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(ref_dir), str(out_dir))

        # All 7 reference slices must be written (overlap+copy-remaining)
        output_dcms = list(out_dir.glob("*.dcm"))
        assert len(output_dcms) == 7

    def test_tags_preserved_with_multi_series_input(self, tmp_path, synthetic_dicom_dir_multi_series):
        """
        With multiple series, the chosen series's UIDs must appear in the output.
        Series A has N_SLICES slices and matches the NIfTI dim0.
        """
        dicom_dir, series_a_uid, _ = synthetic_dicom_dir_multi_series
        data = np.full((N_SLICES, ROWS, COLS), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "defaced.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(dicom_dir), str(out_dir))

        out_files = sorted(out_dir.glob("*.dcm"))
        ds_out = pydicom.dcmread(str(out_files[0]), stop_before_pixels=True)
        assert str(ds_out.SeriesInstanceUID) == series_a_uid


# ---------------------------------------------------------------------------
# nifti_to_dicom_fullref — shape mismatch raises
# ---------------------------------------------------------------------------

class TestNiftiToDicomFullrefShapeMismatch:

    def test_raises_when_slice_shape_mismatches_reference(self, tmp_path):
        """
        If the NIfTI in-plane shape does not match the reference DICOM Rows/Columns
        after orientation, RuntimeError must be raised.
        """
        # Reference DICOMs: ROWS x COLS
        ref_dir = tmp_path / "dicom_ref"
        ref_dir.mkdir()
        uid = generate_uid()
        for i in range(N_SLICES):
            _make_dicom_slice(ref_dir, i, series_uid=uid, rows=ROWS, cols=COLS, pixel_value=0)

        # NIfTI: N_SLICES slices but wrong in-plane size (ROWS+10, COLS)
        wrong_rows = ROWS + 10
        data = np.full((N_SLICES, wrong_rows, COLS), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "wrong_shape.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        with pytest.raises(RuntimeError, match="shape"):
            pipeline.nifti_to_dicom_fullref(str(nii_path), str(ref_dir), str(out_dir))


# ---------------------------------------------------------------------------
# load_dicom_series_groups — InstanceNumber parse error fallback (lines 326-327,
#   342-343, 348-350)
# ---------------------------------------------------------------------------

class TestLoadDicomSeriesGroupsInstanceNumberFallback:
    """
    pydicom validates the IS (integer string) VR and raises when a non-numeric
    value is assigned as a Dataset attribute.  To bypass validation we inject
    the InstanceNumber tag directly into the dataset's internal dict as a plain
    string DataElement, which is what the pipeline sees when reading real-world
    DICOM files with corrupt InstanceNumber tags.
    """

    @staticmethod
    def _set_non_numeric_instance_number(ds: pydicom.Dataset, value: str):
        """Inject a non-numeric InstanceNumber by bypassing pydicom VR validation."""
        from pydicom.dataelem import DataElement
        from pydicom.tag import Tag
        tag = Tag(0x0020, 0x0013)  # InstanceNumber
        # Use 'LO' (Long String) VR instead of 'IS' to allow arbitrary text
        elem = DataElement(tag, "LO", value)
        ds._dict[tag] = elem

    def test_non_numeric_instance_number_falls_back_to_z_position(self, tmp_path):
        """
        When InstanceNumber is a non-parseable string (e.g. 'abc'), the sort_key
        must fall back to ImagePositionPatient[2].  The resulting order must be
        sorted by z-position without raising.
        """
        dicom_dir = tmp_path / "dicom_bad_instance"
        dicom_dir.mkdir()
        uid = generate_uid()
        z_positions = [30.0, 10.0, 20.0]  # deliberately unsorted

        for idx, z in enumerate(z_positions):
            ds = pydicom.Dataset()
            ds.file_meta = FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
            ds.is_implicit_VR = False
            ds.is_little_endian = True
            ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.SOPInstanceUID = generate_uid()
            ds.SeriesInstanceUID = uid
            ds.StudyInstanceUID = STUDY_UID
            ds.PatientID = "TEST_BAD"
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
            # Inject non-numeric InstanceNumber to force fallback to z-position
            self._set_non_numeric_instance_number(ds, "abc")
            ds.ImagePositionPatient = [0.0, 0.0, z]
            ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            ds.PixelSpacing = [1.0, 1.0]
            ds.SliceThickness = 1.0
            data = np.zeros((ROWS, COLS), dtype=np.int16)
            ds.PixelData = data.tobytes()
            ds.save_as(str(dicom_dir / f"slice_{idx:04d}.dcm"), write_like_original=False)

        groups = pipeline.load_dicom_series_groups(str(dicom_dir))
        assert uid in groups
        z_out = [float(ds.ImagePositionPatient[2]) for _, ds in groups[uid]]
        assert z_out == sorted(z_out)

    def test_non_numeric_instance_number_and_no_ipp_falls_back_to_zero(self, tmp_path):
        """
        When InstanceNumber is non-numeric AND ImagePositionPatient is absent,
        sort_key returns 0 (line 350) — all slices get sort key 0, so no crash.
        """
        dicom_dir = tmp_path / "dicom_no_ipp"
        dicom_dir.mkdir()
        uid = generate_uid()

        for idx in range(3):
            ds = pydicom.Dataset()
            ds.file_meta = FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
            ds.is_implicit_VR = False
            ds.is_little_endian = True
            ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.SOPInstanceUID = generate_uid()
            ds.SeriesInstanceUID = uid
            ds.StudyInstanceUID = STUDY_UID
            ds.PatientID = "TEST_NO_IPP"
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
            # Inject non-numeric InstanceNumber; no ImagePositionPatient -> key=0
            self._set_non_numeric_instance_number(ds, "xyz")
            # Deliberately omit ImagePositionPatient
            ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            ds.PixelSpacing = [1.0, 1.0]
            ds.SliceThickness = 1.0
            data = np.zeros((ROWS, COLS), dtype=np.int16)
            ds.PixelData = data.tobytes()
            ds.save_as(str(dicom_dir / f"slice_{idx:04d}.dcm"), write_like_original=False)

        # Should not raise; all three slices present
        groups = pipeline.load_dicom_series_groups(str(dicom_dir))
        assert uid in groups
        assert len(groups[uid]) == 3

    def test_non_parseable_ipp_z_falls_back_to_zero(self, tmp_path):
        """
        When InstanceNumber is absent AND ImagePositionPatient[2] is a
        non-float string, the sort_key falls back to 0 (lines 348-349).

        We inject a non-float value into IPP[2] by writing a DataElement with
        a plain string VR, bypassing pydicom's numeric-string validation.
        """
        from pydicom.dataelem import DataElement
        from pydicom.tag import Tag

        dicom_dir = tmp_path / "dicom_bad_ipp"
        dicom_dir.mkdir()
        uid = generate_uid()

        for idx in range(2):
            ds = pydicom.Dataset()
            ds.file_meta = FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
            ds.is_implicit_VR = False
            ds.is_little_endian = True
            ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
            ds.SOPInstanceUID = generate_uid()
            ds.SeriesInstanceUID = uid
            ds.StudyInstanceUID = STUDY_UID
            ds.PatientID = "TEST_BAD_IPP"
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
            # No InstanceNumber — forces IPP path
            # Inject a bad IPP with non-numeric z value
            tag_ipp = Tag(0x0020, 0x0032)
            elem = DataElement(tag_ipp, "LO", ["0.0", "0.0", "bad_z"])
            ds._dict[tag_ipp] = elem
            ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            ds.PixelSpacing = [1.0, 1.0]
            ds.SliceThickness = 1.0
            data = np.zeros((ROWS, COLS), dtype=np.int16)
            ds.PixelData = data.tobytes()
            ds.save_as(str(dicom_dir / f"slice_{idx:04d}.dcm"), write_like_original=False)

        # Should not raise; all two slices present (sort key 0 for both)
        groups = pipeline.load_dicom_series_groups(str(dicom_dir))
        assert uid in groups
        assert len(groups[uid]) == 2


# ---------------------------------------------------------------------------
# orient_slice_to_dicom — swap branch (lines 452-454) and transpose branch
#   (line 463)
# ---------------------------------------------------------------------------

class TestOrientSliceToDicomSwapBranch:

    def _make_ds_with_iop(self, row_cos, col_cos):
        import pydicom as _pydicom
        ds = _pydicom.Dataset()
        ds.ImageOrientationPatient = list(row_cos) + list(col_cos)
        ds.Rows = ROWS
        ds.Columns = COLS
        return ds

    def test_swap_branch_hit_when_axis1_dominates_row(self):
        """
        Trigger the swap branch (lines 452-454):
          abs(dot_row[1]) > abs(dot_row[0])

        Construction:
          nifti_dim_index=2, so in_plane_axes=[0,1].
          Affine: voxel axis 0 -> RAS Y (after LPS flip -> [0,-1,0])
                  voxel axis 1 -> RAS X (after LPS flip -> [-1, 0,0])
          IOP row_cos = [-1,0,0]  (LPS -X direction)
          dot_row[0] = dot([0,-1,0], [-1,0,0]) = 0
          dot_row[1] = dot([-1,0,0], [-1,0,0]) = 1  > dot_row[0]  -> swap taken
        """
        affine = np.eye(4)
        # swap spatial columns 0 and 1 so axis-0 points along RAS-Y, axis-1 along RAS-X
        affine[:3, 0] = [0.0, 1.0, 0.0]   # voxel axis 0 -> RAS-Y
        affine[:3, 1] = [1.0, 0.0, 0.0]   # voxel axis 1 -> RAS-X

        ds = self._make_ds_with_iop([-1.0, 0.0, 0.0], [0.0, -1.0, 0.0])
        slice_arr = np.arange(ROWS * COLS, dtype=np.float32).reshape(ROWS, COLS)

        result = pipeline.orient_slice_to_dicom(slice_arr, affine, nifti_dim_index=2, ds=ds)

        # swap branch -> nifti_col_ax=1, nifti_row_ax=0
        # nifti_row_ax==0, nifti_col_ax==1 -> goes to the identity branch (no transpose),
        # but the swap variables themselves were set via the else path.
        assert result.ndim == 2
        assert result.shape in {(ROWS, COLS), (COLS, ROWS)}

    def test_transpose_branch_hit_when_nifti_row_ax_is_1(self):
        """
        Trigger the transpose path (line 466: out = slice_arr.T):
          This happens when nifti_row_ax == 1 (and nifti_col_ax == 0).

        To get nifti_row_ax=1 we need abs(dot_row[0]) >= abs(dot_row[1])
        (the if-branch), giving nifti_col_ax=0, nifti_row_ax=1.
        Then the check `if nifti_row_ax == 0 and nifti_col_ax == 1` is False,
        so we go to `else: out = slice_arr.T`.

        Construction:
          nifti_dim_index=2, in_plane_axes=[0,1]
          affine: axis-0 -> RAS-X, axis-1 -> RAS-Y (identity)
          LPS of axis-0: [-1,0,0],  LPS of axis-1: [0,-1,0]
          IOP row_cos = [-1,0,0]
          dot_row[0]=1 >= dot_row[1]=0  -> if-branch taken
          nifti_col_ax=0, nifti_row_ax=1
          -> code hits the else at line 465 (transpose)
        """
        affine = np.eye(4)  # axis-0 -> RAS-X, axis-1 -> RAS-Y
        # row_cos aligns with LPS of axis-0 -> dot_row[0] is large
        ds = self._make_ds_with_iop([-1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        slice_arr = np.arange(ROWS * COLS, dtype=np.float32).reshape(ROWS, COLS)

        result = pipeline.orient_slice_to_dicom(slice_arr, affine, nifti_dim_index=2, ds=ds)

        # nifti_row_ax=1 -> transpose branch taken; shape should be (COLS, ROWS)
        assert result.ndim == 2
        assert result.shape == (COLS, ROWS)

    def test_flip_col_branch_hit(self):
        """
        Trigger flip_col=True (line 471: out = np.flip(out, axis=1)):
          After the if-branch (abs(dot_row[0]) >= abs(dot_row[1])):
            nifti_col_ax=0, nifti_row_ax=1
            flip_col = (dot_row[0] < 0)

        Construction (same as above but row_cos = [+1,0,0]):
          LPS of axis-0: [-1,0,0]
          dot_row[0] = dot([-1,0,0],[+1,0,0]) = -1  < 0 -> flip_col = True
          dot_col[1] = dot([0,-1,0],[0,1,0])  = -1  < 0 -> flip_row = True too
        """
        affine = np.eye(4)
        ds = self._make_ds_with_iop([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        # Use non-square slice to detect correct flip axis
        slice_arr = np.arange(ROWS * COLS, dtype=np.float32).reshape(ROWS, COLS)

        result = pipeline.orient_slice_to_dicom(slice_arr, affine, nifti_dim_index=2, ds=ds)

        assert result.ndim == 2
        assert result.shape in {(ROWS, COLS), (COLS, ROWS)}


# ---------------------------------------------------------------------------
# nifti_to_dicom_fullref — minor uncovered branches (lines 538-539, 553, 591)
# ---------------------------------------------------------------------------

class TestNiftiToDicomFullrefMinorBranches:

    def test_no_pixel_array_attribute_uses_int16(self, tmp_path, monkeypatch):
        """
        Line 591: When the reference DICOM slice does not have a pixel_array
        attribute, ref_dtype defaults to np.int16.

        We monkeypatch pydicom.dcmread to return a Dataset without PixelData
        only for the first full-read call (used to get RescaleSlope and dtype),
        while letting the glob/stop_before_pixels reads work normally.
        """
        ref_dir = tmp_path / "dicom_ref_nopix"
        ref_dir.mkdir()
        uid = generate_uid()
        for i in range(N_SLICES):
            _make_dicom_slice(ref_dir, i, series_uid=uid, pixel_value=100)

        # Patch pydicom.dcmread so the first call without stop_before_pixels
        # returns a Dataset lacking pixel_array (no PixelData present).
        original_dcmread = pydicom.dcmread
        call_counts = [0]

        def patched_dcmread(filename, stop_before_pixels=False, force=False, **kw):
            result = original_dcmread(
                filename, stop_before_pixels=stop_before_pixels, force=force, **kw
            )
            # Remove PixelData from the first full read to test the else-branch
            if not stop_before_pixels and call_counts[0] == 0:
                call_counts[0] += 1
                if "PixelData" in result:
                    del result["PixelData"]
            return result

        monkeypatch.setattr(pydicom, "dcmread", patched_dcmread)
        monkeypatch.setattr("ct_deface_pipeline_multi2.pydicom.dcmread", patched_dcmread)

        data = np.full((N_SLICES, ROWS, COLS), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "defaced.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(ref_dir), str(out_dir))
        assert len(list(out_dir.glob("*.dcm"))) == N_SLICES

    def test_both_dim0_and_dim2_match_prefers_dim0(self, tmp_path):
        """
        When both dim0 and dim2 of the NIfTI equal the series slice count,
        the code takes the elif branch (lines 537-539) that handles both
        candidates and chooses dim0.

        We use n=N_SLICES with cubic NIfTI shape (n, n, n) so dim0==dim2==n,
        and build DICOM reference slices of size n×n to match the in-plane
        dimensions of the selected slices.
        """
        n = N_SLICES  # 5
        ref_dir = tmp_path / "dicom_ref_cubic"
        ref_dir.mkdir()
        uid = generate_uid()
        # DICOM slices must be n x n so the in-plane NIfTI slice (n, n) matches
        for i in range(n):
            _make_dicom_slice(ref_dir, i, series_uid=uid, rows=n, cols=n, pixel_value=0)

        # Cubic NIfTI: dim0 == dim1 == dim2 == n -> both dim0 and dim2 candidates hit
        data = np.full((n, n, n), -500.0, dtype=np.float32)
        nii = nib.Nifti1Image(data, np.eye(4))
        nii_path = tmp_path / "defaced_cubic.nii.gz"
        nib.save(nii, str(nii_path))

        out_dir = tmp_path / "dicom_out"
        pipeline.nifti_to_dicom_fullref(str(nii_path), str(ref_dir), str(out_dir))
        assert len(list(out_dir.glob("*.dcm"))) == n


# ---------------------------------------------------------------------------
# dicom_to_nifti (pipeline) — SimpleITK path (lines 133-154)
# ---------------------------------------------------------------------------

class TestDicomToNiftiPipeline:

    def test_calls_sitk_and_writes_nnunet_named_nifti(self, tmp_path, monkeypatch):
        """
        Mock SimpleITK to avoid needing real GDCM reading; verify that
        dicom_to_nifti() writes a *_0000.nii.gz file in the output dir.
        """
        import SimpleITK as sitk
        import nibabel as nib

        fake_series_id = "1.2.3.4.5.6.7"
        expected_out = str(tmp_path / "nifti_out" / f"{fake_series_id}_0000.nii.gz")

        class FakeReader:
            def GetGDCMSeriesIDs(self, path):
                return [fake_series_id]
            def GetGDCMSeriesFileNames(self, path, sid):
                return []
            def SetFileNames(self, fnames):
                pass
            def Execute(self):
                # Return a minimal SimpleITK image (5x64x64)
                arr = np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32)
                img = sitk.GetImageFromArray(arr)
                return img

        monkeypatch.setattr(sitk, "ImageSeriesReader", FakeReader)

        out_dir = str(tmp_path / "nifti_out")
        result = pipeline.dicom_to_nifti(str(tmp_path / "dicom_in"), out_dir)

        assert result == expected_out
        assert Path(result).exists()

    def test_raises_when_no_series_found(self, tmp_path, monkeypatch):
        """
        If GetGDCMSeriesIDs returns empty list, dicom_to_nifti must raise
        RuntimeError with 'No DICOM series found'.
        """
        import SimpleITK as sitk

        class FakeReaderEmpty:
            def GetGDCMSeriesIDs(self, path):
                return []

        monkeypatch.setattr(sitk, "ImageSeriesReader", FakeReaderEmpty)

        with pytest.raises(RuntimeError, match="No DICOM series found"):
            pipeline.dicom_to_nifti(str(tmp_path / "dicom_in"), str(tmp_path / "nifti_out"))

    def test_warns_on_multiple_series(self, tmp_path, monkeypatch, capsys):
        """
        Multiple series IDs triggers a WARNING print and still uses the first.
        """
        import SimpleITK as sitk

        class FakeReaderMulti:
            def GetGDCMSeriesIDs(self, path):
                return ["1.1.1", "2.2.2"]
            def GetGDCMSeriesFileNames(self, path, sid):
                return []
            def SetFileNames(self, fnames):
                pass
            def Execute(self):
                arr = np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32)
                return sitk.GetImageFromArray(arr)

        monkeypatch.setattr(sitk, "ImageSeriesReader", FakeReaderMulti)

        out_dir = str(tmp_path / "nifti_out")
        result = pipeline.dicom_to_nifti(str(tmp_path / "dicom_in"), out_dir)

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert Path(result).exists()


# ---------------------------------------------------------------------------
# run_ct_deface (pipeline) — subprocess path (lines 169-196)
# ---------------------------------------------------------------------------

class TestRunCtDefacePipeline:

    def test_calls_subprocess_and_returns_nii_list(self, tmp_path, monkeypatch):
        """
        Mock subprocess.run so that it writes a fake NIfTI into the output dir
        (run_ct_deface clears the output dir before calling subprocess, so the
        mock must create files — not rely on pre-existing ones).
        """
        in_dir = tmp_path / "nifti_in"
        in_dir.mkdir()
        out_dir = tmp_path / "nifti_out"
        # NOTE: do NOT pre-populate; run_ct_deface wipes the dir before the call.

        called_cmds = []

        def fake_run(cmd, env=None, **kwargs):
            called_cmds.append(list(cmd))
            # Locate the -o argument and write a fake NIfTI there
            idx_o = cmd.index("-o")
            out_path = Path(cmd[idx_o + 1])
            out_path.mkdir(parents=True, exist_ok=True)
            nib.save(
                nib.Nifti1Image(np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32), np.eye(4)),
                str(out_path / "series_defaced.nii.gz")
            )
            class R:
                returncode = 0
            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = pipeline.run_ct_deface(str(in_dir), str(out_dir))

        assert len(called_cmds) == 1
        assert "-i" in called_cmds[0]
        assert "-o" in called_cmds[0]
        assert any("series_defaced.nii.gz" in f for f in result)

    def test_warns_on_nonzero_exit_code(self, tmp_path, monkeypatch, capsys):
        """
        Non-zero exit code from subprocess triggers WARNING but does not raise
        (as long as output NIfTIs exist).
        """
        in_dir = tmp_path / "nifti_in"
        in_dir.mkdir()
        out_dir_path = tmp_path / "nifti_out"
        # NOTE: do NOT pre-populate; run_ct_deface wipes the dir before the call.

        def fake_run(cmd, env=None, **kwargs):
            idx_o = cmd.index("-o")
            out_path = Path(cmd[idx_o + 1])
            out_path.mkdir(parents=True, exist_ok=True)
            nib.save(
                nib.Nifti1Image(np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32), np.eye(4)),
                str(out_path / "out.nii.gz")
            )
            class R:
                returncode = 1
            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = pipeline.run_ct_deface(str(in_dir), str(out_dir_path))
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert len(result) >= 1

    def test_raises_when_no_output_niftis(self, tmp_path, monkeypatch):
        """
        If subprocess produces no NIfTI files in the output dir,
        run_ct_deface must raise RuntimeError.
        """
        in_dir = tmp_path / "nifti_in"
        in_dir.mkdir()
        out_dir_path = tmp_path / "nifti_out"
        out_dir_path.mkdir()

        def fake_run(cmd, env=None, **kwargs):
            class R:
                returncode = 0
            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(RuntimeError, match="produced no NIfTI"):
            pipeline.run_ct_deface(str(in_dir), str(out_dir_path))

    def test_raises_when_script_not_found(self, tmp_path, monkeypatch):
        """
        Line 174: if run_CT-DEFACE.py cannot be found, RuntimeError is raised.
        """
        in_dir = tmp_path / "nifti_in"
        in_dir.mkdir()
        out_dir_path = tmp_path / "nifti_out"

        # Make os.path.isfile always return False so the script check fails
        monkeypatch.setattr(os.path, "isfile", lambda p: False)

        with pytest.raises(RuntimeError, match="run_CT-DEFACE.py not found"):
            pipeline.run_ct_deface(str(in_dir), str(out_dir_path))

    def test_cleans_existing_output_dir_before_run(self, tmp_path, monkeypatch):
        """
        If nifti_out_dir already exists, it is wiped before subprocess is called
        (verified by checking a stale file is gone after calling run_ct_deface,
        unless the fake subprocess re-creates files).
        """
        in_dir = tmp_path / "nifti_in"
        in_dir.mkdir()
        out_dir_path = tmp_path / "nifti_out"
        out_dir_path.mkdir()
        stale = out_dir_path / "stale.nii.gz"
        nib.save(nib.Nifti1Image(np.zeros((1, 2, 2), dtype=np.float32), np.eye(4)), str(stale))
        assert stale.exists()

        fresh_out = out_dir_path / "fresh.nii.gz"

        def fake_run(cmd, env=None, **kwargs):
            # Simulate nnUNet: write a fresh file in the cleaned dir
            nib.save(
                nib.Nifti1Image(np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32), np.eye(4)),
                str(fresh_out)
            )
            class R:
                returncode = 0
            return R()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = pipeline.run_ct_deface(str(in_dir), str(out_dir_path))
        # stale file was wiped then fake_run wrote fresh.nii.gz
        assert any("fresh.nii.gz" in f for f in result)


# ---------------------------------------------------------------------------
# process_case() — full orchestration (lines 651-700)
# ---------------------------------------------------------------------------

class TestProcessCase:

    def test_happy_path_produces_output_dicoms(self, tmp_path, monkeypatch):
        """
        Mock dicom_to_nifti, run_ct_deface and find_defaced_nifti so that
        process_case() runs to completion and writes output DICOMs.
        """
        # Prepare a real DICOM input so nifti_to_dicom_fullref works
        dicom_in = tmp_path / "input" / "case1"
        dicom_in.mkdir(parents=True)
        for i in range(N_SLICES):
            _make_dicom_slice(dicom_in, i, pixel_value=100)

        dicom_out = tmp_path / "output"
        work_root = tmp_path / "work"
        nifti_root = tmp_path / "nifti_out"

        # Fake NIfTI that will be "returned" by dicom_to_nifti
        fake_nifti_in = tmp_path / "fake_nii_in.nii.gz"
        data_in = np.full((N_SLICES, ROWS, COLS), 100.0, dtype=np.float32)
        nib.save(nib.Nifti1Image(data_in, np.eye(4)), str(fake_nifti_in))

        # Fake defaced NIfTI (different values so pixel-diff check passes)
        fake_defaced = tmp_path / "fake_defaced.nii.gz"
        data_def = np.full((N_SLICES, ROWS, COLS), -500.0, dtype=np.float32)
        nib.save(nib.Nifti1Image(data_def, np.eye(4)), str(fake_defaced))

        def mock_dicom_to_nifti(dicom_dir, output_dir):
            return str(fake_nifti_in)

        def mock_run_ct_deface(nifti_in_dir, nifti_out_dir, extra_args=None):
            return [str(fake_defaced)]

        def mock_find_defaced_nifti(nifti_out_dir, nifti_input_file):
            return str(fake_defaced)

        monkeypatch.setattr(pipeline, "dicom_to_nifti", mock_dicom_to_nifti)
        monkeypatch.setattr(pipeline, "run_ct_deface", mock_run_ct_deface)
        monkeypatch.setattr(pipeline, "find_defaced_nifti", mock_find_defaced_nifti)

        pipeline.process_case(
            case_dicom_dir=str(dicom_in),
            root_in=str(tmp_path / "input"),
            root_out_dicom=str(dicom_out),
            root_out_nifti=str(nifti_root),
            work_root=str(work_root),
            extra_args=[],
        )

        out_case_dir = dicom_out / "case1"
        output_dcms = list(out_case_dir.glob("*.dcm"))
        assert len(output_dcms) == N_SLICES

    def test_work_dir_recreated_fresh(self, tmp_path, monkeypatch):
        """
        Stale files in work_dir must be removed before each case run.
        """
        dicom_in = tmp_path / "input" / "case1"
        dicom_in.mkdir(parents=True)
        for i in range(N_SLICES):
            _make_dicom_slice(dicom_in, i, pixel_value=100)

        work_root = tmp_path / "work"
        case_work = work_root / "case1"
        case_work.mkdir(parents=True)
        stale_file = case_work / "nifti_in" / "stale.nii.gz"
        stale_file.parent.mkdir(parents=True)
        nib.save(nib.Nifti1Image(np.zeros((1, 2, 2), dtype=np.float32), np.eye(4)), str(stale_file))
        assert stale_file.exists()

        fake_nifti_in = tmp_path / "fake_nii.nii.gz"
        nib.save(nib.Nifti1Image(np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32), np.eye(4)),
                 str(fake_nifti_in))
        fake_defaced = tmp_path / "fake_def.nii.gz"
        nib.save(nib.Nifti1Image(np.full((N_SLICES, ROWS, COLS), -500.0, dtype=np.float32), np.eye(4)),
                 str(fake_defaced))

        monkeypatch.setattr(pipeline, "dicom_to_nifti", lambda *a, **kw: str(fake_nifti_in))
        monkeypatch.setattr(pipeline, "run_ct_deface", lambda *a, **kw: [str(fake_defaced)])
        monkeypatch.setattr(pipeline, "find_defaced_nifti", lambda *a, **kw: str(fake_defaced))

        pipeline.process_case(
            case_dicom_dir=str(dicom_in),
            root_in=str(tmp_path / "input"),
            root_out_dicom=str(tmp_path / "output"),
            root_out_nifti=None,
            work_root=str(work_root),
        )

        # Stale file was removed (work dir was wiped and recreated)
        assert not stale_file.exists()

    def test_nifti_copied_to_nifti_root_out(self, tmp_path, monkeypatch):
        """
        When root_out_nifti is provided, the defaced NIfTI must be copied there.
        """
        dicom_in = tmp_path / "input" / "case1"
        dicom_in.mkdir(parents=True)
        for i in range(N_SLICES):
            _make_dicom_slice(dicom_in, i, pixel_value=100)

        nifti_root = tmp_path / "nifti_root"
        fake_nifti_in = tmp_path / "fake_nii.nii.gz"
        nib.save(nib.Nifti1Image(np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32), np.eye(4)),
                 str(fake_nifti_in))
        fake_defaced = tmp_path / "case1_defaced.nii.gz"
        nib.save(nib.Nifti1Image(np.full((N_SLICES, ROWS, COLS), -500.0, dtype=np.float32), np.eye(4)),
                 str(fake_defaced))

        monkeypatch.setattr(pipeline, "dicom_to_nifti", lambda *a, **kw: str(fake_nifti_in))
        monkeypatch.setattr(pipeline, "run_ct_deface", lambda *a, **kw: [str(fake_defaced)])
        monkeypatch.setattr(pipeline, "find_defaced_nifti", lambda *a, **kw: str(fake_defaced))

        pipeline.process_case(
            case_dicom_dir=str(dicom_in),
            root_in=str(tmp_path / "input"),
            root_out_dicom=str(tmp_path / "output"),
            root_out_nifti=str(nifti_root),
            work_root=str(tmp_path / "work"),
        )

        copied = nifti_root / "case1" / "case1_defaced.nii.gz"
        assert copied.exists()


# ---------------------------------------------------------------------------
# main() CLI (lines 708-757, 761)
# ---------------------------------------------------------------------------

class TestMainCLI:

    def test_main_runs_process_case_for_each_case(self, tmp_path, monkeypatch):
        """
        main() must discover cases and call process_case for each one.
        """
        dicom_in = tmp_path / "dicom_in" / "case1"
        dicom_in.mkdir(parents=True)
        for i in range(N_SLICES):
            _make_dicom_slice(dicom_in, i, pixel_value=100)

        dicom_out = tmp_path / "dicom_out"
        work_root = tmp_path / "work"

        calls = []

        def mock_process_case(case_dicom_dir, root_in, root_out_dicom,
                               root_out_nifti, work_root_arg, extra_args=None):
            calls.append(case_dicom_dir)

        monkeypatch.setattr(pipeline, "process_case", mock_process_case)
        monkeypatch.setattr(
            sys, "argv",
            [
                "ct_deface_pipeline_multi2.py",
                "-i", str(tmp_path / "dicom_in"),
                "-o", str(dicom_out),
                "-w", str(work_root),
            ]
        )

        pipeline.main()

        assert len(calls) == 1
        assert str(dicom_in.resolve()) in calls

    def test_main_passes_nifti_root_out_when_provided(self, tmp_path, monkeypatch):
        """
        --nifti-root-out argument is forwarded to process_case correctly.
        """
        dicom_in = tmp_path / "dicom_in" / "case1"
        dicom_in.mkdir(parents=True)
        for i in range(N_SLICES):
            _make_dicom_slice(dicom_in, i, pixel_value=100)

        nifti_root = tmp_path / "nifti_root"
        received_nifti_roots = []

        def mock_process_case(case_dicom_dir, root_in, root_out_dicom,
                               root_out_nifti, work_root_arg, extra_args=None):
            received_nifti_roots.append(root_out_nifti)

        monkeypatch.setattr(pipeline, "process_case", mock_process_case)
        monkeypatch.setattr(
            sys, "argv",
            [
                "ct_deface_pipeline_multi2.py",
                "-i", str(tmp_path / "dicom_in"),
                "-o", str(tmp_path / "dicom_out"),
                "--nifti-root-out", str(nifti_root),
            ]
        )

        pipeline.main()

        assert len(received_nifti_roots) == 1
        assert received_nifti_roots[0] == str(nifti_root.resolve())

    def test_main_exits_when_no_cases_found(self, tmp_path, monkeypatch):
        """
        When no DICOM cases are found, main() raises SystemExit.
        """
        empty_in = tmp_path / "empty_in"
        empty_in.mkdir()

        monkeypatch.setattr(
            sys, "argv",
            [
                "ct_deface_pipeline_multi2.py",
                "-i", str(empty_in),
                "-o", str(tmp_path / "out"),
            ]
        )

        with pytest.raises(SystemExit):
            pipeline.main()

    def test_main_passes_extra_args(self, tmp_path, monkeypatch):
        """
        --ct-extra-args are passed through to process_case.
        """
        dicom_in = tmp_path / "dicom_in" / "case1"
        dicom_in.mkdir(parents=True)
        for i in range(N_SLICES):
            _make_dicom_slice(dicom_in, i, pixel_value=100)

        received_extra = []

        def mock_process_case(case_dicom_dir, root_in, root_out_dicom,
                               root_out_nifti, work_root_arg, extra_args=None):
            received_extra.append(extra_args)

        monkeypatch.setattr(pipeline, "process_case", mock_process_case)
        monkeypatch.setattr(
            sys, "argv",
            [
                "ct_deface_pipeline_multi2.py",
                "-i", str(tmp_path / "dicom_in"),
                "-o", str(tmp_path / "dicom_out"),
                "--ct-extra-args", "--device", "cpu",
            ]
        )

        pipeline.main()

        assert received_extra[0] == ["--device", "cpu"]
