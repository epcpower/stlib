import shutil
from datetime import datetime

import attr
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem, QFileDialog
from twisted.internet.defer import ensureDeferred
from twisted.internet.interfaces import IDelayedCall
from typing import Coroutine

from epyqlib.tabs.files.aws_login_manager import AwsLoginManager
from epyqlib.tabs.files.bucket_manager import BucketManager
from epyqlib.tabs.files.cache_manager import CacheManager
from epyqlib.tabs.files.configuration import Configuration, Vars
from epyqlib.tabs.files.filesview import Cols, Relationships, get_values, FilesView
from epyqlib.tabs.files.log_manager import LogManager
from epyqlib.utils.twisted import errbackhook as show_error_dialog
from .graphql import API, InverterNotFoundException


@attr.s(slots=True)
class AssociationMapping():
    association = attr.ib()
    row: QTreeWidgetItem = attr.ib()


class FilesController:
    from epyqlib.tabs.files.filesview import FilesView
    def __init__(self, view: FilesView):
        self.view = view
        self.api = API()
        self.old_notes: str = None
        self._last_sync: datetime = None

        self.bucket_manager = BucketManager()
        self.cache_manager = CacheManager()
        self.log_manager = LogManager("logs")
        self.log_rows = {}
        self.aws_login_manager = AwsLoginManager.get_instance()
        self.configuration = Configuration.get_instance()
        self.associations: [str, AssociationMapping] = {}

        self.sync_timer: IDelayedCall = None

    def setup(self):
        self.aws_login_manager.register_listener(self.login_status_changed)

        self.view.bind()
        self.view.populate_tree()
        self.view.initialize_ui()

        logged_in = self.aws_login_manager.is_logged_in()
        self.view.show_logged_out_warning(not logged_in)
        self.view.enable_file_buttons(logged_in)

        self._show_local_logs()

    ## Sync Info Methods
    def _set_sync_time(self) -> None:
        self._last_sync = datetime.now()

    ## Data fetching
    async def get_inverter_associations(self, serial_number: str):
        """
        :raises InverterNotFoundException
        """
        associations = await self.api.get_associations(serial_number)
        self.view.enable_grid_sorting(False)
        for association in associations:
            if association['file'] is None:
                print(f"[Files Controller] WARNING: Association {association['id']} returned with null file associated")
                continue

            type = association['file']['type'].lower()
            key = association['id'] + association['file']['id']
            if (key in self.associations):
                row = self.associations[key].row
                self.associations[key].association = association # Update the association in case it's changed
            else:
                row = self.view.attach_row_to_parent(type, association['file']['filename'])
                self.associations[association['id'] + association['file']['id']] = AssociationMapping(association, row)

            # Render either the new or updated association
            self.render_association_to_row(association, row)

        self.view.enable_grid_sorting(True)
        self._set_sync_time()
        self.view.show_sync_time(self._last_sync)


    async def _sync_files(self):
        missing_hashes = set()
        for key, mapping in self.associations.items():
            # mapping is of type AssociationMapping
            hash = mapping.association['file']['hash']
            if(not self.cache_manager.has_hash(hash)):
                missing_hashes.add(hash)
            else:
                mapping.row.setText(Cols.local, FilesView.check_icon)

        if len(missing_hashes) == 0:
            print("All files already hashed locally.")
            return

        coroutines = [self.sync_file(hash) for hash in missing_hashes]

        for coro in coroutines:
            await coro

    async def sync_file(self, hash):
        await self.download_file(hash)

        mapping: AssociationMapping
        for mapping in self._get_mapping_for_hash(hash):
            mapping.row.setText(Cols.local, FilesView.check_icon)

    def _get_key_for_hash(self, hash: str):
        value: AssociationMapping
        return next(key for key, value in self.associations.items() if value.association['file']['hash'] == hash)

    def _get_mapping_for_hash(self, hash: str) -> [AssociationMapping]:
        map: AssociationMapping
        return [map for map in self.associations.values() if map.association['file']['hash'] == hash]

    def _get_mapping_for_row(self, row: QTreeWidgetItem) -> AssociationMapping:
        return next(map for map in self.associations.values() if map.row == row)


    def render_association_to_row(self, association, row: QTreeWidgetItem):
        row.setText(Cols.filename, association['file']['filename'])
        row.setText(Cols.version, association['file']['version'])
        row.setText(Cols.description, association['file']['description'])

        if(association.get('model')):
            model_name = " " + association['model']['name']

            if association.get('customer'):
                relationship = Relationships.customer
                rel_text = association['customer']['name'] + model_name
            elif association.get('site'):
                relationship = Relationships.site
                rel_text = association['site']['name'] + model_name
            else:
                relationship = Relationships.model
                rel_text = "All" + model_name
        else:
            relationship = Relationships.inverter
            rel_text = association['inverter']['serialNumber']

        self.view.show_relationship(row, relationship, rel_text)

    async def download_file(self, hash: str):
        print(f"[Files Controller] Downloading missing file hash {hash}")
        filename = self.cache_manager.get_file_path(hash)
        await self.bucket_manager.download_file(hash, filename)
        return hash

    ## Lifecycle events
    def tab_selected(self):
        self.cache_manager.verify_cache()
        if self.configuration.get(Vars.auto_sync):
            ensureDeferred(self.sync_now())

    ## UI Events
    async def login_clicked(self):
        self.aws_login_manager.show_login_window(self.view.files_grid)

    async def save_file_as_clicked(self):
        map = self._get_mapping_for_row(self.view.files_grid.currentItem())
        hash = map.association['file']['hash']
        if hash not in self.cache_manager.hashes():
            await self.sync_file(hash)

        (destination, filter) = QFileDialog.getSaveFileName(
            parent=self.view.files_grid,
            caption="Pick location to save file",
            directory=map.association['file']['filename']
        )

        if destination != '':
            shutil.copy2(self.cache_manager.get_file_path(hash), destination)

    async def sync_now(self):
        self.view.show_inverter_error(None)

        unsubscribe: Coroutine = self.api.unsubscribe()

        serial_number = self.view.serial_number.text()
        # If InverterId is not set and we're connected, get inverter serial #
        if serial_number == '':
            if not self.view.device_interface.get_connected_status().connected:
                self.view.show_inverter_error('Bus is disconnected. Unable to get Inverter Serial Number')
                return
            serial_number = await self.view.device_interface.get_serial_number()

            self.view.serial_number.setText(serial_number)


        try:
            await self._fetch_files(self.view.serial_number.text())
        except InverterNotFoundException:
            self.view.show_inverter_error("Error: Inverter ID not found.")
            return
        finally:
            await unsubscribe

        await self.api.subscribe(self.file_updated)

    def file_updated(self, action, payload):
        if (action == 'created'):
            pass
            # Get file info including association
            # Create row for info
            # Add info and row to self.associations

        key = self._get_key_for_hash(payload['hash'])

        if (action == 'updated'):
            map: AssociationMapping = self.associations[key]
            map.association['file'].update(payload)
            self.render_association_to_row(map.association, map.row)

        if (action == 'deleted'):
            self.view.remove_row(self.associations[key].row)
            del(self.associations[key])



    def file_item_clicked(self, item: QTreeWidgetItem, column: int):
        if (item in get_values(self.view.section_headers)):
            self.view.show_file_details(None)
            self.view.enable_file_action_buttons(False)
        else:
            mapping: AssociationMapping = next(a for a in self.associations.values() if a.row == item)
            self.view.show_file_details(mapping.association)
            self.view.enable_file_action_buttons(True)

    async def _fetch_files(self, serial_number):
        """
        :raises InverterNotFoundException
        """
        await self.get_inverter_associations(serial_number)
        await self._sync_files()


    ## Application events
    async def login_status_changed(self, logged_in: bool):
        self.view.show_logged_out_warning(not logged_in)
        self.view.btn_sync_now.setDisabled(not logged_in)
        self.view.enable_file_buttons(logged_in)

        if logged_in:
            await self.sync_now()
        else:
            await self.api.unsubscribe()

    ## Notes
    def set_original_notes(self, notes: str):
        self.old_notes = notes or ''

    def notes_modified(self, new_notes):
        if self.old_notes is None:
            return False

        return (len(self.old_notes) != len(new_notes)) or self.old_notes != new_notes

    def _show_local_logs(self):
        for filename in self.log_manager.filenames():
            row = self.view.attach_row_to_parent('log', filename)
            self.log_rows[filename] = row

            row.setText(Cols.local, self.view.check_icon)
            row.setText(Cols.web, self.view.question_icon)

            ctime = self.log_manager.stat(filename).st_ctime
            ctime = datetime.fromtimestamp(ctime)
            row.setText(Cols.created_at, ctime.strftime(self.view.time_format))

