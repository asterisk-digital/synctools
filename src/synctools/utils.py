import copy
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

def create_template(data: list[dict]) -> dict:
    return merge_ignore_none(data)

def merge_ignore_none(dicts: list[dict]) -> dict:
    """
    Recursively merge a sequence of dicts with these rules:
      - None values are ignored (never written).
      - Dicts are merged recursively.
      - "Upgrade" empty -> non-empty ([], {}, ""), but never "downgrade" non-empty -> empty.
      - For lists: the first non-empty list wins. We never replace a non-empty list with an empty list.
      - For scalars (non-containers): last non-None wins, except we do not overwrite a non-empty
        string with an empty string.
      - Type flips are allowed only when upgrading from an *empty container* to a non-empty value.

    Returns a new dict; inputs are not modified.
    """

    def is_empty_container(v: Any) -> bool:
        return isinstance(v, (list, dict)) and len(v) == 0

    def is_empty_string(v: Any) -> bool:
        return isinstance(v, str) and v == ""

    def is_container(v: Any) -> bool:
        return isinstance(v, (list, dict))

    def is_empty(v: Any) -> bool:
        # "Empty" for downgrade/upgrade purposes
        return v is None or is_empty_container(v) or is_empty_string(v)

    def should_upgrade(old: Any, new: Any) -> bool:
        # Upgrade when old is empty and new is not empty
        if is_empty(old) and not is_empty(new):
            return True
        # Dicts merge rather than replace; treat as upgrade path handled elsewhere
        return False

    def is_downgrade(old: Any, new: Any) -> bool:
        # Never replace non-empty with empty
        if not is_empty(old) and is_empty(new):
            return True
        # Specifically, don't overwrite non-empty string with empty string
        if isinstance(old, str) and old != "" and is_empty_string(new):
            return True
        # Don't replace a non-empty list with an empty list
        if isinstance(old, list) and len(old) > 0 and isinstance(new, list) and len(new) == 0:
            return True
        return False

    def _merge(into: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
        for k, v in src.items():
            if v is None:
                continue  # ignore None entirely

            if k not in into:
                # First write: deep-copy containers to avoid mutating inputs later
                into[k] = copy.deepcopy(v) if is_container(v) else v
                continue

            old = into[k]

            # Dict + Dict => recursive merge
            if isinstance(old, dict) and isinstance(v, dict):
                into[k] = _merge(old, v)
                continue

            # Never downgrade
            if is_downgrade(old, v):
                continue

            # Upgrade: empty -> non-empty, allowing type change (e.g., [] -> [{"a":1}])
            if should_upgrade(old, v):
                into[k] = copy.deepcopy(v) if is_container(v) else v
                continue

            # Lists: keep the first non-empty list; don't replace it with another list (empty or not)
            if isinstance(old, list) and isinstance(v, list):
                # If old is empty, the 'should_upgrade' branch above already handled replacing with non-empty.
                # If old is non-empty, we keep it (no concatenation unless you want that behavior).
                continue

            # For everything else (primarily scalars), last non-None wins
            # (we already blocked empty-string downgrades above).
            into[k] = v

        return into

    result: dict[str, Any] = {}
    for d in dicts:
        if not isinstance(d, dict):
            raise TypeError(f"All items must be dicts; got {type(d).__name__}")
        result = _merge(result, d)
    return result
