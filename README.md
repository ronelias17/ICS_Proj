# ICS - Ruppin Open Day Assistant

Voice-first Open Day assistant for Ruppin Academic Center. The application combines a React client, FastAPI backend, Neo4j GraphRAG retrieval, MongoDB question records, and local `llama.cpp` models.

## Prerequisites

- Git
- Docker Engine and Docker Compose
- A Linux machine or server is recommended for deployment and required by the included model-download script.
- A public domain is required only when running the optional HTTPS configuration.

## 1. Clone The Repository

Clone the repository into a directory named `app` so the following commands work consistently:

```bash
git clone https://github.com/ronelias17/ICS_Proj.git app
cd app
```

## 2. Configure Environment Values

Create the local environment file:

```bash
cp .env.example .env
```

Open `.env` and replace at least these values:

```text
NEO4J_PASSWORD=CHANGE_ME
MONGO_ROOT_PASSWORD=CHANGE_ME
```

For the HTTPS option, also set the public domain:

```text
DOMAIN=your-domain.example
```

The remaining default addresses are intended for Docker Compose and normally do not need to change.

## 3. Download The Local Models

The script downloads the chat model, MTP draft model, and embedding model into `models/`:

```bash
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```

If a download cannot be completed, use the direct links and expected filenames in [MODEL_DOWNLOADS.md](MODEL_DOWNLOADS.md) to download the files manually into `models/`.

## 4. Start The Application With HTTP

For local use or a private network, start the standard stack:

```bash
docker compose up -d --build
```

The frontend is served by Nginx. Requests under `/api/` are forwarded internally to the FastAPI backend.

## 5. Initialize Data Once

Run these commands after the services are healthy. They are initial setup operations, not commands for every restart.

Populate Neo4j with the graph, indexes, and embeddings:

```bash
docker compose --profile setup run --rm populate-neo4j
```

Insert the suggested questions into MongoDB:

```bash
docker compose exec backend python scripts/inject_seed_suggestions.py
```

## 6. Optional Public HTTPS

Use this option only when the server has a public domain that points to its public IP address. A free DuckDNS subdomain is sufficient.

Set `DOMAIN` in `.env`, then create a Let's Encrypt certificate. Port 80 must be publicly reachable, and no other service may occupy it while Certbot runs.

If Certbot is not installed:

```bash
sudo apt update
sudo apt install certbot
```

Create the certificate:

```bash
sudo certbot certonly --standalone -d your-domain.example
```

If a valid certificate for the same domain already exists on the server, skip the Certbot installation and certificate-creation commands.

Start the HTTPS configuration instead of the standard HTTP command:

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
```

The HTTPS configuration redirects port 80 to HTTPS and serves the application through Nginx on port 443.

## 7. Verify The Application

Open one of the following addresses:

- Same machine: `http://127.0.0.1`
- Another device on the same network: `http://<server-local-ip>`
- Public HTTPS deployment: `https://your-domain.example`

The backend API documentation is available at `/docs`, for example `http://127.0.0.1/docs` or `https://your-domain.example/docs`.

## Stop The Stack

Stop and remove the Compose containers and network:

```bash
docker compose down
```

For more Docker Compose commands, see the [Docker Compose documentation](https://docs.docker.com/compose/).

## Optional NVIDIA GPU Configuration

The default configuration uses CPU inference. On a server with an NVIDIA GPU and Docker GPU support, update both `llama-chat` and `llama-embed` services to use the CUDA image:

```yaml
llama-chat:
  image: ghcr.io/ggml-org/llama.cpp:server-cuda

llama-embed:
  image: ghcr.io/ggml-org/llama.cpp:server-cuda
```

The host still requires compatible NVIDIA drivers and Docker GPU configuration. See the official [llama.cpp Docker documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md) for current GPU options.

## Useful Commands

```bash
# Follow all service logs
docker compose logs -f

# Follow one service
docker compose logs -f backend

# Restart the chat model service
docker compose restart llama-chat
```
