# OfferOps

> Provision domains, DNS, hosting, email, databases, and scheduled tasks from one reliable workflow.

OfferOps helps teams launch offer-site infrastructure with repeatable profiles and a guided dashboard. It coordinates DNS, hosting, email, database setup, registrar nameservers, and credentials so each domain follows the same dependable process.

---

## Dashboard Preview

A focused operations dashboard for preparing domains, tracking live progress, and reviewing completed runs.

### OfferOps Dashboard

![OfferOps Dashboard](screenshots/Offerops_dashboard_1.png)

### Provisioning Workflow

![OfferOps Provisioning Workflow](screenshots/Offerops_dashboard_2.png)

The dashboard supports:

* Provision one or many domains at once
* Select the target environment for each run
* Add offer paths directly in the workflow
* Monitor infrastructure tasks in real time
* Review recent provisioning runs
* Open saved credentials when needed

---

## Why OfferOps?

Provisioning offer infrastructure usually spans several systems:

* Cloudflare
* WHM/cPanel
* Domain registrars
* DNS management
* Email configuration
* Database creation
* Cron scheduling

OfferOps turns that work into a repeatable workflow that reduces missed steps, keeps results easy to review, and gives every domain the same deployment path.

---

## Features

### Cloudflare Automation

* Create or reuse Cloudflare zones
* Publish SPF, DKIM, and DMARC records
* Enable Bot Fight Mode
* Manage DNS records from predefined templates

### Hosting Automation

* Create or reuse cPanel accounts
* Create support mailboxes
* Upload starter application files
* Configure document roots

### Database Provisioning

* Create MySQL databases
* Create database users
* Assign permissions automatically

### Registrar Integration

* Update nameservers through Orange when automation is enabled
* Support manual registrar workflows when automation is disabled

### Operations Dashboard

* Launch guided dashboard runs
* Live provisioning status updates
* Historical run tracking
* Saved run results and credentials for later review

---

## What Happens During Provisioning?

For every domain submitted, OfferOps can:

1. Create or reuse the Cloudflare zone
2. Configure nameservers
3. Create or reuse the cPanel account
4. Create the support mailbox
5. Publish deliverability records
6. Upload starter files
7. Create the database and user
8. Schedule recurring tasks
9. Save run results and credentials

---

## Quick Start

### Clone the Repository

```powershell
git clone <repository-url>
cd offerops
```

### Create a Virtual Environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install Dependencies

```powershell
pip install -e .
```

---

## Configuration

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Create your local configuration file:

```powershell
Copy-Item config.example.json config.json
```

Update the following values:

* Cloudflare credentials
* WHM credentials
* Orange registrar credentials
* Server mappings
* DNS templates
* Cron templates
* Deployment profiles

> Never commit `.env` or `config.json` files containing real credentials.

---

## Running the Dashboard

Start the web interface:

```powershell
python -m offerops.cli web --port 8787 --reload
```

Open:

```text
http://127.0.0.1:8787
```

---

## Running a Dry Run

Preview a run without making changes:

```powershell
python -m offerops.cli run --csv data/domains.csv --dry-run
```

---

## Running Provisioning

Run provisioning:

```powershell
python -m offerops.cli run --csv data/domains.csv
```

---

## Orange Nameserver Automation

Run provisioning with registrar updates enabled:

```powershell
python -m offerops.cli run --csv data/domains.csv --orange-browser
```

Run only the registrar update step:

```powershell
python -m offerops.cli orange-ns --domain example.com --profile sweeps-live
```

---

## CSV Import Format

```csv
domain,profile,offer_path,notes
harborcartmarket.test,ecom-live,https://www.harborcartmarket.test/v1/msrack,
brightbuyexchange.test,sweeps-live,https://www.brightbuyexchange.test/v1/msrack,
```

### Fields

| Field      | Description         |
| ---------- | ------------------- |
| domain     | Domain to provision |
| profile    | Target environment  |
| offer_path | Offer URL or path   |
| notes      | Optional metadata   |

---

## Profiles

OfferOps supports multiple target environments.

Example profile types:

* ecom-live
* ecom-bkp
* sweeps-live
* sweeps-bkp
* sweeps-live-2
* sweeps-bkp-2

Profiles define:

* Cloudflare account
* Hosting target
* DNS templates
* Cron templates
* Hosting configuration

---

## Environment Variables

### Cloudflare

```text
CLOUDFLARE_SWEEPS_API_TOKEN
CLOUDFLARE_SWEEPS_ACCOUNT_ID
CLOUDFLARE_ECOM_API_TOKEN
CLOUDFLARE_ECOM_ACCOUNT_ID
```

### WHM

```text
WHM_URL
WHM_USERNAME
WHM_API_TOKEN
```

### Orange

```text
ORANGE_LOGIN_URL
ORANGE_HEADLESS
ORANGE_USERNAME
ORANGE_PASSWORD
```

---

## Security

OfferOps is designed so sensitive information remains outside source control.

Ignored by Git:

```text
.env
.env.*
config.json
logs/
state/
.tmp/
dist/
build/
*.egg-info/
```

Before pushing:

* Verify no credentials are staged
* Verify generated run data is excluded
* Use least-privilege API tokens
* Rotate exposed credentials immediately

---

## Running Tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

---

## License

Internal tooling project. Use according to your organization's policies.

---

Built with Python, Cloudflare, WHM/cPanel, Selenium, and a focus on repeatable operations.
