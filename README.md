# OfferOps

OfferOps is a Python CLI for provisioning offer-site infrastructure from a CSV import. It wires together Cloudflare and WHM/cPanel so you can stand up domains with repeatable profiles instead of doing the same setup by hand every day.

## What It Does

For each domain row, OfferOps can:

1. Read the domain and selected profile from CSV.
2. Create or reuse the Cloudflare zone.
3. Prepare the nameserver step for manual update in the registrar.
4. Apply profile-specific DNS records.
5. Create or reuse a cPanel account through WHM.
6. Create a `support@domain` mailbox.
7. Pull SPF, DKIM, and DMARC-style deliverability records from cPanel and publish them in Cloudflare.
8. Upload starter files such as `robots.txt` and `info.php`.
9. Create a MySQL database, user, and grants.
10. Register the offer cron job.
11. Save run state locally for auditing and retries.

## Project Layout

- `offerops/`: application code, CLI entrypoint, providers, state management, and web dashboard.
- `data/domains.csv`: sample input file for domain imports.
- `config.example.json`: example profile and DNS configuration.
- `.env.example`: example environment variables for tokens and account credentials.
- `tests/`: unit tests.

## Quick Start

Create a virtual environment and install the package:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Then review `config.example.json` and update profile values such as:

- server IPs
- document-root template
- cron command template
- DNS record sets
- profile names and mappings

Run a dry run first:

```powershell
python -m offerops.cli run --csv data/domains.csv --dry-run
```

Run the actual provisioning after secrets are configured:

```powershell
python -m offerops.cli run --csv data/domains.csv
```

Start the local dashboard:

```powershell
python -m offerops.cli web --port 8787
```

Open `http://127.0.0.1:8787` in your browser.

## CSV Format

The CSV should include these columns:

```csv
domain,profile,offer_path,notes
example-offer.com,ecom-live,https://www.example-offer.com/v1/msrack,
example-sweeps.com,sweeps-live,https://www.example-sweeps.com/v1/msrack,
```

Notes:

- `profile` must match a profile key in `config.example.json`.
- `offer_path` can be a full URL or a path like `v1/msrack`.
- The cron template uses the normalized offer path during provisioning.

## Profiles

The included sample configuration shows four profile shapes:

- `ecom-live`
- `ecom-bkp`
- `sweeps-live`
- `sweeps-bkp`

Profiles control which Cloudflare account, WHM account, DNS record template, and cron settings get used. Placeholder values such as `{domain}` and `{offer_path}` are expanded at runtime.

## Environment Variables

Keep real credentials only in `.env`, never in tracked files.

Key groups used by the app:

- Cloudflare settings: `CLOUDFLARE_SWEEPS_API_TOKEN`, `CLOUDFLARE_SWEEPS_ACCOUNT_ID`, `CLOUDFLARE_ECOM_API_TOKEN`, `CLOUDFLARE_ECOM_ACCOUNT_ID`
- WHM settings: base URL, username, API token, package, and contact email for each live/backup environment
- Local paths: `OFFEROPS_CONFIG` and `OFFEROPS_STATE`

Use WHM API tokens with only the permissions you need, such as `create-acct`, `list-accts`, and `cpanel-api`.

## Safe GitHub Publishing

This repository is set up so these local-only files stay out of Git:

- `.env` and other `.env.*` files except `.env.example`
- `state/` runtime state and generated credentials
- `logs/`
- `.tmp/`
- local build artifacts such as `*.egg-info/`, `build/`, and `dist/`

Before pushing to GitHub:

1. Double-check that `.env` contains your real secrets and remains untracked.
2. Keep `.env.example` as the public template with blank tokens.
3. Review `git status` to confirm no runtime state or credentials are staged.

Important: because your current `.env` contains what look like real WHM details and an API token, rotate that token if it has ever been shared, copied, or committed anywhere else before today, May 9, 2026.

## Running Tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```
