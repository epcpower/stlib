import attr
import graham

import epyqlib.attrsmodel


@graham.schemify(tag='node')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@epyqlib.utils.qt.pyqtify_passthrough_properties(
    original='node',
    field_names=(
        'name',
    ),
)
@attr.s(hash=False)
class Node(epyqlib.treenode.TreeNode):
    name = epyqlib.attrsmodel.create_name_attribute()
    epyqlib.attrsmodel.attrib(
        attribute=name,

    )

    node = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=node,
        no_column=True,
    )

    children = attr.ib(
        default=attr.Factory(list),
    )

    uuid = epyqlib.attrsmodel.attr_uuid(no_column=True)

    def __attrs_post_init__(self):
        super().__init__()

    @classmethod
    def build(cls, name, node, local_results=[], child_results=[]):
        results = [
            Result(node=node, message=result)
            for result in local_results
        ]

        node = cls(
            name=name,
            node=node,
        )

        for child in child_results + results:
            node.append_child(child)

        return node

    def can_delete(self, node=None):
        return False

    def check(self):
        return None

    def can_drop_on(self, node):
        return False

    all_addable_types = epyqlib.attrsmodel.empty_all_addable_types
    addable_types = epyqlib.attrsmodel.empty_addable_types
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move


@graham.schemify(tag='result')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Result(epyqlib.treenode.TreeNode):
    node = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=node,
        no_column=True,
    )

    message = epyqlib.attrsmodel.create_str_attribute()

    children = attr.ib(
        default=attr.Factory(list),
    )

    uuid = epyqlib.attrsmodel.attr_uuid(no_column=True)

    def __attrs_post_init__(self):
        super().__init__()

    def can_delete(self, node=None):
        return False

    def check(self):
        return None

    def can_drop_on(self, node):
        return False

    all_addable_types = epyqlib.attrsmodel.empty_all_addable_types
    addable_types = epyqlib.attrsmodel.empty_addable_types
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move


Root = epyqlib.attrsmodel.Root(
    default_name='Check Results',
    valid_types=(
        Node,
        Result,
    ),
)


types = epyqlib.attrsmodel.Types(
    types=(
        Root,
        Node,
        Result,
    ),
)


# TODO: CAMPid 943896754217967154269254167
def merge(name, *types):
    return tuple((x, name) for x in types)


columns = epyqlib.attrsmodel.columns(
    merge('name', Node),
    merge('message', Result),
)


# TODO: CAMPid 075454679961754906124539691347967
@attr.s
class ReferencedUuidNotifier:
    changed = epyqlib.utils.qt.Signal('PyQt_PyObject')

    view = attr.ib(default=None)
    selection_model = attr.ib(default=None)

    def __attrs_post_init__(self):
        if self.view is not None:
            self.set_view(self.view)

    def set_view(self, view):
        self.disconnect_view()

        self.view = view
        self.selection_model = self.view.selectionModel()
        if self.selection_model is not None:
            self.selection_model.currentChanged.connect(
                self.current_changed,
            )

    def disconnect_view(self):
        if self.selection_model is not None:
            self.selection_model.currentChanged.disconnect(
                self.current_changed,
            )
        self.view = None
        self.selection_model = None

    def current_changed(self, current, previous):
        if not current.isValid():
            return

        index = epyqlib.utils.qt.resolve_index_to_model(
            index=current,
        )
        model = index.data(epyqlib.utils.qt.UserRoles.attrs_model)
        node = model.node_from_index(index)
        self.changed.emit(node.node.uuid)
