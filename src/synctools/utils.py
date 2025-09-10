import logging
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Mapping, Optional

import dotenv


def load_env(required_envvars: list[str], envfile_path: str | None = None) -> dict:
    """
    Loads environment variables from the environment. Sets the value to None if any of the required
    envvars are missing. Also loads an envfile from disk if given in args.
    Returns a dictionary of the required envvars.
    :param required_envvars: list of required envvars
    :param envfile_path: path of envfile to load envvars from
    :return: dict: dictionary of envvars
    """
    # Try loading envfile if it's given
    if envfile_path is not None:
        envfile = Path(envfile_path)
        if not envfile.exists():
            # If an envfile is given, it must exist. Terminate early if it doesn't
            # Print absolute path to make it easier to debug
            raise FileNotFoundError(f"{envfile.absolute()}")

        dotenv.load_dotenv(dotenv_path=envfile)

    envvars = {}
    for required_envvar in required_envvars:
        # An empty string is always an invalid value
        if required_envvar not in os.environ or os.environ[required_envvar] == "":
            # We don't expect this to be caught, terminate early if an envvar is missing
            raise EnvironmentError(f"Environment variable {required_envvar} not defined")

        envvars[required_envvar] = os.environ[required_envvar]

    return envvars


def list_to_dict(list_in: list[dict], metakey: str) -> dict:
    """
    Converts a list of dicts to a dict of dicts, using the value of metakey as the key
    :param list_in: list of dicts
    :param metakey: key to use as key in return dictionary
    :return: dict: dictionary of dicts
    """
    return_dict = {}

    for record in list_in:
        key = record[metakey]
        if key in return_dict:
            logging.warning(f"Warning in list_to_dict: {key} already present, overwriting")
        return_dict[key] = record

    return return_dict


def dict_diff(dict_a: Mapping[Any, Any], dict_b: Mapping[Any, Any]) -> dict[Any, Any]:
    """
    Compare dict_a against dict_b and return the (recursive) difference.
    Only keys present in both are considered. Works with any Mapping and
    any hashable key type.
    """
    diff: dict[Any, Any] = {}

    for key in (dict_a.keys() & dict_b.keys()):
        a_val = dict_a[key]
        b_val = dict_b[key]

        if isinstance(a_val, dict) and isinstance(b_val, dict):
            sub = dict_diff(a_val, b_val)
            if sub:
                diff[key] = sub
        else:
            if a_val != b_val:
                diff[key] = a_val

    return diff


def is_running_in_cloud_run() -> bool:
    """
    Checks if the currently running script is running in Cloud Run as a service or job
    :return: bool
    """
    # K_SERVICE should always be defined in GCP if it's a service and CLOUD_RUN_JOB if it's a job
    # See https://cloud.google.com/run/docs/container-contract#env-vars
    return "K_SERVICE" in os.environ or "CLOUD_RUN_JOB" in os.environ

def add_skip_only_parser(parser: ArgumentParser, known_models_key_list: list[str]) -> ArgumentParser:
    sel = parser.add_mutually_exclusive_group()
    sel.add_argument(
        "--skip",
        help=f"Comma-separated list of models to skip (options: {', '.join(known_models_key_list)})",
    )
    sel.add_argument(
        "--only",
        help=(
            "Comma-separated list of models to run (others are skipped) "
            f"(options: {', '.join(known_models_key_list)})"
        ),
    )

    return parser

def csv_to_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]

def select_models(known_models: dict, skip: list[str], only: list[str]) -> list[str]:
    # Fail fast if unknown models were passed
    known = set(known_models.keys())
    unknown = (set(skip) | set(only)) - known
    if unknown:
        raise ValueError(f"Unknown model(s): {', '.join(sorted(unknown))}. Known: {', '.join(sorted(known))}")

    # decide final set
    if only:
        selected_models = sorted(only)
    elif skip:
        selected_models = sorted(known - set(skip))
    else:
        selected_models = sorted(known)

    return selected_models
