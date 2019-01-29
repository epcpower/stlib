from datetime import datetime, timedelta

import treq
import twisted
from PyQt5.QtWidgets import QTreeWidgetItem, QFileDialog
import attr
from twisted.internet.defer import Deferred, ensureDeferred
from twisted.internet.interfaces import IDelayedCall

from epyqlib.tabs.files.configuration import Configuration, Vars
from epyqlib.tabs.files.filesview import Cols, Relationships
from epyqlib.utils.twisted import errbackhook as show_error_dialog
from .graphql import API, InverterNotFoundException

@attr.s(slots=True)
class AssociationMapping():
    association = attr.ib()
    row: QTreeWidgetItem = attr.ib()


class FilesController:

    bucket_path = 'https://s3-us-west-2.amazonaws.com/epc-files-dev/public/firmware/'

    from epyqlib.tabs.files.filesview import FilesView
    def __init__(self, view: FilesView):
        self.view = view
        self.api = API()
        self.old_notes: str = None
        self.last_sync: datetime = None

        self.configuration = Configuration()
        self.associations: [str, AssociationMapping] = {}

        self.sync_timer: IDelayedCall = None

    def setup(self):
        self.view.bind()
        self.view.populate_tree()
        self.view.setup_buttons()
        self.view.chk_auto_sync.setChecked(self.configuration.get(Vars.auto_sync))

    ## Sync Info Methods
    def _set_sync_time(self) -> str:
        self.last_sync = datetime.now()
        return self.get_sync_time()

    def get_sync_time(self) -> str:
        return self.last_sync.strftime('%l:%M%p %m/%d')

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

    def render_association_to_row(self, association, row: QTreeWidgetItem):
        row.setText(Cols.filename, association['file']['filename'])
        row.setText(Cols.version, association['file']['version'])
        row.setText(Cols.notes, association['file']['notes'])

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

    async def download_file(self, filename: str, destination: str):
        outf = open(destination, 'wb')

        deferred: Deferred = treq.get(self.bucket_path + filename)
        deferred.addCallback(treq.collect, outf.write)
        deferred.addBoth(lambda _: outf.close())
        return await deferred

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
        m: AssociationMapping = next(a for a in self.associations.values() if a.row == item)
        self.view.show_file_details(m.association)
        # m.row.setText(Cols.notes, m.association['id'])

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
