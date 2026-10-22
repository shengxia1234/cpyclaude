import argparse
import sys

from cpy_Claude.cli.command.version import cmd_version
from cpy_Claude.cli.command.ping import cmd_ping
from cpy_Claude.core.config import get_config
from cpy_Claude.core.logging_setup import setup_logging
from cpy_Claude.cli.command.run import cmd_run

def main() -> None:
    parser = argparse.ArgumentParser(prog="cpyClaude",description="cpyClauce CLI")
    parser.add_argument("--version",action="store_true",help="check the version")
    subparser = parser.add_subparsers(dest="command")
    subparser.add_parser("ping",help="Ping the core daemon")
    run_parser = subparser.add_parser("run",help="Use Agent")
    run_parser.add_argument("--goal",type=str,required=True)

    args = parser.parse_args()

    if args.version:
        cmd_version()
        return

    cf = get_config()
    setup_logging(cf)

    if args.command == "ping":
        cmd_ping(cf)
    if args.command == "run":
        cmd_run(args.goal,cf)
    else:
        parser.print_help()
        sys.exit(1)
