#!/usr/bin/env bash
# Download the local GGUF models required by docker-compose.yml.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_DIR="${APP_ROOT}/models"

CHAT_MODEL_URL="https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF/resolve/main/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
MTP_MODEL_URL="https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF/resolve/main/MTP/mtp-gemma-4-E2B-it-Q4_0.gguf"
EMBEDDING_MODEL_URL="https://huggingface.co/unsloth/embeddinggemma-300m-GGUF/resolve/main/embeddinggemma-300M-Q8_0.gguf"

mkdir -p "${MODELS_DIR}"

if command -v curl >/dev/null 2>&1; then
    DOWNLOADER="curl"
elif command -v wget >/dev/null 2>&1; then
    DOWNLOADER="wget"
else
    echo "Error: install curl or wget before running this script." >&2
    exit 1
fi

download_model() {
    local url="$1"
    local filename="$2"
    local destination="${MODELS_DIR}/${filename}"
    local partial="${destination}.part"

    if [[ -s "${destination}" ]]; then
        echo "Already present: ${filename}"
        return
    fi

    echo "Downloading: ${filename}"
    if [[ "${DOWNLOADER}" == "curl" ]]; then
        if [[ -f "${partial}" ]]; then
            curl --fail --location --retry 3 --continue-at - --output "${partial}" "${url}"
        else
            curl --fail --location --retry 3 --output "${partial}" "${url}"
        fi
    else
        wget --continue --tries=3 --output-document="${partial}" "${url}"
    fi

    mv "${partial}" "${destination}"
    echo "Saved: ${destination}"
}

download_model "${CHAT_MODEL_URL}" "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"
download_model "${MTP_MODEL_URL}" "gemma-4-E2B-it-Q4_0-MTP.gguf"
download_model "${EMBEDDING_MODEL_URL}" "embeddinggemma-300M-Q8_0.gguf"

echo "Model download complete."
