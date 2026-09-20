"""Long-enough hold process for cancel / SSE verification."""

from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="CURV instrument hold (cancel test).")
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--fail", action="store_true", help="Exit non-zero after hold.")
    args = parser.parse_args()
    print("instrument_hold start", flush=True)
    print("run_id=instrument_hold_live", flush=True)
    end = time.time() + float(args.seconds)
    n = 0
    while time.time() < end:
        n += 1
        print(f"tick={n}", flush=True)
        time.sleep(0.5)
    print("instrument_hold end", flush=True)
    sys.exit(1 if args.fail else 0)


if __name__ == "__main__":
    main()
