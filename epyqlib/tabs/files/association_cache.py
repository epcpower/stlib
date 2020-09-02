import json
import os

from typing import List, Dict, Set

from epyqlib.tabs.files.files_utils import ensure_dir


class AssociationCache:

    _instance: "AssociationCache" = None
    _tag = "[Associations Cache]"

    def __init__(self, files_dir: str):
        self._cache_dir = os.path.join(files_dir, "")
        self._cache_file = os.path.join(self._cache_dir, "associations-cache.json")
        ensure_dir(self._cache_dir)

        self._associations: Dict[str, List] = {}

    @staticmethod
    def get_instance():
        if AssociationCache._instance is None:
            raise Exception("AssociationsCache being used before initialized")
        return AssociationCache._instance

    @staticmethod
    def init(files_dir: str):
        AssociationCache._instance = AssociationCache(files_dir)
        AssociationCache._instance._init()
        return AssociationCache._instance

    def _init(self):
        self._read_file()

    def _read_file(self):
        if os.path.exists(self._cache_file):
            with open(self._cache_file, "r") as cache_file:
                self._associations = json.load(cache_file)

    def _write_file(self):
        with open(self._cache_file, "w") as cache_file:
            json.dump(self._associations, cache_file, indent=2)

    def clear(self):
        self._associations = {}
        if os.path.exists(self._cache_file):
            os.unlink(self._cache_file)

    def get_associations(self, serial_number: str) -> List:
        return self._associations.get(serial_number)

    def put_associations(self, serial_number: str, associations: List):
        self._associations[serial_number] = associations
        self._write_file()

    def get_all_known_file_hashes(self) -> Set[str]:
        hashes = set()

        for serial, association_list in self._associations.items():
            for association in association_list:
                if association["file"] is None:
                    continue

                if association["file"]["type"] == "Log":
                    continue

                hashes.add(association["file"]["hash"])

        return hashes
