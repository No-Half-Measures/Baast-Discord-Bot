# Baast

Website, dashboard, and Discord bot for [Baast](https://baast.app), an event
scheduling and sign-up bot for Discord communities.

The project is a single Django codebase in `baast/` that runs as two processes:

- **Web.** `bot.cli.run_http` serves the public site, Discord OAuth login, the
  server dashboard, and Stripe billing through uvicorn on port 8000.
- **Bot.** `bot.cli.run_workers` runs the Discord bot as a Django Channels
  worker. The bot uses [hikari](https://github.com/hikari-py/hikari) and
  [lightbulb](https://github.com/tandemdude/hikari-lightbulb).

Both use PostgreSQL for data and Redis for caching and the channel layer. They
can also sync events to Google Calendar and Google Sheets.

## Requirements

- Docker with Docker Compose
- A Discord application with a bot user, created in the
  [developer portal](https://discord.com/developers/applications)
- A Stripe account in test mode, for billing
- A Google Cloud service account, only if you want Calendar and Sheets sync

## Setup

1. **Create the environment file.**

   ```sh
   cd baast
   cp .env.example .env
   ```

   Fill in `baast/.env`. The table below explains each value. `.env` is
   gitignored; never commit it.

2. **Configure Discord.** In the developer portal, copy the application's client
   ID and client secret, and the bot token, into `.env`. Under OAuth2, add the
   redirect URL `http://localhost/login/redirect`, which is the one used when
   `ENVIRONMENT=local`.

3. **Set the Redis password.** `baast/docker-compose.yaml` passes `--requirepass`
   to Redis. Replace `PASSWORD_HERE` with the same value as `REDIS_PASSWORD` in
   `.env`.

4. **Create the Docker network and start PostgreSQL.** The database runs from a
   separate compose file on a shared external network. Replace `USER_HERE` and
   `PASSWORD_HERE` in `baast/postgres-docker-compose.yaml` with your
   `DB_USER`/`DB_PASSWORD`, then run:

   ```sh
   docker network create baast-network
   docker compose -f postgres-docker-compose.yaml up -d db
   ```

   Containers reach the database at `DB_HOST=db` and `DB_PORT=5432`. The host
   machine reaches it at `127.0.0.1:5332`.

5. **Switch nginx to local mode.** `baast/docker-compose.yaml` mounts the
   production nginx config by default. For local development, comment out the
   lines marked `##LIVE` in the `nginx` service and uncomment the ones marked
   `##LOCAL`.

6. **Start the stack.**

   ```sh
   docker compose up --build -d
   ```

   The web container runs `collectstatic` and `migrate` on startup. The site is
   then available at <http://localhost>.

7. **Create an admin user.** This step is optional.

   ```sh
   docker compose exec baast-web python manage.py createsuperuser
   ```

The compose file also starts a monitoring stack with Prometheus, Grafana, Loki,
Alloy, and exporters. Set a Grafana admin password before you expose it
anywhere.

## Environment variables

`baast/baast/settings.py` reads all of these.

| Variable | Description |
| --- | --- |
| `ENVIRONMENT` | `local` for development. Any other value uses production URLs and settings. |
| `TESTING` | `True` selects the Stripe `*_TEST` keys; `False` selects the `*_LIVE` keys. |
| `DEBUG` | Django debug mode. Must be `False` in production. |
| `SECRET_KEY` | Django secret key. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"`. |
| `ALLOWED_HOSTS` | Comma-separated hostnames Django will serve. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection. |
| `REDIS_PASSWORD`, `REDIS_HOST`, `REDIS_PORT` | Redis connection. |
| `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` | Discord OAuth2 application credentials. |
| `DISCORD_TOKEN` | Discord bot token. |
| `STRIPE_PUBLISHABLE_KEY_TEST`, `STRIPE_SECRET_KEY_TEST`, `STRIPE_ENDPOINT_SECRET_TEST` | Stripe test-mode keys and webhook signing secret. |
| `STRIPE_PUBLISHABLE_KEY_LIVE`, `STRIPE_SECRET_KEY_LIVE`, `STRIPE_ENDPOINT_SECRET_LIVE` | Stripe live-mode keys, used when `TESTING=False`. |
| `STRIPE_PRODUCT_ID_*`, `STRIPE_PRICE_ID_*` | Stripe product and price IDs for the subscription plans. |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to the Google service account JSON key file. Keep the file out of git. |
| `HASH_SALT` | Salt for the hashids used in public IDs. Use a random value and keep it secret. |

For Stripe webhooks during local development, forward events with the
[Stripe CLI](https://docs.stripe.com/stripe-cli):

```sh
stripe listen --forward-to localhost/stripe/webhook/
```

Put the signing secret it prints into `STRIPE_ENDPOINT_SECRET_TEST`.

## Project layout

```
baast/
├── app/          # Core models (events, configs, presets), public pages, Stripe
├── bot/          # Discord bot: commands, listeners, tasks, components
├── cache/        # Cached Discord guilds, channels, and roles
├── discord/      # Discord OAuth, dashboard pages, and AJAX endpoints
├── baast/        # Django project settings, URLs, ASGI
├── grafana/      # Grafana dashboards and provisioning
└── docker-compose.yaml
```

## Deployment

Pushes to `main` that touch `baast/` trigger `.github/workflows/deploy.yml`. The
workflow copies the code to the server over SSH and runs `deploy.sh`. It needs
these repository secrets: `SERVER_USER`, `SERVER_HOST`, `SERVER_PORT`,
`PROJECT_PATH`, and `SERVER_SSH_KEY`. `baast/init-letsencrypt.sh` issues the
production TLS certificates.

## License

See [LICENSE.md](LICENSE.md).
