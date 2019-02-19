import shutil
from datetime import datetime
from typing import Coroutine

import attr
from PyQt5.QtWidgets import QTreeWidgetItem, QFileDialog
from botocore.exceptions import EndpointConnectionError
from twisted.internet.defer import ensureDeferred
from twisted.internet.error import DNSLookupError

from epyqlib.device import DeviceInterface
from epyqlib.tabs.files.activity_log import ActivityLog, Event
from epyqlib.tabs.files.activity_syncer import ActivitySyncer
from epyqlib.tabs.files.aws_login_manager import AwsLoginManager
from epyqlib.tabs.files.bucket_manager import BucketManager
from epyqlib.tabs.files.files_manager import FilesManager
from epyqlib.tabs.files.filesview import Cols, Relationships, get_values
from epyqlib.tabs.files.log_manager import LogManager
from epyqlib.tabs.files.sync_config import SyncConfig, Vars
from epyqlib.utils.twisted import errbackhook
from .graphql import API, InverterNotFoundException


@attr.s(slots=True)
class AssociationMapping():
    association = attr.ib()
    row: QTreeWidgetItem = attr.ib()


class FilesController:
    _tag = "[Files Controller]"
    from epyqlib.tabs.files.filesview import FilesView
    def __init__(self, view: FilesView):
        self.view = view
        self.old_notes: str = None
        self._last_sync: datetime = None


        self.activity_log = ActivityLog()
        self.api = API()
        self.activity_syncer = ActivitySyncer(self.activity_log, self.api)

        self.aws_login_manager = AwsLoginManager.get_instance()
        self.bucket_manager = BucketManager()
        self._log_rows: dict[str, QTreeWidgetItem] = {}
        self.sync_config = SyncConfig.get_instance()
        self.cache_manager = FilesManager(self.sync_config.directory)
        self.log_manager = LogManager.init(self.sync_config.directory)

        self._is_offline = self.sync_config.get(Vars.offline_mode) or False
        self._is_connected = False
        self._serial_number = ""
        self._inverter_id = ""
        self._build_hash = ""

        self._device_interface = None

        self.associations: [str, AssociationMapping] = {}

    def setup(self):
        self.aws_login_manager.register_listener(self.login_status_changed)

        self.view.bind()
        self.view.populate_tree()
        self.view.initialize_ui()

        logged_in = self.aws_login_manager.is_logged_in()
        self.view.show_logged_out_warning(not logged_in)
        if logged_in:
            try:
                self.aws_login_manager.refresh()
            except EndpointConnectionError as e:
                print(f"{self._tag} Unable to login to AWS. Setting offline mode to true.")
                self.set_offline(True)


        self.activity_log.register_listener(lambda event: self.view.add_log_line(LogRenderer.render_event(event)))
        self.activity_log.register_listener(self.activity_syncer.listener)

        self.log_manager.register_listener(self.log_synced)

        self._show_local_logs()

    def device_interface_set(self, device_interface: DeviceInterface):
        self._device_interface = device_interface

    async def _read_info_from_inverter(self, online: bool, transmit: bool):
        # Appears you can never be "connected" in offline mode?
        if not transmit:
            return

        # Don't do this if we already have this information
        if self._serial_number != "":
            return

        self._serial_number = await self._device_interface.get_serial_number()
        self._build_hash = await self._device_interface.get_build_hash()

        inverter_info = await self.api.get_inverter_by_serial(self._serial_number)

        self._inverter_id = inverter_info['id']
        self.log_manager.inverter_id = self._inverter_id
        self.log_manager.build_id = self._build_hash

    ## Sync Info Methods
    def _set_sync_time(self) -> None:
        self._last_sync = datetime.now()

    ## Data fetching
    async def get_inverter_associations(self, serial_number: str):
        """
        :raises InverterNotFoundException
        """
        associations = await self.api.get_associations(serial_number)
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
                self.view.show_sync_status_icon(row, Cols.local, self.view.fa_question, self.view.color_red)
                self.view.show_sync_status_icon(row, Cols.web, self.view.fa_check, self.view.color_green)
                self.associations[association['id'] + association['file']['id']] = AssociationMapping(association, row)

            # Render either the new or updated association
            self.render_association_to_row(association, row)

        self.view.sort_grid_items()
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
                self.view.show_sync_status_icon(mapping.row, Cols.local, self.view.fa_check, self.view.color_green)

        if len(missing_hashes) == 0:
            print("All files already hashed locally.")
            return

        #TODO: Figure out how to download multiple files at a time
        # Just trying to wrap in asyncio task fails.
        for hash in missing_hashes:
            await self.sync_file(hash)

    async def sync_file(self, hash):
        await self.download_file(hash)

        mapping: AssociationMapping
        for mapping in self._get_mapping_for_hash(hash):
            self.view.show_sync_status_icon(mapping.row, Cols.local, self.view.fa_check, self.view.color_green)

    def _get_key_for_hash(self, hash: str):
        value: AssociationMapping
        return next(key for key, value in self.associations.items() if value.association['file']['hash'] == hash)

    def _get_mapping_for_hash(self, hash: str) -> [AssociationMapping]:
        map: AssociationMapping
        return [map for map in self.associations.values() if map.association['file']['hash'] == hash]

    def _get_mapping_for_row(self, row: QTreeWidgetItem) -> AssociationMapping:
        try:
            return next(map for map in self.associations.values() if map.row == row)
        except StopIteration:
            return None


    def render_association_to_row(self, association, row: QTreeWidgetItem):
        row.setText(Cols.filename, association['file']['filename'])
        row.setText(Cols.version, association['file']['version'])
        row.setText(Cols.description, association['file']['description'])

        if(association.get('model')):
            model_name = " " + association['model']['name']

            if association.get('customer'):
                relationship = Relationships.customer
                rel_text = association['customer']['name'] + "," + model_name
            elif association.get('site'):
                relationship = Relationships.site
                rel_text = association['site']['name'] + "," + model_name
            else:
                relationship = Relationships.model
                rel_text = "All" + model_name
        else:
            relationship = Relationships.inverter
            rel_text = "SN: " + association['inverter']['serialNumber']

        self.view.show_relationship(row, relationship, rel_text)

    async def download_file(self, hash: str):
        print(f"[Files Controller] Downloading missing file hash {hash}")
        filename = self.cache_manager.get_file_path(hash)
        await self.bucket_manager.download_file(hash, filename)
        return hash

    ## Lifecycle events
    def tab_selected(self):
        self.cache_manager.verify_cache()
        if self.sync_config.get(Vars.auto_sync):
            sync_def = ensureDeferred(self.sync_now())
            sync_def.addErrback(errbackhook)

    async def on_bus_status_changed(self, online: bool, transmit: bool):
        await self._read_info_from_inverter(online, transmit)

    ## UI Events
    async def login_clicked(self):
        try:
            self.aws_login_manager.show_login_window(self.view.files_grid)
        except EndpointConnectionError:
            print(f"{self._tag} Unable to login to AWS. Setting offline mode to true.")
            self.set_offline(True)

    def open_file(self, row: QTreeWidgetItem):
        file_hash = self._get_mapping_for_row(row).association['file']['hash']
        file_path = self.cache_manager.get_file_path(file_hash)
        import subprocess, os, sys
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', file_path))
        elif os.name == 'nt':  # For Windows
            os.startfile(file_path)
        elif os.name == 'posix':  # For Linux, Mac, etc.
            subprocess.call(('xdg-open', file_path))

    async def save_file_as_clicked(self, item: QTreeWidgetItem = None):
        if item is None:
            item = self.view.files_grid.currentItem()

        map = self._get_mapping_for_row(item)
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


        serial_number = self.view.serial_number.text()
        # If InverterId is not set and we're connected, get inverter serial #
        if serial_number == '':
            if not self._device_interface.get_connected_status().connected:
                self.view.show_inverter_error('Bus is disconnected. Unable to get Inverter Serial Number')
                return
            serial_number = await self._device_interface.get_serial_number()

            self.view.serial_number.setText(serial_number)

        try:
            await self.log_manager.sync_logs_to_server()
        except EndpointConnectionError:
            self.set_offline(True)

        if not self._is_offline:
            unsubscribe: Coroutine = self.api.unsubscribe()

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
            return

        file_mapping: AssociationMapping = self._get_mapping_for_row(item)
        if file_mapping is not None:
            self.view.show_file_details(file_mapping.association)

        if item in self._log_rows.values():
            hash = next(key for key, value in self._log_rows.items() if value == item)


    async def send_to_inverter(self, row: QTreeWidgetItem):
        map = self._get_mapping_for_row(row)

        file = map.association['file']
        event = Event.new_load_param_file(
            self.view.serial_number.text(),
            'FakeUser',
            file['id'],
            file['hash'],
            file['filename']
        )
        await self.activity_log.add(event)

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


    ## Raw Log Syncing
    async def _sync_pending_logs(self):
        if self._is_offline:
            return

        log = self.log_manager.get_next_pending_log()
        while log is not None:
            file_path = self.log_manager.get_path_to_log(log.hash)
            await self.bucket_manager.upload_log(file_path, log.hash)

            # ?: Where do we want to store the timestamp and build_id that the log was generated?
            notes = f"BuildId: {log.build_id}\nLog Captured At: {log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            create_file_response = await self.api.create_file(API.FileType.Log, log.filename, log.hash, notes)
            new_file_id = create_file_response['id']

            new_association = await self.api.create_association(self._inverter_id, new_file_id)

            await self.activity_log.add(Event.new_raw_log(self._inverter_id, "Testuser", self._build_hash, log.filename, log.hash))

            ## Move UI row from pending to current
            row = self.view.pending_log_rows.pop(log.hash)
            map = AssociationMapping(new_association, row)
            key = new_association['id'] + new_association['file']['id']

            self.associations[key] = map

            # Done processing. Remove pending and get next (if present)
            self.log_manager.remove_pending(log)
            log = self.log_manager.get_next_pending_log()

    async def _show_pending_logs(self):
        for log in self.log_manager.get_pending_logs():
            row = self.view.attach_row_to_parent('log', log.filename)
            self.view.show_check_icon(row, Cols.local)
            self.view.show_question_icon(row, Cols.web)

            ctime = self.log_manager.stat(hash).st_ctime
            ctime = datetime.fromtimestamp(ctime)
            row.setText(Cols.created_at, ctime.strftime(self.view.time_format))

            row.setText(Cols.creator, log.username)

            self.view.pending_log_rows[log.hash] = row



    def _show_local_logs(self):
        for hash, filename in self.log_manager.items():
            row = self._create_local_log_row(filename, hash)

            self.view.show_sync_status_icon(row, Cols.local, self.view.fa_check, self.view.color_green)
            if hash in self.log_manager.uploaded_hashes:
                self.view.show_sync_status_icon(row, Cols.web, self.view.fa_check, self.view.color_green)
            else:
                self.view.show_sync_status_icon(row, Cols.web, self.view.fa_question, self.view.color_red)

            # ctime = self.log_manager.stat(filename).st_ctime
            ctime = self.log_manager.stat(hash).st_ctime
            ctime = datetime.fromtimestamp(ctime)
            row.setText(Cols.created_at, ctime.strftime(self.view.time_format))

    def _create_local_log_row(self, filename, hash):
        row = self.view.attach_row_to_parent('log', filename)
        self._log_rows[hash] = row
        row.setFont(Cols.local, self.view.fontawesome)
        row.setFont(Cols.web, self.view.fontawesome)

        self.view.show_sync_status_icon(row, Cols.local, self.view.fa_check, self.view.color_green)
        self.view.show_sync_status_icon(row, Cols.web, self.view.fa_question, self.view.color_red)

        return row

    def delete_local_log(self, row: QTreeWidgetItem):
        hash = next(key for key, value in self._log_rows.items() if value == row)
        self.log_manager.delete_local(hash)
        del(self._log_rows[hash])
        row.parent().removeChild(row)

    async def log_synced(self, event: LogManager.EventType, hash: str, filename: str):
        if event == LogManager.EventType.log_synced:
            row: QTreeWidgetItem = self._log_rows.get(hash)
            if row is not None:
                self.view.show_sync_status_icon(row, Cols.web, self.view.fa_check, self.view.color_green)

        if event == LogManager.EventType.log_generated:
            new_row = self._create_local_log_row(filename, hash)
            ctime = self.log_manager.stat(hash).st_ctime
            ctime = datetime.fromtimestamp(ctime)
            new_row.setText(Cols.created_at, ctime.strftime(self.view.time_format))

            # Try to log event with inverterId and build hash that log was generated
            event = Event.new_raw_log("testInvId", "testUserId", self._build_hash, filename, hash)
            try:
                await self.activity_log.add(event)
            except DNSLookupError:
                self.set_offline(True)

            # Try to sync the file to the server
            if not self._is_offline:
                try:
                    await self.log_manager.sync_single_log(hash)
                    # Show it synced correctly
                    self.view.show_sync_status_icon(new_row, Cols.web, self.view.fa_check, self.view.color_green)
                except EndpointConnectionError:
                    self.set_offline(True)


    def set_offline(self, is_offline):
        self.activity_syncer.set_offline(is_offline)
        if is_offline:
            # TODO: Display offline warning in UI
            self._is_offline = True


class LogRenderer():
    @staticmethod
    def render_event(event: Event) -> str:
        if (event.type == Event.Type.load_param_file):
            return f"Param file {event.details['filename']} loaded."  # (Hash: {event.details['fileHash'][:8]})"
        elif (event.type == Event.Type.param_set):
            return f"Parameter \"{event.details['paramName']}\" set to \"{event.details['paramValue']}\"."
        elif (event.type == Event.Type.push_to_inverter):
            return "All settings pushed to inverter."
        else:
            return f"Unknown event type: {event.type}. Details: {event.details}"

