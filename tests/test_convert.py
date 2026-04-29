"""
Tests for functions shared between run_CT-DEFACE.py and ct_deface_convert.py:
  - ensure_nnunet_naming()       (run_CT-DEFACE.py)
  - create_defaced_image()       (run_CT-DEFACE.py)
  - sorted_dicom_files()         (ct_deface_convert.py)
  - dicom_to_nifti()             (ct_deface_convert.py)
  - run_ct_deface() / nifti_to_dicom() via CLI (ct_deface_convert.py)
"""

import os
import sys
import subprocess
import pytest
import numpy as np
import nibabel as nib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import run_CT_DEFACE as run_deface
import ct_deface_convert as convert
from conftest import N_SLICES, ROWS, COLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_nifti(path: Path, value: float = 0.0, shape=None) -> Path:
    if shape is None:
        shape = (N_SLICES, ROWS, COLS)
    data = np.full(shape, value, dtype=np.float32)
    nib.save(nib.Nifti1Image(data, np.eye(4)), str(path))
    return path


# ---------------------------------------------------------------------------
# ensure_nnunet_naming
# ---------------------------------------------------------------------------

class TestEnsureNnunetNaming:
    def test_already_named_file_is_untouched(self, tmp_path):
        """Files already ending with _0000.nii.gz must not be renamed."""
        existing = tmp_path / "case_0000.nii.gz"
        _make_nifti(existing)
        run_deface.ensure_nnunet_naming(str(tmp_path))
        files = list(tmp_path.glob("*.nii.gz"))
        assert len(files) == 1
        assert files[0].name == "case_0000.nii.gz"

    def test_creates_symlink_for_non_nnunet_file(self, tmp_path):
        """A file without _0000 suffix gets a symlink with the correct name."""
        src = tmp_path / "CT.nii.gz"
        _make_nifti(src)
        run_deface.ensure_nnunet_naming(str(tmp_path), copy=False)
        expected = tmp_path / "CT_0000.nii.gz"
        assert expected.exists()
        assert expected.is_symlink()

    def test_creates_copy_when_copy_flag_set(self, tmp_path):
        """copy=True should create a real file, not a symlink."""
        src = tmp_path / "CT.nii.gz"
        _make_nifti(src)
        run_deface.ensure_nnunet_naming(str(tmp_path), copy=True)
        expected = tmp_path / "CT_0000.nii.gz"
        assert expected.exists()
        assert not expected.is_symlink()

    def test_does_not_overwrite_existing_nnunet_file(self, tmp_path):
        """If the target already exists, do not overwrite it."""
        src = tmp_path / "CT.nii.gz"
        _make_nifti(src, value=1.0)
        existing_target = tmp_path / "CT_0000.nii.gz"
        _make_nifti(existing_target, value=2.0)

        run_deface.ensure_nnunet_naming(str(tmp_path), copy=True)

        # Target should still have value=2 (not overwritten)
        nii = nib.load(str(existing_target))
        assert float(nii.get_fdata()[0, 0, 0]) == pytest.approx(2.0)

    def test_multiple_non_nnunet_files(self, tmp_path):
        """All non-compliant files in the directory are renamed."""
        for name in ["a.nii.gz", "b.nii.gz", "c.nii.gz"]:
            _make_nifti(tmp_path / name)
        run_deface.ensure_nnunet_naming(str(tmp_path), copy=True)
        for name in ["a_0000.nii.gz", "b_0000.nii.gz", "c_0000.nii.gz"]:
            assert (tmp_path / name).exists()

    def test_empty_directory_does_not_raise(self, tmp_path):
        """Calling on an empty directory must not raise."""
        run_deface.ensure_nnunet_naming(str(tmp_path))


# ---------------------------------------------------------------------------
# create_defaced_image
# ---------------------------------------------------------------------------

