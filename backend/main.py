"""
Dice Scraper Pro - Main Entry Point
====================================
Now uses microservices architecture internally.

Usage:
    python main.py                    # All-in-one mode (default)
    python main.py --service api     # API Gateway only
    python main.py --service scraper  # Scraper Worker only
    python main.py --service scheduler # Scheduler only

Or use the unified runner:
    python services/run.py --service all
"""

import sys
import os

# Add backend directory to path
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

if __name__ == "__main__":
    from services.run import run_all, run_api, run_scraper, run_scheduler
    import argparse

    parser = argparse.ArgumentParser(description="Dice Scraper Pro")
    parser.add_argument(
        "--service", choices=["api", "scraper", "scheduler", "all"], default="all"
    )
    args = parser.parse_args()

    if args.service == "api":
        run_api()
    elif args.service == "scraper":
        run_scraper()
    elif args.service == "scheduler":
        run_scheduler()
    else:
        run_all()
