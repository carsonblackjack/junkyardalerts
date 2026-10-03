import os
import sys

import sentry_sdk
from dotenv import load_dotenv

load_dotenv()

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=False)

from scrape_job import run_scrape

if __name__ == "__main__":
    run_scrape(send_summary="--summary" in sys.argv)