class TestCreateDefacedImage:
    def test_defaced_output_exists(self, tmp_path):
        image_path = tmp_path / "image.nii.gz"
        _make_nifti(image_path, value=0.0)

        mask = np.zeros((N_SLICES, ROWS, COLS), dtype=np.uint8)
        mask[0, 10:20, 10:20] = 1  # small region masked

        output_path = tmp_path / "defaced.nii.gz"
        run_deface.create_defaced_image(str(image_path), mask, str(output_path))

        assert output_path.exists()

    def test_defaced_pixels_differ_from_original(self, tmp_path):
        """Masked voxels must be modified in the output.

        create_defaced_image() fills masked voxels with the 1st percentile of
        the original image. We use a bimodal volume: most voxels are at 500 HU
        (tissue), a small patch is at -1000 HU (air). The 1st percentile then
        resolves to -1000, which is clearly distinct from 500. The mask covers
        the tissue region, so the output there must differ from 500.
        """
        image_path = tmp_path / "image.nii.gz"
        data = np.ones((N_SLICES, ROWS, COLS), dtype=np.float32) * 500.0
        # Air patch must cover > 1% of voxels so the 1st percentile resolves
        # to -1000 rather than 500. 5*8*8 = 320 voxels = 1.56% of 20480.
        data[:, 0:8, 0:8] = -1000.0
        nib.save(nib.Nifti1Image(data, np.eye(4)), str(image_path))

        # Mask covers the tissue region of the first slice (not the air patch)
        mask = np.zeros((N_SLICES, ROWS, COLS), dtype=np.uint8)
        mask[0, 10:20, 10:20] = 1

        output_path = tmp_path / "defaced.nii.gz"
        run_deface.create_defaced_image(str(image_path), mask, str(output_path))

        nii_out = nib.load(str(output_path))
        arr_out = nii_out.get_fdata()

        # The fill value is ~-1000 (1st percentile), not 500 — masked patch must change
        assert not np.all(arr_out[0, 10:20, 10:20] == 500.0)

    def test_unmasked_pixels_unchanged(self, tmp_path):
        """Voxels outside the mask must retain their original values."""
        image_path = tmp_path / "image.nii.gz"
        # Use a value far from the 1st percentile fill value
        data = np.full((N_SLICES, ROWS, COLS), 200.0, dtype=np.float32)
        nib.save(nib.Nifti1Image(data, np.eye(4)), str(image_path))

        # Zero mask = nothing masked
        mask = np.zeros((N_SLICES, ROWS, COLS), dtype=np.uint8)
        output_path = tmp_path / "defaced.nii.gz"
        run_deface.create_defaced_image(str(image_path), mask, str(output_path))

        nii_out = nib.load(str(output_path))
        arr_out = nii_out.get_fdata()
        np.testing.assert_array_almost_equal(arr_out, data)

    def test_output_has_same_shape_as_input(self, tmp_path):
        image_path = tmp_path / "image.nii.gz"
        _make_nifti(image_path, value=0.0)
        mask = np.ones((N_SLICES, ROWS, COLS), dtype=np.uint8)
        output_path = tmp_path / "defaced.nii.gz"
        run_deface.create_defaced_image(str(image_path), mask, str(output_path))

        nii_out = nib.load(str(output_path))
        assert nii_out.shape == (N_SLICES, ROWS, COLS)


# ---------------------------------------------------------------------------
# sorted_dicom_files (ct_deface_convert)
# ---------------------------------------------------------------------------

class TestSortedDicomFiles:
    def test_returns_files_sorted_by_instance_number(self, synthetic_dicom_dir):
        files = convert.sorted_dicom_files(str(synthetic_dicom_dir))
        import pydicom
        instance_numbers = [
            int(pydicom.dcmread(f, stop_before_pixels=True).InstanceNumber)
            for f in files
        ]
        assert instance_numbers == sorted(instance_numbers)

    def test_raises_on_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(RuntimeError, match="No readable DICOM files"):
            convert.sorted_dicom_files(str(empty))

    def test_correct_number_of_files_returned(self, synthetic_dicom_dir):
        """
        sorted_dicom_files() collects via glob('*.dcm') then glob('*'), with
        no deduplication before sorting. Files with a .dcm extension are
        therefore matched by both patterns, so the raw list contains duplicates.
        The function sorts this de-duplicated-by-Dataset list, meaning each
        unique (filepath, ds) pair still appears. In practice the sorted output
        contains at least N_SLICES entries. We assert uniqueness of the returned
        paths and that the unique count equals N_SLICES.
        """
        files = convert.sorted_dicom_files(str(synthetic_dicom_dir))
        unique_files = list(dict.fromkeys(files))  # preserve order, drop dups
        assert len(unique_files) == N_SLICES


