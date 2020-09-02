import json
import shutil
from datetime import datetime

import attr
from PyQt5.QtWidgets import QTreeWidgetItem, QFileDialog
from botocore.exceptions import EndpointConnectionError
from epyqlib.device import DeviceInterface
from epyqlib.tabs.files.activity_log import ActivityLog, Event
from epyqlib.tabs.files.activity_syncer import ActivitySyncer
from epyqlib.tabs.files.association_cache import AssociationCache
from epyqlib.tabs.files.aws_login_manager import AwsLoginManager
from epyqlib.tabs.files.bucket_manager import BucketManager
from epyqlib.tabs.files.files_manager import FilesManager
from epyqlib.tabs.files.filesview import Cols, get_values
from epyqlib.tabs.files.log_manager import LogManager, PendingLog
from epyqlib.tabs.files.sync_config import SyncConfig, Vars
from epyqlib.utils.twisted import errbackhook
from twisted.internet import reactor
from twisted.internet.error import DNSLookupError
from twisted.internet.task import deferLater
from typing import Dict

from .graphql import API, InverterNotFoundException


@attr.s(slots=True)
class AssociationMapping:
    association = attr.ib()
    row: QTreeWidgetItem = attr.ib()


class FilesController:
    _tag = "[Files Controller]"
    from epyqlib.tabs.files.filesview import FilesView

    def __init__(self, view: FilesView):
        self.view = view
        self.old_notes: str = ""
        self._last_sync: datetime = None

        self.sync_config = SyncConfig.get_instance()
        self.api = API(self.sync_config.get_env())

        self.activity_log = ActivityLog()
        self.activity_syncer = ActivitySyncer(self.activity_log, self.api)
        self.association_cache = AssociationCache.init(self.sync_config.cache_dir)
        self.aws_login_manager = AwsLoginManager.get_instance()
        self.bucket_manager = BucketManager()
        self.cache_manager = FilesManager(self.sync_config.cache_dir)
        self.log_manager = LogManager.init(self.sync_config.cache_dir)

        self._is_offline = self.sync_config.get(Vars.offline_mode) or False
        self._is_connected = False
        self._serial_number = None
        self._inverter_id = None
        self._build_hash = None

        self._device_interface = None

        self._inverter_id_lookup: Dict[str, str] = {}  # serial -> inverter_id

        self.associations: [str, AssociationMapping] = {}
        self._log_rows: Dict[str, QTreeWidgetItem] = {}

    def setup(self):
        self.aws_login_manager.register_listener(self.login_status_changed)

        if self.sync_config.get(Vars.offline_mode):
            print(
                f"{self._tag} 'offline_mode' flag set to true. Simulating offline mode."
            )
            self.set_offline(True)

        self.view.bind()
        self.view.populate_tree()
        self.view.initialize_ui()

        self.view.show_logged_out_warning()
        self._ensure_current_token()

        self.activity_log.register_listener(
            lambda event: self.view.add_log_line(LogRenderer.render_event(event))
        )
        self.activity_log.register_listener(self.activity_syncer.listener)

        self.log_manager.add_listener(self._on_new_pending_log)

        self._show_pending_logs()

    def _ensure_current_token(self):

        if not self.aws_login_manager.is_logged_in():
            return

        if not self.aws_login_manager.is_session_valid():
            try:
                self.aws_login_manager.refresh()

                # Make sure that using the refresh token worked
                if not self.aws_login_manager.is_logged_in():
                    return

            except (EndpointConnectionError, DNSLookupError):
                print(
                    f"{self._tag} Unable to login to AWS. Setting offline mode to true."
                )
                self.set_offline(True)
                return

        self.set_offline(False)
        self.api.set_id_token(self.aws_login_manager.get_id_token())
        self.periodically_refresh_token()
        self.view.show_logged_in_status(True, self.aws_login_manager.get_username())

    def device_interface_set(self, device_interface: DeviceInterface):
        self._device_interface = device_interface

    async def _read_info_from_inverter(self):
        """
        Read serial number and build hash from the inverter, and query the API for the inverterId for
        the given serial number
        """
        # Hasn't been set yet
        if self._device_interface is None:
            return

        # Don't do this if we already have this information
        if self._inverter_id is not None:
            return

        bus_status: DeviceInterface.TransmitStatus = (
            self._device_interface.get_connected_status()
        )
        # Appears you can never be "connected" to the offline inverter?
        if not (bus_status.connected and bus_status.transmitting):
            return

        # Only read serial number if it wasn't set through the UI (Will this ever happen if transmit is true?)
        if self._serial_number is None:
            self._serial_number = await self._device_interface.get_serial_number()
            self._build_hash = await self._device_interface.get_build_hash()

            self.log_manager.build_id = self._build_hash

        await self._get_id_for_serial_number(self._serial_number)

    ## Sync Info Methods
    def _set_sync_time(self) -> None:
        self._last_sync = datetime.now()

    ## Data fetching
    async def get_inverter_associations(self, serial_number: str):
        """
        :raises InverterNotFoundException
        """

        if self._is_offline:
            associations = self.association_cache.get_associations(serial_number) or []
        else:
            associations = await self.api.get_associations(serial_number)
            self.association_cache.put_associations(serial_number, associations)

        for association in associations:
            if association["file"] is None:
                print(
                    f"[Files Controller] WARNING: Association {association['id']} returned with null file associated"
                )
                continue

            key = association["id"] + association["file"]["id"]
            if key in self.associations:
                self.associations[
                    key
                ].association = (
                    association  # Update the association in case it's changed
                )
                row: QTreeWidgetItem = self.associations[key].row
                self.view.ensure_correct_parent_for_row(
                    row, association["file"]["type"]
                )
            else:
                row = self.view.attach_row_to_parent(
                    association["file"]["type"], association["file"]["filename"]
                )
                self.view.show_question_icon(row, Cols.local)
                self.view.show_check_icon(row, Cols.web)
                self.associations[
                    association["id"] + association["file"]["id"]
                ] = AssociationMapping(association, row)

            # Render either the new or updated association
            self.view.render_association_to_row(association, row)

        # to_remove = [key for key, value in self.associations.items() if (value.association not in associations)]
        to_remove = []
        for key, mapping in self.associations.items():
            if mapping.association not in associations:
                to_remove.append(key)
        for key in to_remove:
            map: AssociationMapping = self.associations[key]
            map.row.parent().removeChild(map.row)
            del self.associations[key]

        self.view.sort_grid_items()
        self._set_sync_time()
        self.view.show_sync_time(self._last_sync)

    async def _sync_files(self):
        missing_hashes = set()

        mapping: AssociationMapping
        for key, mapping in self.associations.items():

            hash = mapping.association["file"]["hash"]
            if self.cache_manager.has_hash(hash):
                self.view.show_check_icon(mapping.row, Cols.local)
            else:
                # Don't proactively cache raw log files
                if mapping.association["file"]["type"].lower() == "log":
                    self.view.show_cross_status_icon(mapping.row, Cols.local)
                    continue
                missing_hashes.add(hash)

        if len(missing_hashes) == 0:
            print(f"{self._tag} All files already hashed locally.")
            return

        if self._is_offline:
            print(
                f"{self._tag} Not syncing missing files because we are currently offline."
            )
            return

        # TODO: Figure out how to download multiple files at a time. Just trying to wrap in asyncio task fails.
        for hash in missing_hashes:
            await self.sync_file(hash)

    async def sync_file(self, hash):
        await self.download_file(hash)

        mapping: AssociationMapping
        for mapping in self._get_mapping_for_hash(hash):
            self.view.show_check_icon(mapping.row, Cols.local)

    def _get_key_for_file_id(self, file_id: str):
        value: AssociationMapping
        return next(
            key
            for key, value in self.associations.items()
            if value.association["file"]["id"] == file_id
        )

    def _get_mapping_for_hash(self, hash: str) -> [AssociationMapping]:
        map: AssociationMapping
        return [
            map
            for map in self.associations.values()
            if map.association["file"]["hash"] == hash
        ]

    def get_hash_for_row(self, row: QTreeWidgetItem):
        return self._get_mapping_for_row(row).association["file"]["hash"]

    def _get_mapping_for_row(self, row: QTreeWidgetItem) -> AssociationMapping:
        try:
            return next(map for map in self.associations.values() if map.row == row)
        except StopIteration:
            return None

    def is_file_cached_locally(self, item: QTreeWidgetItem):
        hash = self._get_mapping_for_row(item).association["file"]["hash"]
        return self.cache_manager.has_hash(hash)

    async def download_file_for_row(self, row: QTreeWidgetItem):
        await self.download_file(
            self._get_mapping_for_row(row).association["file"]["hash"]
        )

    async def download_file(self, hash: str):
        print(f"[Files Controller] Downloading missing file hash {hash}")
        filename = self.cache_manager.get_file_path(hash)
        await self.bucket_manager.download_file(hash, filename)
        return hash

    async def download_log(self, hash: str):
        print(f"[Files Controller] Downloading missing log hash {hash}")
        filename = self.cache_manager.get_file_path(hash)
        await self.bucket_manager.download_log(hash, filename)
        return hash

    ## Lifecycle events
    async def tab_selected(self):
        self.cache_manager.verify_cache()

        self.view.serial_number.setText(self._serial_number)
        self.view.disable_serial_number_input(
            not self._device_interface.on_offline_bus()
        )

        self._show_pending_logs()

        if self.aws_login_manager.is_logged_in():
            self._ensure_current_token()

            if not self.aws_login_manager.is_logged_in():
                self.view.show_logged_out_warning()
                return

            if self.sync_config.get(Vars.auto_sync):
                await self.sync_now()

    async def on_bus_status_changed(self):
        # Note: this gets called at least once for the offline inverter before on_offline_bus is
        # set to true. So do not trust that exclusively. (BSB 18Apr19)
        if self._device_interface is not None:
            bus_status: DeviceInterface.TransmitStatus = (
                self._device_interface.get_connected_status()
            )
            if bus_status.connected and bus_status.transmitting:
                await self.sync_now()

    ## UI Events
    async def login_clicked(self):
        try:
            self.aws_login_manager.show_login_window(self.view.files_grid)
        except EndpointConnectionError:
            print(f"{self._tag} Unable to login to AWS. Setting offline mode to true.")
            self.set_offline(True)

    def open_file(self, row: QTreeWidgetItem):
        file_hash = self._get_mapping_for_row(row).association["file"]["hash"]
        file_path = self.cache_manager.get_file_path(file_hash)
        import subprocess, os, sys

        if sys.platform.startswith("darwin"):
            subprocess.call(("open", file_path))
        elif os.name == "nt":  # For Windows
            # noinspection PyUnresolvedReferences
            os.startfile(file_path)
        elif os.name == "posix":  # For Linux, Mac, etc.
            subprocess.call(("xdg-open", file_path))

    async def save_file_as_clicked(self, item: QTreeWidgetItem = None):
        if item is None:
            item = self.view.files_grid.currentItem()

        map = self._get_mapping_for_row(item)
        hash = map.association["file"]["hash"]
        if hash not in self.cache_manager.hashes():
            await self.sync_file(hash)

        (destination, filter) = QFileDialog.getSaveFileName(
            parent=self.view.files_grid,
            caption="Pick location to save file",
            directory=map.association["file"]["filename"],
        )

        if destination != "":
            shutil.copy2(self.cache_manager.get_file_path(hash), destination)

    async def sync_now(self):
        self.view.show_inverter_error(None)

        if self._serial_number is None:
            if self._device_interface.on_offline_bus():
                return

            if not self._device_interface.get_connected_status().connected:
                self.view.show_inverter_error(
                    "Bus is disconnected. Unable to get Inverter Serial Number"
                )
                return

            # If InverterId is not set and we're connected, get inverter serial #
            await self._read_info_from_inverter()

            if self._serial_number is None:
                # If we still can't get it, bail out
                return

            self.view.serial_number.setText(self._serial_number)

        self._ensure_current_token()

        ## Verify that we actually are offline
        if self._is_offline:
            try:
                await self.api.test_connection()
                self.set_offline(False)
            except Exception:
                pass

        try:
            await self.get_inverter_associations(self._serial_number)
        except InverterNotFoundException:
            self.view.show_inverter_error("Error: Inverter ID not found.")
            return
        except DNSLookupError:
            self.set_offline(True)
            return

        try:
            await self._sync_pending_logs()
        except EndpointConnectionError:
            self.set_offline(True)

        await self._sync_files()
        if not self._is_offline:
            await self.api.unsubscribe()
            await self.api.subscribe(
                self.aws_login_manager.get_user_customer(), self.subscription_fired
            )

    async def sync_all(self):
        self.view.add_log_line("Starting to sync all associations for organization.")

        # Pull associations
        all_associations = await self.api.get_associations_for_customer()

        # Write fresh associations to cache
        for serial, association_list in all_associations.items():
            self.association_cache.put_associations(serial, association_list)

        # Fetch missing files
        for hash in self.association_cache.get_all_known_file_hashes():
            if not self.cache_manager.has_hash(hash):
                try:
                    await self.download_file(hash)
                except Exception:
                    self.view.add_log_error_line(
                        f"Error caching file {hash}. See epyq.log for details."
                    )

        self.view.add_log_line("Completed syncing all associations for organization.")

    async def subscription_fired(self, action, payload):
        if action == "associationCreated":
            await self.show_new_association(payload["id"], payload["file"]["id"])
            print(
                f"{self._tag} Received association action {action}: {json.dumps(payload)}"
            )
            return
        elif action == "associationDeleted":
            key = self._get_key_for_file_id(payload["file"]["id"])
            self.view.remove_row(self.associations[key].row)
            del self.associations[key]
            return

        if "id" not in payload:
            raise Exception(
                f"ERROR: Unable to handle file subscription message."
                f"Payload doesn't contain file id.\n{json.dumps(payload, indent=2)}"
            )

        key = self._get_key_for_file_id(payload["id"])

        if action == "fileUpdated":
            map: AssociationMapping = self.associations[key]
            map.association["file"].update(payload)
            self.view.render_association_to_row(map.association, map.row)

        if action == "fileDeleted":
            self.view.remove_row(self.associations[key].row)
            del self.associations[key]

        value: AssociationMapping
        new_associations = [
            value.association for key, value in self.associations.items()
        ]

        self.association_cache.put_associations(self._serial_number, new_associations)

    async def show_new_association(self, association_id: str, file_id: str):
        association = await self.api.get_association(association_id, file_id)

        row = self.view.attach_row_to_parent(
            association["file"]["type"], association["file"]["filename"]
        )
        self.view.show_question_icon(row, Cols.local)
        self.view.show_check_icon(row, Cols.web)
        self.associations[
            association["id"] + association["file"]["id"]
        ] = AssociationMapping(association, row)
        self.view.render_association_to_row(association, row)
        await self.sync_file(association["file"]["hash"])

    def file_item_clicked(self, item: QTreeWidgetItem, column: int):
        if item in get_values(self.view.section_headers):
            self.view.show_file_details(None)
            return

        file_mapping: AssociationMapping = self._get_mapping_for_row(item)

        association = file_mapping.association

        readonly_description = (
            association["file"]["owner"] == "epc"
            and not self.aws_login_manager._cognito_helper.is_user_epc()
        )
        readonly_description = readonly_description or self._is_offline

        if file_mapping is not None:
            self.view.show_file_details(file_mapping.association, readonly_description)

            if self._is_offline:
                self.view.description.setReadOnly(True)
                self.view.notes.setReadOnly(True)

        if item in self._log_rows.values():
            hash = next(key for key, value in self._log_rows.items() if value == item)

    async def send_dummy_param_event(self, row: QTreeWidgetItem):
        map = self._get_mapping_for_row(row)

        inverter_id = await self._get_id_for_serial_number(self._serial_number)

        file = map.association["file"]
        event = Event.new_load_param_file(
            inverter_id, "PlaceholderUser", file["id"], file["hash"], file["filename"]
        )
        await self.activity_log.add(event)

    ## Application events
    async def login_status_changed(self, logged_in: bool):
        self.view.btn_sync_now.setDisabled(not logged_in)

        if logged_in:
            self.api.set_id_token(self.aws_login_manager.get_id_token())
            self.view.show_logged_in_status(True, self.aws_login_manager.get_username())
            self.periodically_refresh_token()
            await self.sync_now()
        else:
            self.view.show_logged_out_warning()
            self.association_cache.clear()
            await self.api.unsubscribe()

    def periodically_refresh_token(self):
        def _refresh():
            print(f"{self._tag} Refreshing access token.")
            self.aws_login_manager.refresh(force=True)
            self.api.set_id_token(self.aws_login_manager.get_id_token())
            deferLater(
                reactor, self.aws_login_manager._cognito_helper._expires_in, _refresh
            )

        _refresh()

    ## Notes
    def set_original_notes(self, description: str, notes: str):
        description = description or ""
        notes = notes or ""
        self.old_notes = notes + description

    def notes_modified(self, new_desc: str, new_notes: str):
        new_notes = new_notes + new_desc

        return (len(self.old_notes) != len(new_notes)) or self.old_notes != new_notes

    async def save_notes(self, file_id: str, description: str, notes: str):
        print(f"{self._tag} Saving updated notes for file {file_id}")
        await self.api.set_file_notes(file_id, description, notes)
        self.set_original_notes(description, notes)

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
            create_file_response = await self.api.create_file(
                API.FileType.Log, log.filename, log.hash, notes
            )
            new_file_id = create_file_response["id"]

            inverter_id = await self._get_id_for_serial_number(log.serial_number)

            new_association = await self.api.create_association(
                inverter_id, new_file_id
            )

            ## Move UI row from pending to current
            row = self.view.pending_log_rows.pop(log.hash)
            self.view.show_check_icon(row, Cols.web)
            map = AssociationMapping(new_association, row)
            key = new_association["id"] + new_association["file"]["id"]

            self.associations[key] = map

            self.cache_manager.move_into_cache(
                self.log_manager.get_path_to_log(log.hash)
            )

            # Done processing. Remove pending and get next (if present)
            self.log_manager.remove_pending(log)
            log = self.log_manager.get_next_pending_log()

    async def _on_new_pending_log(self, log: PendingLog):
        inverter_id = await self._get_id_for_serial_number(log.serial_number)

        event = Event.new_raw_log(
            inverter_id,
            log.username,
            log.build_id,
            log.serial_number,
            log.filename,
            log.hash,
        )
        await self.activity_log.add(event)

        self._add_new_pending_log_row(log)
        await self._sync_pending_logs()

    def _show_pending_logs(self):
        for log in self.log_manager.get_pending_logs():
            if log.hash not in self.view.pending_log_rows:
                self._add_new_pending_log_row(log)

    def _add_new_pending_log_row(self, log: PendingLog):
        ctime = self.log_manager.stat(log.hash).st_ctime
        ctime = datetime.fromtimestamp(ctime)

        self.view.add_new_pending_log_row(log, ctime)

    def set_offline(self, is_offline):
        self.activity_syncer.set_offline(is_offline)
        self._is_offline = is_offline

        if is_offline:
            self.view.show_logged_in_status(False)
        else:
            self.view.show_logged_in_status(True, self.aws_login_manager.get_username())

    async def _get_id_for_serial_number(self, serial_number: str):
        if serial_number not in self._inverter_id_lookup and not self._is_offline:
            inverter = await self.api.get_inverter_by_serial(serial_number)
            self._inverter_id_lookup[serial_number] = inverter["id"]

        return self._inverter_id_lookup[serial_number]

    async def debug(self):
        self.api.ws_handler.clients[0].disconnect()


class LogRenderer:
    @staticmethod
    def render_event(event: Event) -> str:
        if event.type == Event.Type.load_param_file:
            return f"Param file {event.details['filename']} loaded."  # (Hash: {event.details['fileHash'][:8]})"
        elif event.type == Event.Type.new_raw_log:
            return f"New raw log generated. ({json.dumps(event.details)})"
        elif event.type == Event.Type.param_set:
            return f"Parameter \"{event.details['paramName']}\" set to \"{event.details['paramValue']}\"."
        elif event.type == Event.Type.push_to_inverter:
            return "All settings pushed to inverter."
        else:
            return f"Unknown event type: {event.type}. Details: {event.details}"
