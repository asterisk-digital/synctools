import os
from pathlib import Path

from src import App

script_dir = Path(os.path.dirname(os.path.realpath(__file__)))


# Run from CLI with python -m src.tasks.post_data
def main():
    envfile = Path(script_dir, "../../.env-dev")
    app = App({"envfile": str(envfile)})

    response = app.post_data({})

    print(response)


if __name__ == "__main__":
    main()
