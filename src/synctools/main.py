import argparse

from .App import App


def main():
    parser = argparse.ArgumentParser(
        description="synctools"
    )
    parser.add_argument(
        "--dry-run", dest="dry_run", help="Enable dry run, where nothing is applied", action="store_true"
    )
    parser.add_argument(
        "--cache-data", dest="cache_data", help="Cache fetched and applied data locally", action="store_true"
    )
    parser.add_argument("--verbose", dest="verbose", help="Enable verbose output", action="store_true")
    parser.add_argument("--envfile", dest="envfile", help="Name of an env file to load envvars from")

    args = vars(parser.parse_args())

    app = App(args=args)
    app.run()


if __name__ == "__main__":
    main()
