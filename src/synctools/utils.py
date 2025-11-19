import copy
import logging
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Mapping, Optional
from typing import Union, Optional, AnyStr, Iterable


class NormalizeException(Exception):
    pass


class EmptyValueException(Exception):
    pass


class MixedTypesException(Exception):
    pass

PathLike = Union[str, os.PathLike[str]]

# Implemented to avoid dotenv dependency in other modules
def load_env_file(dotenv_path: PathLike = ".env") -> None:
    # Normalize to Path
    p = Path(dotenv_path)

    if not p.is_file():
        return

    for line in p.read_text().splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        if "=" in line:
            key, value = line.split("=", 1)

            key = key.strip()
            value = value.strip().strip('"').strip("'")

            # Do not overwrite existing environment variables
            os.environ.setdefault(key, value)



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

        load_env_file(dotenv_path=envfile)

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

    for key in dict_a.keys() & dict_b.keys():
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
    def csv_list(value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]

    sel = parser.add_mutually_exclusive_group()
    sel.add_argument(
        "--skip",
        type=csv_list,
        help=f"Comma-separated list of models to skip (options: {', '.join(known_models_key_list)})",
    )
    sel.add_argument(
        "--only",
        type=csv_list,
        help=(
            f"Comma-separated list of models to run (others are skipped) (options: {', '.join(known_models_key_list)})"
        ),
    )

    return parser


def csv_to_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def select_models(known_models: list[str], skip: list[str] | None, only: list[str] | None) -> list[str]:
    if not known_models:
        # Known models can't be empty, fail early if it is
        raise ValueError("No known models passed")

    if not skip and not only:
        # Both args are empty or None, return all models
        return sorted(known_models)

    if skip and only:
        # It doesn't make sense to specify both skip and only, fail early
        raise ValueError("Cannot specify both skip and only")

    if skip is None:
        skip = []

    if only is None:
        only = []

    # Fail fast if unknown models were passed
    known = set(known_models)
    unknown = (set(skip) | set(only)) - known
    if unknown:
        raise ValueError(f"Unknown model(s): {', '.join(unknown)}. Known: {', '.join(known)}")

    # Decide final set
    if only:
        selected_models = only
    elif skip:
        selected_models = known - set(skip)
    else:
        # Shouldn't happen (covered above), but just in case
        logging.warning("No skip or only models specified, running all models")
        selected_models = known

    # Return selected models sorted by known_models order
    return sorted(selected_models, key=lambda x: known_models.index(x))


def create_template(data: list[dict]) -> dict:
    return merge_ignore_none(data)


def create_schema_dict(data: list[dict]) -> dict:
    return merge_ignore_none(data)


def merge_ignore_none(dicts: list[dict]) -> dict:
    """
    Recursively merge a sequence of dicts with these rules:
      - If a key appears only with None values, include it with "".
      - None values never downgrade an existing non-empty value.
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
                # Include keys that are only None by initializing to ""
                if k not in into:
                    into[k] = ""
                # If the key already exists, None never downgrades—do nothing.
                continue

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


def normalize_dicts(template: dict[str, Any], inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Recursively normalize a list of dicts against a template schema.
    - If a template field is a list, None becomes [].
    - If it's a list of dicts, recurse into each dict.
    - If it's a dict, recurse into it.
    - Scalars default to the template value if missing/None.
    """

    def normalize(template_value: Any, input_value: Any) -> Any:
        if template_value is None:
            # Template should never contain None, hard fail
            raise NormalizeException("Template should never contain None")

        if input_value is None:
            # Simplest case, input is None. Use template value.
            return template_value

        if isinstance(template_value, dict):
            if not isinstance(input_value, dict):
                # Type mismatch, we can't resolve this
                raise NormalizeException("Type mismatch: template is a dict, but input is not a dict")

            # Recurse into dict
            return {k: normalize(v, (input_value or {}).get(k)) for k, v in template_value.items()}

        if isinstance(template_value, list):
            if not isinstance(input_value, list):
                # Type mismatch, we can't resolve this
                raise NormalizeException("Type mismatch: template is a list, but input is not a list")

            if len(template_value) == 0:
                # Template can't be empty list... we need to know the type
                raise NormalizeException("Type mismatch: template list should have at least one element")

            # Check if template_value has mixed types
            has_mixed_types = len({type(x) for x in template_value}) > 1
            if has_mixed_types:
                # Bad template
                raise NormalizeException("Type mismatch: template list has mixed types")

            # Now we have a non-empty, non-mixed-type list (in the template)

            return_list = []
            for i in range(len(template_value)):
                template_element = template_value[i]
                input_element = input_value[i] if i < len(input_value) else None
                return_list.append(normalize(template_element, input_element))

            return return_list

        # At this point, we have a primitive, non-empty type

        # if isinstance(template_value, str) and isinstance(input_value, int):

        return input_value

    return [normalize(template, d) for d in inputs]


