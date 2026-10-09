import argparse
import sys

from cpy_Claude.cli.command.version import cmd_version

def main() -> None:
    parser = argparse.ArgumentParser(prog="cpyClaude",description="cpyClauce CLI")
    parser.add_argument("--version",action="store_true",help="check the version")
    subparser = parser.add_subparsers(dest="command")
    subparser.add_parser("ping",help="Ping the core daemon")

    args = parser.parse_args()

    if args.version:
        cmd_version()
        return

    if args.command == "ping":
        ...
    else:
        parser.print_help()
        sys.exit(1)
