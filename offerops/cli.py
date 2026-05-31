from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_app_config, load_settings
from .importer import load_jobs
from .runner import OfferProvisioner
from .state import StateStore, serialize_result
from .web import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="offerops", description="Automate offer-site provisioning.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Provision domains from a CSV file.")
    run_parser.add_argument("--csv", default="data/domains.csv", help="CSV with domain,profile,offer,notes columns.")
    run_parser.add_argument("--dry-run", action="store_true", help="Print and store planned actions without provider writes.")
    run_parser.add_argument("--orange-browser", action="store_true", help="Use browser automation to search Orange accounts and update nameservers.")

    orange_parser = sub.add_parser("orange-ns", help="Run only the Orange nameserver update step for one domain.")
    orange_parser.add_argument("--domain", required=True, help="Domain to search in Orange and update nameservers for.")
    orange_parser.add_argument("--profile", required=True, help="Profile used to resolve the Cloudflare nameservers.")
    orange_parser.add_argument("--dry-run", action="store_true", help="Show which Orange accounts would be searched without updating anything.")

    sub.add_parser("status", help="Print saved job state.")

    web_parser = sub.add_parser("web", help="Start the local dashboard.")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8787)

    args = parser.parse_args()
    settings = load_settings()
    config = load_app_config(settings.config_path)
    state = StateStore(settings.state_path)

    if args.command == "run":
        provisioner = OfferProvisioner(settings, config, state, dry_run=args.dry_run, use_orange_browser=args.orange_browser)
        for job in load_jobs(Path(args.csv)):
            print(json.dumps(serialize_result(provisioner.run(job)), indent=2))
    elif args.command == "orange-ns":
        provisioner = OfferProvisioner(settings, config, state, dry_run=args.dry_run, use_orange_browser=True)
        result = provisioner.run_orange_nameserver_update(args.domain, args.profile)
        print(json.dumps(result, indent=2))
    elif args.command == "status":
        print(json.dumps(state.read(), indent=2))
    elif args.command == "web":
        serve(args.host, args.port, settings, config, state)


if __name__ == "__main__":
    main()