# ---------------------------------------------------------------------------
# dicom_to_nifti (ct_deface_convert) — SimpleITK path (lines 73-107)
# ---------------------------------------------------------------------------

class TestConvertDicomToNifti:

    def test_writes_nnunet_named_nifti_in_directory(self, tmp_path, monkeypatch):
        """
        When output_path is a directory, dicom_to_nifti writes
        <series_id>_0000.nii.gz there (nnunet_style=True).
        """
        import SimpleITK as sitk

        fake_series_id = "1.2.3.99"
        expected_name = f"{fake_series_id}_0000.nii.gz"

        class FakeReader:
            def GetGDCMSeriesIDs(self, path):
                return [fake_series_id]
            def GetGDCMSeriesFileNames(self, path, sid):
                return []
            def SetFileNames(self, fnames):
                pass
            def Execute(self):
                arr = np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32)
                return sitk.GetImageFromArray(arr)

        monkeypatch.setattr(sitk, "ImageSeriesReader", FakeReader)

        out_dir = str(tmp_path / "nifti_out") + os.sep  # ends with sep -> dir
        result = convert.dicom_to_nifti(str(tmp_path / "dicom"), out_dir)

        assert Path(result).name == expected_name
        assert Path(result).exists()

    def test_writes_to_explicit_file_path_non_nnunet(self, tmp_path, monkeypatch):
        """
        When output_path is an explicit .nii.gz file path and
        nnunet_style=False, write exactly to that path.
        """
        import SimpleITK as sitk

        class FakeReader:
            def GetGDCMSeriesIDs(self, path):
                return ["1.2.3.100"]
            def GetGDCMSeriesFileNames(self, path, sid):
                return []
            def SetFileNames(self, fnames):
                pass
            def Execute(self):
                arr = np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32)
                return sitk.GetImageFromArray(arr)

        monkeypatch.setattr(sitk, "ImageSeriesReader", FakeReader)

        out_file = str(tmp_path / "my_output.nii.gz")
        result = convert.dicom_to_nifti(str(tmp_path / "dicom"), out_file, nnunet_style=False)

        assert result == out_file
        assert Path(result).exists()

    def test_appends_0000_suffix_for_nnunet_style_explicit_path(self, tmp_path, monkeypatch):
        """
        When output_path is an explicit file that doesn't end with _0000.nii.gz
        and nnunet_style=True, the suffix is appended.
        """
        import SimpleITK as sitk

        class FakeReader:
            def GetGDCMSeriesIDs(self, path):
                return ["1.2.3.101"]
            def GetGDCMSeriesFileNames(self, path, sid):
                return []
            def SetFileNames(self, fnames):
                pass
            def Execute(self):
                arr = np.zeros((N_SLICES, ROWS, COLS), dtype=np.float32)
                return sitk.GetImageFromArray(arr)

        monkeypatch.setattr(sitk, "ImageSeriesReader", FakeReader)

        out_file = str(tmp_path / "my_ct.nii.gz")
        result = convert.dicom_to_nifti(str(tmp_path / "dicom"), out_file, nnunet_style=True)

        assert result.endswith("_0000.nii.gz")
        assert Path(result).exists()

    def test_raises_when_no_series_found(self, tmp_path, monkeypatch):
        """
        Empty series ID list -> RuntimeError with 'No DICOM series found'.
        """
        import SimpleITK as sitk

        class FakeReaderEmpty:
            def GetGDCMSeriesIDs(self, path):
                return []

        monkeypatch.setattr(sitk, "ImageSeriesReader", FakeReaderEmpty)

        with pytest.raises(RuntimeError, match="No DICOM series found"):
            convert.dicom_to_nifti(str(tmp_path / "dicom"), str(tmp_path / "out"))

    def test_warns_on_multiple_series(self, tmp_path, monkeypatch, capsys):
        """
        Multiple series IDs -> WARNING printed, still uses first series.
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

        result = convert.dicom_to_nifti(str(tmp_path / "dicom"),
                                        str(tmp_path / "out") + os.sep)
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert Path(result).exists()


# ---------------------------------------------------------------------------
# nifti_to_dicom (ct_deface_convert) — roundtrip (lines 115-211)
# ---------------------------------------------------------------------------

class TestConvertNiftiToDicom:
    """
    ct_deface_convert.sorted_dicom_files() globs both '*.dcm' and '*' without
    deduplication, so for a directory of N_SLICES .dcm files it returns
    N_SLICES * 2 entries (each file appears once in each glob pass).
    nifti_to_dicom() uses that count as n_slices_ref, so tests must supply
    NIfTI volumes whose slice-dimension matches 2 * N_SLICES.
    """
    # Number of reference "slices" as seen by nifti_to_dicom (double-glob)
    REF_COUNT = N_SLICES * 2

    def test_writes_one_dicom_per_reference_slice(self, tmp_path, synthetic_dicom_dir):
        """
        nifti_to_dicom writes exactly REF_COUNT DICOM files (one per entry
        in sorted_dicom_files, which includes both glob passes).
        """
        data = np.full((self.REF_COUNT, ROWS, COLS), -500.0, dtype=np.float32)
        nii_path = tmp_path / "defaced.nii.gz"
        nib.save(nib.Nifti1Image(data, np.eye(4)), str(nii_path))

        out_dir = tmp_path / "dicom_out"
        convert.nifti_to_dicom(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        output_dcms = list(out_dir.glob("*.dcm"))
        assert len(output_dcms) == self.REF_COUNT

    def test_new_series_uid_differs_from_reference(self, tmp_path, synthetic_dicom_dir):
        """
        nifti_to_dicom generates a new SeriesInstanceUID.
        """
        from conftest import SERIES_UID
        import pydicom

        data = np.full((self.REF_COUNT, ROWS, COLS), -500.0, dtype=np.float32)
        nii_path = tmp_path / "defaced.nii.gz"
        nib.save(nib.Nifti1Image(data, np.eye(4)), str(nii_path))

        out_dir = tmp_path / "dicom_out"
        convert.nifti_to_dicom(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        out_files = sorted(out_dir.glob("*.dcm"))
        ds = pydicom.dcmread(str(out_files[0]), stop_before_pixels=True)
        assert str(ds.SeriesInstanceUID) != SERIES_UID

    def test_raises_on_incompatible_shape(self, tmp_path, synthetic_dicom_dir):
        """
        NIfTI shape incompatible with reference slice count raises RuntimeError.
        dim0=3 and dim2=COLS=64 — neither equals REF_COUNT (10).
        """
        data = np.full((3, ROWS, COLS), 0.0, dtype=np.float32)
        nii_path = tmp_path / "wrong.nii.gz"
        nib.save(nib.Nifti1Image(data, np.eye(4)), str(nii_path))

        out_dir = tmp_path / "dicom_out"
        with pytest.raises(RuntimeError, match="not compatible"):
            convert.nifti_to_dicom(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

    def test_accepts_dim2_slices_ordering(self, tmp_path, synthetic_dicom_dir):
        """
        NIfTI with shape (ROWS, COLS, REF_COUNT): dim2 == REF_COUNT path.
        """
        data = np.full((ROWS, COLS, self.REF_COUNT), -500.0, dtype=np.float32)
        nii_path = tmp_path / "dim2.nii.gz"
        nib.save(nib.Nifti1Image(data, np.eye(4)), str(nii_path))

        out_dir = tmp_path / "dicom_out"
        convert.nifti_to_dicom(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

        assert len(list(out_dir.glob("*.dcm"))) == self.REF_COUNT

    def test_raises_on_non_3d_nifti(self, tmp_path, synthetic_dicom_dir):
        """
        A 2D NIfTI (shape ROWS x COLS) must raise RuntimeError (line 163:
        'Only 3D NIfTI volumes are supported for now.').
        """
        data_2d = np.zeros((ROWS, COLS), dtype=np.float32)
        nii_path = tmp_path / "flat.nii.gz"
        nib.save(nib.Nifti1Image(data_2d, np.eye(4)), str(nii_path))

        out_dir = tmp_path / "dicom_out"
        with pytest.raises(RuntimeError, match="Only 3D"):
            convert.nifti_to_dicom(str(nii_path), str(synthetic_dicom_dir), str(out_dir))

    def test_raises_on_slice_shape_mismatch(self, tmp_path, synthetic_dicom_dir):
        """
        When a NIfTI slice shape doesn't match the DICOM Rows x Columns,
        RuntimeError is raised (line 199: 'does not match DICOM').
        REF_COUNT slices are needed, but with wrong in-plane size.
        """
        wrong_rows = ROWS + 5
        data = np.full((self.REF_COUNT, wrong_rows, COLS), -500.0, dtype=np.float32)
        nii_path = tmp_path / "wrong.nii.gz"
        nib.save(nib.Nifti1Image(data, np.eye(4)), str(nii_path))

        out_dir = tmp_path / "dicom_out"
        with pytest.raises(RuntimeError, match="does not match DICOM"):
            convert.nifti_to_dicom(str(nii_path), str(synthetic_dicom_dir), str(out_dir))


# ---------------------------------------------------------------------------
# ct_deface_convert main() CLI (lines 219-277)
# ---------------------------------------------------------------------------

class TestConvertMainCLI:

    def test_dicom2nii_subcommand_calls_dicom_to_nifti(self, tmp_path, monkeypatch):
        """
        'dicom2nii' subcommand delegates to dicom_to_nifti() correctly.
        """
        calls = {}

        def mock_dicom_to_nifti(input_dir, output, nnunet_style=True):
            calls["input"] = input_dir
            calls["output"] = output
            calls["nnunet_style"] = nnunet_style

        monkeypatch.setattr(convert, "dicom_to_nifti", mock_dicom_to_nifti)
        monkeypatch.setattr(
            sys, "argv",
            ["ct_deface_convert.py", "dicom2nii", "-i", "/fake/dicom", "-o", "/fake/out"]
        )

        ret = convert.main()
        assert ret == 0
        assert calls["input"] == "/fake/dicom"
        assert calls["nnunet_style"] is True

    def test_dicom2nii_no_nnunet_style_flag(self, tmp_path, monkeypatch):
        """
        --no-nnunet-style sets nnunet_style=False.
        """
        calls = {}

        def mock_dicom_to_nifti(input_dir, output, nnunet_style=True):
            calls["nnunet_style"] = nnunet_style

        monkeypatch.setattr(convert, "dicom_to_nifti", mock_dicom_to_nifti)
        monkeypatch.setattr(
            sys, "argv",
            ["ct_deface_convert.py", "dicom2nii",
             "-i", "/fake/dicom", "-o", "/fake/out", "--no-nnunet-style"]
        )

        convert.main()
        assert calls["nnunet_style"] is False

    def test_nii2dicom_subcommand_calls_nifti_to_dicom(self, tmp_path, monkeypatch):
        """
        'nii2dicom' subcommand delegates to nifti_to_dicom() correctly.
        """
        calls = {}

        def mock_nifti_to_dicom(nifti_file, ref_dicom_dir, output_dir):
            calls["nifti"] = nifti_file
            calls["ref"] = ref_dicom_dir
            calls["output"] = output_dir

        monkeypatch.setattr(convert, "nifti_to_dicom", mock_nifti_to_dicom)
        monkeypatch.setattr(
            sys, "argv",
            [
                "ct_deface_convert.py", "nii2dicom",
                "-n", "/fake/defaced.nii.gz",
                "-r", "/fake/ref_dicom",
                "-o", "/fake/out",
            ]
        )

        ret = convert.main()
        assert ret == 0
        assert calls["nifti"] == "/fake/defaced.nii.gz"
        assert calls["ref"] == "/fake/ref_dicom"
