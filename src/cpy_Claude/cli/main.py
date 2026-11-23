import argparse
import sys
import asyncio

from cpy_Claude.cli.command.version import cmd_version
from cpy_Claude.cli.command.ping import cmd_ping
from cpy_Claude.core.config import get_config
from cpy_Claude.core.logging_setup import setup_logging
from cpy_Claude.cli.command.run import cmd_run
from cpy_Claude.cli.command.core import cmd_core_start,cmd_core_status,cmd_core_stop,cmd_core_restart
from cpy_Claude.cli.command.trace import cmd_trace

def main() -> None:
    parser = argparse.ArgumentParser(prog="cpyClaude",description="cpyClauce CLI")
    parser.add_argument("--version",action="store_true",help="check the version")
    subparser = parser.add_subparsers(dest="command")
    subparser.add_parser("ping",help="Ping the core daemon")
    run_parser = subparser.add_parser("run",help="Use Agent")
    run_parser.add_argument("--goal",type=str,required=True,help="The goal you wanna deal with using agent.")
    trace_parser = subparser.add_parser("trace",help="View system trace log")
    trace_parser.add_argument("run_id", nargs="?", default=None, help="Filter by run ID") # 位置参数,不用加--run_id,直接加参数
    trace_parser.add_argument("--layer", choices=["ipc", "event", "llm"], help="Filter by layer")
    trace_parser.add_argument("--direction",choices=["CORE","CORE->LLM","LLM->CORE","CORE->CLIENT","CLIENT->CORE"],help="Filter by direction (e.g. CORE->LLM)")
    trace_parser.add_argument("--raw", action="store_true", help="Output raw NDJSON")
    trace_parser.add_argument("--follow", "-f", action="store_true", help="Follow new records")
    core_parser = subparser.add_parser("core",help="Manage the core daemon")
    core_sub = core_parser.add_subparsers(dest="core_command")
    core_sub.add_parser("start", help="Start the daemon in the background")
    core_sub.add_parser("stop", help="Stop the running daemon")
    core_sub.add_parser("status", help="Show daemon status")
    core_sub.add_parser("restart",help="restart the daemon")

    args = parser.parse_args()

    if args.version:
        cmd_version()
        return

    cf = get_config()
    setup_logging(cf)

    if args.command == "ping":
        cmd_ping(cf)
    elif args.command == "run":
        cmd_run(args.goal,cf)
    elif args.command == "core":
        if args.core_command == "start":
            asyncio.run(cmd_core_start(cf))
        elif args.core_command == "stop":
            asyncio.run(cmd_core_stop(cf))
        elif args.core_command == "status":
            cmd_core_status(cf)
        elif args.core_command == "restart":
            asyncio.run(cmd_core_restart(cf))
    elif args.command == "trace":
        cmd_trace(cf,args.run_id,args.layer,args.direction,args.raw,args.follow)
    else:
        parser.print_help()
        sys.exit(1)
