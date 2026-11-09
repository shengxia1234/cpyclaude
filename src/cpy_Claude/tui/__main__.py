import argparse

from cpy_Claude.core.config import get_config
from cpy_Claude.tui.app import TuiApp

def main():
    parser = argparse.ArgumentParser(prog="cpyClaude-tui",description="cpyClauce TUI")
    parser.add_argument(
        "--replay",
        metavar="RUN_ID",
        help="Replay events from a past run on connect",
    )
    args = parser.parse_args()

    cf = get_config()
    app = TuiApp(cf.host,cf.port,args.replay)
    app.run()

    

if __name__ == "__main__":
    main()