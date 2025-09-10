import datetime
import json
import logging
import os
from pathlib import Path

from . import GCPLogger as Gcpl
from . import utils

script_dir = Path(os.path.dirname(os.path.realpath(__file__)))

base_cachedir = Path(script_dir, "../../cache")
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
cachedir = Path(base_cachedir, timestamp)


class App:
    def __init__(self, args: {} = None):
        self.args = args if args is not None else {}

        self.dry_run = self.args["dry_run"] if "dry_run" in self.args else False
        self.verbose = self.args["verbose"] if "verbose" in self.args else False
        self.cache_data = self.args["cache_data"] if "cache_data" in self.args else False
        self.envfile = self.args["envfile"] if "envfile" in self.args else None

        logging.getLogger().setLevel(logging.DEBUG if self.verbose else logging.INFO)

        if utils.is_running_in_cloud_run():
            # This handler formats the logs so GCP can parse them
            logging.getLogger().addHandler(Gcpl.GCPLogger())

        required_envvars = ["API_URL", "API_KEY"]
        self.envvars = utils.load_env(required_envvars, self.envfile)

        self.origin_client_data = [{"Id": 1, "Name": "Test 1"}, {"Id": 2, "Name": "Test 2"}]
        self.target_client_data = [{"Id": 1, "Name": "Test 1"}, {"Id": 3, "Name": "Test 3"}]

    def run(self):
        logging.info("Running...")

        origin_data = self.fetch_origin_data()
        target_data = self.fetch_target_data()

        if self.cache_data:
            self.dump_data(origin_data, "origin_data")
            self.dump_data(target_data, "target_data")

        changelist = self.calculate(origin_data, target_data)

        if self.cache_data:
            self.dump_data(changelist, "changelist")

        if not self.dry_run:
            self.apply(changelist)

        logging.info("Done!")

    # Fetch data from some imagined origin
    def fetch_origin_data(self) -> list:
        response_data = self.origin_client_data
        return response_data

    def fetch_target_data(self) -> list:
        response_data = self.target_client_data
        return response_data

    # Calculate required changes and return a set of lists with changes
    @staticmethod
    def calculate(origin_data_list: list, target_data_list: list) -> dict:
        origin_data = utils.list_to_dict(origin_data_list, "Id")
        target_data = utils.list_to_dict(target_data_list, "Id")

        newlist = []
        updatelist = {}
        deletelist = {}

        for origin_key, origin_record in origin_data.items():
            new_entry = {"Id": origin_record["Id"], "Name": origin_record["Name"]}

            if origin_key not in target_data:
                # If entry does not exist in target, create a new one
                newlist.append(new_entry)
            else:
                diff = utils.dict_diff(new_entry, target_data[origin_key])
                if diff != {}:
                    # Native ID is required to know which record we should PATCH to
                    native_id = target_data[origin_key]["Id"]
                    if native_id in updatelist:
                        logging.warning(
                            f"calculate_contacts: Native Id {native_id} " + "already exists in updatelist. Overwriting."
                        )
                    updatelist[native_id] = diff

        for target_key, target_record in target_data.items():
            if target_key not in origin_data:
                deletelist[target_key] = target_record

        return {"newlist": newlist, "updatelist": updatelist, "deletelist": deletelist}

    # Apply required changes
    def apply(self, changelist):
        for record in changelist["newlist"]:
            self.post_data(record)
            # response = self.landax_client.post_data()
            # if response.status_code != 201:
            #     logging.error(f'Error creating record: {response.text}')

        for native_id, diff in changelist["updatelist"].items():
            pass
            # response = self.landax_client.patch_data('Tasks', native_id, diff)
            # if response.status_code >= 300:
            #     logging.error(f'Error patching record: {response.text}')

        for native_id in changelist["deletelist"]:
            pass
            # response = self.landax_client.delete_data('Tasks', native_id)
            # if response.status_code >= 300:
            #     logging.error(f'Error deleting record: {response.text}')

    def post_data(self, record: dict):
        logging.info(f"Posting data: {record}")
        return True

    @staticmethod
    def dump_data(data, name: str):
        if not cachedir.exists():
            cachedir.mkdir(parents=True, exist_ok=True)

        filename = f"{name}.json"
        path = Path(cachedir, filename)
        with open(path, "w") as file:
            file.write(json.dumps(data, indent=4))

    @staticmethod
    def load_data(path: Path):
        with open(path) as file:
            data = json.loads(file.read())

        return data
