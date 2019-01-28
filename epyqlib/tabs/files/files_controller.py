from datetime import datetime, timedelta

import treq
from PyQt5.QtWidgets import QTreeWidgetItem, QFileDialog
from twisted.internet.defer import Deferred, ensureDeferred

from epyqlib.utils.twisted import errbackhook as show_error_dialog
from .graphql import API, InverterNotFoundException


class FilesController:

    bucket_path = 'https://s3-us-west-2.amazonaws.com/epc-files-dev/public/firmware/'

    from epyqlib.tabs.files.filesview import FilesView
    def __init__(self, view: FilesView):
        self.view = view
        self.api = API()
        self.old_notes: str = None
        self.last_sync: datetime = None

    def setup(self):
        self.view.bind()
        self.view.populate_tree()
        self.view.setup_buttons()

    ## Sync Info Methods
    def set_sync_time(self) -> str:
        self.last_sync = datetime.now()
        return self.get_sync_time()

    def get_sync_time(self) -> str:
        return self.last_sync.strftime('%l:%M%p %m/%d')

    def should_sync(self):
        if self.last_sync is None:
            return True

        sync_time = self.last_sync + timedelta(minutes=5)
        return sync_time < datetime.now()

    ## Data fetching
    async def get_inverter_associations(self, inverter_id: str):
        groups = {
            'parameter': [],
            'firmware': [],
            'fault_logs': [],
            'other': []
        }

        associations = await self.api.get_associations(inverter_id)
        for association in associations:
            type = association['file']['type'].lower()
            if groups.get(type) is None:
                groups[type] = []
            groups[type].append(association)

        self.set_sync_time()
        return groups

    async def download_file(self, filename: str, destination: str):
        outf = open(destination, 'wb')

        deferred: Deferred = treq.get(self.bucket_path + filename)
        deferred.addCallback(treq.collect, outf.write)
        deferred.addBoth(lambda _: outf.close())
        return await deferred

    ## Lifecycle events
    def tab_selected(self):
        if self.should_sync():
            self.fetch_files('TestInv')

    ## UI Events
    def download_file_clicked(self):
        directory = QFileDialog.getExistingDirectory(parent=self.view.files_grid, caption='Pick location to download')
        print(f'[Filesview] Filename picked: {directory}')

    def auto_sync_checked(self):
        checked = self.view.chk_auto_sync.isChecked()
        self.view.btn_sync_now.setDisabled(checked)

    def sync_now_clicked(self):
        self.view.show_inverter_id_error(None)
        self.fetch_files(self.view.inverter_id.text())

    def file_item_clicked(self, item: QTreeWidgetItem, column: int):
        if hasattr(item, 'obj'):
            self.view.show_file_details(item.obj)

    def fetch_files(self, inverter_id):
        deferred = ensureDeferred(self.get_inverter_associations(inverter_id))
        deferred.addCallback(self.view.show_files)
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
