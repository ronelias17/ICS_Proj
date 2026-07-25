# Local Model Downloads

Run the automated Linux download script from the project root:

```bash
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```

The script downloads the required GGUF files into `models/`. The directory is excluded from Git.

## Manual Download Fallback

If the script cannot run, create the `models/` directory and download the following files with the exact output names:

```bash
mkdir -p models

wget -O models/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf \
  "https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF/resolve/main/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf"

wget -O models/gemma-4-E2B-it-Q4_0-MTP.gguf \
  "https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF/resolve/main/MTP/mtp-gemma-4-E2B-it-Q4_0.gguf"

wget -O models/embeddinggemma-300M-Q8_0.gguf \
  "https://huggingface.co/unsloth/embeddinggemma-300m-GGUF/resolve/main/embeddinggemma-300M-Q8_0.gguf"
```

The model file names must match `docker-compose.yml` exactly.
