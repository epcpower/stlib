from datetime import datetime

import attr
import twisted
from PyQt5.QtWidgets import QTreeWidgetItem, QFileDialog
from twisted.internet.defer import Deferred, ensureDeferred
from twisted.internet.interfaces import IDelayedCall

from epyqlib.tabs.files.bucket_manager import BucketManager
from epyqlib.tabs.files.cache_manager import CacheManager
from epyqlib.tabs.files.configuration import Configuration, Vars
from epyqlib.tabs.files.filesview import Cols, Relationships, get_values
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
        self.last_sync: datetime = None

        self.bucket_manager = BucketManager()
        self.cache_manager = CacheManager()
        self.log_manager = LogManager("logs")
        self.log_rows = {}
        self.configuration = Configuration()
        self.associations: [str, AssociationMapping] = {}

        self.sync_timer: IDelayedCall = None

    def setup(self):
        self.view.bind()
        self.view.populate_tree()
        self.view.setup_buttons()

        self._show_local_logs()

        self.view.chk_auto_sync.setChecked(self.configuration.get(Vars.auto_sync))


    ## Sync Info Methods
    def _set_sync_time(self) -> str:
        self.last_sync = datetime.now()
        return self.get_sync_time()

    def get_sync_time(self) -> str:
        return self.last_sync.strftime(self.view.time_format)

    ## Data fetching
    async def get_inverter_associations(self, inverter_id: str):
        associations = await self.api.get_associations(inverter_id)
        for association in associations:
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

        self._set_sync_time()
        self.view.lbl_last_sync.setText(f'Last sync at:{self.get_sync_time()}')

        return await self.sync_files()

    async def sync_files(self):
        missing_hashes = set()
        for key, mapping in self.associations.items():
            # mapping is of type AssociationMapping
            hash = mapping.association['file']['hash']
            if(not self.cache_manager.has_hash(hash)):
                missing_hashes.add(hash)

        if len(missing_hashes) == 0:
            print("All files already hashed locally.")
            return

        coroutines = [self.download_file(hash) for hash in missing_hashes]

        for coro in coroutines:
            await coro

        # result = await asyncio.gather(*coroutines)


    def render_association_to_row(self, association, row: QTreeWidgetItem):
        row.setText(Cols.filename, association['file']['filename'])
        row.setText(Cols.version, association['file']['version'])
        row.setText(Cols.notes, association['file']['hash'] or association['file']['notes'])

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

    ## Lifecycle events
    def tab_selected(self):
        if self.view.inverter_id.text() == '':
            self.view.inverter_id.setText('TestInv')

        if self.configuration.get(Vars.auto_sync):
            self.sync_and_schedule()

    ## UI Events
    def download_file_clicked(self):
        directory = QFileDialog.getExistingDirectory(parent=self.view.files_grid, caption='Pick location to download')
        print(f'[Filesview] Filename picked: {directory}')

    def auto_sync_checked(self):
        checked = self.view.chk_auto_sync.isChecked()
        self.configuration.set(Vars.auto_sync, checked)
        if checked:
            self.sync_and_schedule()
        else:
            if (self.sync_timer is not None):
                self.sync_timer.cancel()

    def sync_and_schedule(self):
        self.fetch_files(self.view.inverter_id.text())
        self.sync_timer = twisted.internet.reactor.callLater(300, self.sync_and_schedule)

    def sync_now_clicked(self):
        self.view.show_inverter_id_error(None)
        self.fetch_files(self.view.inverter_id.text())

    def file_item_clicked(self, item: QTreeWidgetItem, column: int):
        if (item in get_values(self.view.section_headers)):
            self.view.show_file_details(None)
        else:
            mapping: AssociationMapping = next(a for a in self.associations.values() if a.row == item)
            self.view.show_file_details(mapping.association)

    def fetch_files(self, inverter_id):
        deferred = ensureDeferred(self.get_inverter_associations(inverter_id))
        # deferred.addCallback(self.view.show_files)
        deferred.addErrback(self.inverter_error_handler)
        deferred.addErrback(show_error_dialog)

    def inverter_error_handler(self, error):
        if error.type is InverterNotFoundException:  # Twisted wraps errors in its own class
            self.view.show_inverter_id_error("Error: Inverter ID not found.")
        else:
            raise error


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

