#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=${VENV_DIR:-.venv_ct_deface}

# Activate venv
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

# Force CPU
export CUDA_VISIBLE_DEVICES=""

# Pass all args through to the original script
python run_CT-DEFACE.py "$@"

