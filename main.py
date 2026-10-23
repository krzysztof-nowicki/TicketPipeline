"""
Northdesk Company
"""

import argparse
import asyncio
import sys
import uvicorn
from scripts.config import get_settings
from scripts.temporal.worker import run_worker


def main():
    parser = argparse.ArgumentParser(description="Northdesk Ticket Workflow Runner")
    parser.add_argument(
        "--role",
        choices=["api", "worker", "all"],
        default="api",
        help="Service role to run: 'api', 'worker', or 'all'",
    )
    args = parser.parse_args()
    settings = get_settings()

    if args.role == "api":
        uvicorn.run("scripts.front_api.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=False)
    elif args.role == "worker":
        asyncio.run(run_worker())
    # Local debugging: run both API and worker in the same process
    elif args.role == "all":
        import threading
        t = threading.Thread(target=lambda: asyncio.run(run_worker()), daemon=True)
        t.start()
        uvicorn.run("scripts.front_api.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=False)


if __name__ == "__main__":
    main()