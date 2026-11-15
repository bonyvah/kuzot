# Deploying Kuzot

One Linux server runs everything in Docker. nginx (the `web` image) is the only
thing exposed: it terminates TLS with a Let's Encrypt certificate, serves the
built frontend and proxies `/api` to FastAPI and `/media` to object storage.

```
internet ──443──▶ web (nginx + frontend) ──▶ api ──▶ postgres, mongodb, redis
                        │                      │
                        └─ /media ─▶ minio     └─▶ rabbitmq ──▶ workers (scraping, browser, embedding), beat
certbot: issues and renews the certificate through web on port 80
```

Every push to `main` runs CI, builds `kuzot-backend` and `kuzot-web` into GHCR
(tagged `latest` and the commit SHA) and rolls the server forward
(`.github/workflows/deploy.yml`).

## What you need

- A server with Ubuntu 22.04 or 24.04, **4 GB RAM** or more (Chromium for the
  browser worker is the hungry part), 2 vCPU, 40 GB disk.
- A domain (or subdomain) with an **A record** pointing at the server.
  Add an AAAA record too if the server has IPv6.
- Ports **80** and **443** open to the internet. Keep SSH (22) open for deploys.
- Accounts: OpenAI API key, Pinecone API key (cloud, not Pinecone Local).
  Optional: Tavily (web search during discovery), Apify (Instagram/Facebook/X).

## One-time server setup

```bash
# Docker Engine + compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER        # log out and back in after this

# firewall: ssh, http, https
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable

# app directory
sudo mkdir -p /opt/kuzot && sudo chown $USER /opt/kuzot
```

Copy `.env.prod.example` from this repo to `/opt/kuzot/.env` and fill it in:

```bash
nano /opt/kuzot/.env
chmod 600 /opt/kuzot/.env
```

- `DOMAIN`: the domain from your A record, e.g. `kuzot.example.com`
- `CERTBOT_EMAIL`: where Let's Encrypt sends expiry warnings
- each `*_PASSWORD`: `openssl rand -hex 24` (hex only, they go into URLs)
- `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`: `openssl rand -hex 32`, two different values
- `OPENAI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`

## GitHub setup

1. Make a deploy key on your machine, not the server:

   ```bash
   ssh-keygen -t ed25519 -f kuzot_deploy -N "" -C "github-deploy"
   ssh-copy-id -i kuzot_deploy.pub <user>@<server>
   ssh-keyscan -t ed25519 <server>
   ```

2. In the repository: **Settings → Secrets and variables → Actions → New repository secret**:

   | Secret | Value |
   |---|---|
   | `VPS_HOST` | server IP or hostname |
   | `VPS_USER` | the ssh user (must be in the `docker` group) |
   | `VPS_SSH_KEY` | contents of `kuzot_deploy` (the private key) |
   | `VPS_KNOWN_HOSTS` | the `ssh-keyscan` output line |

   Then delete the local `kuzot_deploy` files, or keep them somewhere safe.

## First deploy

Push to `main`, or run **Actions → Deploy → Run workflow**. The workflow copies
`docker-compose.prod.yml` to `/opt/kuzot/docker-compose.yml`, pulls the images
and starts everything; database migrations run when the API starts.

Then, once, on the server, create the Pinecone index:

```bash
cd /opt/kuzot
docker compose run --rm api python -m app.embedding.manage init-index
```

The certificate: nginx starts with a temporary self-signed one, certbot gets
the real one within a minute or two, and nginx switches to it by itself
(it checks every 5 minutes). Watch it with `docker compose logs -f certbot web`.

Open `https://<DOMAIN>` and register.

## Day to day

```bash
cd /opt/kuzot
docker compose ps                         # what's running, health
docker compose logs -f api                # or worker_scraping, worker_browser, ...
TAG=<older commit sha> docker compose up -d   # roll back to an earlier build
```

**Backups**: the data lives in Docker volumes (`kuzot-prod_pgdata`,
`kuzot-prod_mongodata`, `kuzot-prod_miniodata`). A nightly dump:

```bash
docker compose exec -T postgres pg_dump -U kuzot kuzot | gzip > pg-$(date +%F).sql.gz
docker compose exec -T mongodb sh -c 'mongodump --archive --gzip -u kuzot -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin' > mongo-$(date +%F).gz
```

Copy those off the server. Pinecone can be rebuilt from Mongo with
`python -m app.embedding.manage reindex`.

## Trying the production setup locally

```bash
cp .env.prod.example /tmp/kuzot-prod.env      # set DOMAIN=localhost, CERTBOT_EMAIL empty, passwords
export ENV_FILE=/tmp/kuzot-prod.env
docker compose -f docker-compose.prod.yml --env-file $ENV_FILE up -d --build
```

It runs as project `kuzot-prod`, beside the dev stack, and needs ports 80
and 443 free. The browser warns about the self-signed certificate.
`docker compose -p kuzot-prod down -v` removes it with its data.
