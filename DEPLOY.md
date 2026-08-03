# Production Docker Deployment

## Architecture

- `frontend`: nginx serves the compiled Vue app and reverse proxies `/api` to `backend:8000`.
- `backend`: FastAPI + Uvicorn.
- `mysql`: MySQL 8.4 with host data directory `/opt/nit-ao/mysql`.
- `redis`: Redis 7.4 with host data directory `/opt/nit-ao/redis`.
- `backend` storage: generated documents and uploaded files in `/opt/nit-ao/storage`.
- Runtime config: `/opt/nit-ao/config/app.env`.

The browser only talks to nginx, so frontend and backend are same-origin in production. CORS is kept for direct debugging but is not required for normal use.

## First Deploy

1. Prepare host directories:

```bash
sudo mkdir -p /opt/nit-ao/{config,mysql,redis,storage,refer}
sudo chown -R "$USER":"$USER" /opt/nit-ao
cp -r refer/* /opt/nit-ao/refer/
```

2. Prepare environment values:

```bash
cp .env.production.example /opt/nit-ao/config/app.env
```

Edit `/opt/nit-ao/config/app.env` and change at least:

- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `SECRET_KEY`
- `APP_ADMIN_EMAIL`
- `APP_ADMIN_PASSWORD`
- `FRONTEND_URL`
- `BACKEND_CORS_ORIGINS`
- `OPENAI_API_KEY` if AI parsing is enabled

`FRONTEND_URL` and `BACKEND_CORS_ORIGINS` must be the address opened by the user's browser, not Docker's internal service name.

Examples:

```bash
# Direct HTTP access by server IP
FRONTEND_URL=http://203.0.113.10
BACKEND_CORS_ORIGINS=http://203.0.113.10

# Production domain through HTTPS
FRONTEND_URL=https://oa.example.com
BACKEND_CORS_ORIGINS=https://oa.example.com

# Allow both while testing
FRONTEND_URL=https://oa.example.com
BACKEND_CORS_ORIGINS=https://oa.example.com,http://203.0.113.10
```

Docker internal names such as `backend:8000`, `mysql:3306`, and `redis:6379` are used only by containers to talk to each other.
The browser does not know those names. In this compose file, nginx proxies `/api` to `backend:8000` internally, while users access only the frontend URL.

OpenAI settings:

```bash
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.5
```

Dify AI assistant settings:

```bash
DIFY_ASSISTANT_ENABLED=true
# This can be a Dify API base, a full /v1/chat-messages endpoint, or the console develop URL.
DIFY_ASSISTANT_API_BASE=https://dify.example.com/app/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/develop
DIFY_ASSISTANT_API_KEY=app-...
DIFY_ASSISTANT_APP_URL=https://dify.example.com/app/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/develop
DIFY_ASSISTANT_TITLE=NIT AI Help Desk
DIFY_ASSISTANT_GREETING=会社情報や社内手続きについて質問できます。
DIFY_ASSISTANT_DEFAULT_INPUTS={}
DIFY_ASSISTANT_RESPONSE_MODE=blocking
DIFY_ASSISTANT_TIMEOUT_SECONDS=60
```

If the backend runs in Docker and Dify runs on the host, `localhost` points to the backend container itself. Use a reachable host name such as `host.docker.internal`, a Dify container service name, or the public Dify domain.

File storage in the current v0.8 image is local persistent storage:

```bash
NIT_OA_ROOT=/opt/nit-ao
# uploaded files and generated documents are stored at /opt/nit-ao/storage
```

S3 settings are reserved in `app.env` for the later storage backend switch. The current image does not upload to or read from S3 yet:

```bash
STORAGE_BACKEND=local
AWS_REGION=ap-northeast-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=
S3_PREFIX=nit-oa
S3_ENDPOINT_URL=
```

3. Build images locally:

```bash
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml build
```

4. Start all services:

```bash
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml up -d
```

5. Check status:

```bash
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml ps
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml logs -f backend
```

6. Open:

```text
http://your-server/
```

## Upgrade

```bash
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml build
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml up -d
```

## Deploy With ECR Images

After pushing images to ECR, set these in `/opt/nit-ao/config/app.env`:

```bash
BACKEND_IMAGE=123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/japan-nit-oa-backend
FRONTEND_IMAGE=123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/japan-nit-oa-frontend
APP_VERSION=0.8
BACKEND_IMAGE_TAG=0.8
FRONTEND_IMAGE_TAG=0.8
```

If both images are stored in the same ECR repository, use different tags:

```bash
BACKEND_IMAGE=123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/nit/nit-ao
FRONTEND_IMAGE=123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/nit/nit-ao
BACKEND_IMAGE_TAG=backend-0.8
FRONTEND_IMAGE_TAG=frontend-0.8
```

Then run:

```bash
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml pull
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml up -d --no-build
```

## Stop

```bash
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml down
```

This keeps host data directories under `/opt/nit-ao`.

## Notes

- Public port is controlled by `HTTP_PORT` in `/opt/nit-ao/config/app.env`; default is `80`.
- Database and Redis are not exposed to the host in `docker-compose.prod.yml`.
- Fixed contract files are read from `/opt/nit-ao/refer` and mounted read-only into the backend container.
- Uploaded files and generated documents are stored in `/opt/nit-ao/storage`.
- Changing `/opt/nit-ao/config/app.env` requires a container restart, not an image rebuild:

```bash
docker compose --env-file /opt/nit-ao/config/app.env -f docker-compose.prod.yml up -d --force-recreate backend frontend
```

- If deploying behind an external TLS reverse proxy, set `FRONTEND_URL` and `BACKEND_CORS_ORIGINS` to the HTTPS domain.
