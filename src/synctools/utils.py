import logging
import os
from pathlib import Path

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


def dict_diff(dict_a: dict, dict_b: dict) -> dict:
    """
    Compares dict_a and dict_b. Returns the difference. Return a dict with a key and value for
    each value that is different. See the tests for a demonstration how this should work.
    Essentially, check if dict_a is a strict subset of dict_b, and return the difference
    Keys that aren't in both a and b are ignored
    :param dict_a:
    :param dict_b:
    :return: dict
    """
    diff = {}
    for key, value in dict_a.items():
        if key in dict_b:
            if value != dict_b[key]:
                diff[key] = value

    return diff


def is_running_in_cloud_run() -> bool:
    """
    Checks if the currently running script is running in Cloud Run as a service or job
    :return: bool
    """
    # K_SERVICE should always be defined in GCP if it's a service and CLOUD_RUN_JOB if it's a job
    # See https://cloud.google.com/run/docs/container-contract#env-vars
    return "K_SERVICE" in os.environ or "CLOUD_RUN_JOB" in os.environ
