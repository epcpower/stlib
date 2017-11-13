import PyQt5.QtCore

# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class NotFoundError(Exception):
    pass


class Signals(PyQt5.QtCore.QObject):
    child_added = PyQt5.QtCore.pyqtSignal('PyQt_PyObject', int)
    child_removed = PyQt5.QtCore.pyqtSignal(
        'PyQt_PyObject',
        'PyQt_PyObject',
        int,
    )


class TreeNode:
    def __init__(self, tx=False, parent=None, children=None):
        self.last = None

        self.tx = tx

        self.tree_parent = None
        self.set_parent(parent)

        self.pyqt_signals = Signals()

        # TODO: this isn't a good way to handle predefined children
        #       in an inherited class
        if children is None:
            if hasattr(self, 'children'):
                children = self.children

        if children is None:
                self.children = []
        else:
            children = self.children
            self.children = []
            for child in children:
                self.append_child(child)

    def set_parent(self, parent):
        self.tree_parent = parent
        if self.tree_parent is not None:
            self.tree_parent.append_child(self)

    def insert_child(self, i, child):
        self.children.insert(i, child)
        child.tree_parent = self
        self.pyqt_signals.child_added.emit(child, i)

    def append_child(self, child):
        self.children.append(child)
        child.tree_parent = self
        self.pyqt_signals.child_added.emit(child, len(self.children) - 1)

    def child_at_row(self, row):
        if row < len(self.children):
            return self.children[row]
        else:
            return None

    def row_of_child(self, child):
        for i, item in enumerate(self.children):
            if item is child:
                return i
        return -1

    def remove_child(self, row=None, child=None):
        if child is None:
            child = self.children[row]
        elif row is None:
            row = self.children.index(child)

        tree_parent = child.tree_parent

        child.parent = None
        child.tree_parent = None
        self.children.remove(child)

        self.pyqt_signals.child_removed.emit(tree_parent, child, row)

        return True

    def traverse(self, call_this, payload=None, internal_nodes=False):
        child = None
        for child in self.children:
            child.traverse(call_this, payload, internal_nodes=internal_nodes)

        if internal_nodes or child is None:
            call_this(self, payload)

    def leaves(self):
        leaves = []
        self.traverse(
            call_this=lambda node, payload: payload.append(node),
            payload=leaves,
            internal_nodes=False
        )

        return leaves

    def find_root(self):
        root = self

        while root.tree_parent is not None:
            root = root.tree_parent

        return root

    def __len__(self):
        return len(self.children)

    def nodes_by_attribute(self, attribute_value, attribute_name):
        def matches(node, matches):
            if not hasattr(node, attribute_name):
                return

            if getattr(node, attribute_name) == attribute_value:
                matches.add(node)

        nodes = set()
        self.traverse(
            call_this=matches,
            payload=nodes,
            internal_nodes=True
        )

        if len(nodes) == 0:
            raise NotFoundError(
                '''Attribute '{}' with value '{}' not found'''.format(
                    attribute_name,
                    attribute_value,
                )
            )

        return nodes


if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