def validate_dict(input_dict: dict) -> None:
    """
    Recursively validate a given dict.
    It needs to be 1. complete (no empty values). That means:
    - No "None" values
    - No empty lists
    - No empty dicts
    It also needs to be 2. valid (no mixed types). That means:
    - No mixed values in lists
    - No mixed keys in dicts
    :param input_dict:
    :raises DictValidationException: If the dict is not complete or valid
    :return: None
    """

    def validate_value(value: Any) -> None:
        if value is None:
            raise EmptyValueException("None value found")
        if isinstance(value, list) and len(value) == 0:
            raise EmptyValueException("Empty list found")
        if isinstance(value, dict) and len(value) == 0:
            raise EmptyValueException("Empty dict found")
        if isinstance(value, list):
            has_mixed_types = len({type(x) for x in value}) > 1
            if has_mixed_types:
                raise MixedTypesException("Type mismatch: list has mixed types")
            for v in value:
                validate_value(v)
        elif isinstance(value, dict):
            # Ensure no mixed value keys
            has_mixed_types = len({type(x) for x in value.keys()}) > 1
            if has_mixed_types:
                raise MixedTypesException("Type mismatch: dict keys have mixed types")
            for v in value.values():
                validate_value(v)
        else:
            # Primitive value, do nothing
            pass

    validate_value(input_dict)


from typing import Any


def complete_dicts(template_dict: dict, input_dicts: list[dict]) -> list[dict]:
    """
    Complete each input dict to match the structure of template_dict.
    - Copy structure recursively from the template.
    - For missing branches:
        * dict -> {}
        * list -> []
        * primitive -> template's value
    - Coerce int -> str when the template expects a string.
    """

    # Validate the template is complete & valid per provided rules
    validate_dict(template_dict)

    def _coerce_to_template_type(template_value: Any, value: Any) -> Any:
        # Only do the single requested coercion: int -> str
        if isinstance(template_value, str) and isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value

    def _empty_like(template_value: Any) -> Any:
        if isinstance(template_value, dict):
            return {}
        if isinstance(template_value, list):
            return []
        # For primitives, default to None
        return None

    def _complete(template_value: Any, data_value: Any) -> Any:
        # Dict branch: ensure all keys exist; recurse
        if isinstance(template_value, dict):
            base = data_value if isinstance(data_value, dict) else {}
            out = {}
            for k, t_v in template_value.items():
                if k in base:
                    out[k] = _complete(t_v, base[k])
                else:
                    out[k] = _empty_like(t_v)
            return out

        # List branch: template lists are non-empty (validated).
        # Use the first item as the element schema. Recurse per element.
        if isinstance(template_value, list):
            elem_schema = template_value[0]
            if isinstance(data_value, list):
                result_list = []
                for item in data_value:
                    # Apply coercion for primitive case up front (int -> str)
                    item = _coerce_to_template_type(elem_schema, item)
                    result_list.append(_complete(elem_schema, item))
                return result_list
            # If not a list or missing: provide an empty list to keep structure complete
            return []

        # Coerce when template expects str and value is int
        data_value = _coerce_to_template_type(template_value, data_value)
        return data_value

    return [_complete(template_dict, d) for d in input_dicts]
