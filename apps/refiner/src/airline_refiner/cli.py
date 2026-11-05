"""CLI discoverability without an executable refinement loop."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="airline-refiner",
        description="Refinement worker scaffold. Execution is not implemented.",
    )
    parser.add_argument("command", choices=["run"], nargs="?")
    args = parser.parse_args()
    if args.command == "run":
        parser.exit(2, "Refinement execution is not implemented; no work was performed.\n")
    parser.print_help()
