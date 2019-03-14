import arrow
import attr
import graham
import marshmallow

import epyqlib.attrsmodel
import epyqlib.treenode


def create_blank(model=None):
    fault_log = FaultLog(model=model)
    _post_load(fault_log)

    return fault_log


def _post_load(fault_log, root=None):
    if root is None:
        root = Root()

    if fault_log.model is None:
        fault_log.model = epyqlib.attrsmodel.Model(
            root=root,
            columns=columns,
        )


@graham.schemify(tag='event')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Event(epyqlib.treenode.TreeNode):
    time = attr.ib(
        converter=arrow.get,
        default=attr.Factory(arrow.utcnow),
    )
    graham.attrib(
        attribute=time,
        field=marshmallow.fields.DateTime(),
    )
    epyqlib.attrsmodel.attrib(
        attribute=time,
        editable=False,
    )

    value = attr.ib(
        converter=epyqlib.attrsmodel.to_int_or_none,
        default=None,
    )
    epyqlib.attrsmodel.attrib(
        attribute=value,
        editable=False,
    )

    description = attr.ib(
        converter=str,
        default=None,
    )
    epyqlib.attrsmodel.attrib(
        attribute=description,
        editable=False,
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    @staticmethod
    def can_delete(node=None):
        return False

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


Root = epyqlib.attrsmodel.Root(
    default_name='Event Log',
    valid_types=(Event,),
)

types = epyqlib.attrsmodel.Types(
    types=(
        Root,
        Event,
    ),
)


@attr.s
class FaultLog:
    model = attr.ib(default=None)

    def connect(
            self,
            process_frames,
            process_message_names,
            nv_frames,
            nv_message_names,
    ):
        process_signals = []
        for name in process_message_names:
                frame = process_frames.frame_by_name(name)
                process_signals.extend(frame.signals)

        for signal in process_signals:
            description = ':'.join((signal.frame.name, signal.name))

            def changed(value, *, signal=signal, description=description):
                self.changed(
                    value=value,
                    signal=signal,
                    description=description,
                )

            signal.value_changed.connect(changed)

        nv_signals = [
            nv
            for nv in nv_frames.all_nv()
            if nv.frame.mux_name in nv_message_names
        ]

        for signal in nv_signals:
            description = ':'.join((signal.frame.mux_name, signal.name))

            def changed(value, *, signal=signal, description=description):
                self.changed(
                    value=value,
                    signal=signal,
                    description=description,
                )

            signal.value_changed.connect(changed)

    def changed(self, signal, value, description):
        event = Event(
            value=value,
            description=description,
        )
        self.model.root.append_child(event)


# TODO: CAMPid 943896754217967154269254167
def merge(name, *types):
    return tuple((x, name) for x in types)


columns = epyqlib.attrsmodel.columns(
    merge('time', Event),
    merge('value', Event),
    merge('description', Event),
    merge('uuid', *types.types.values()),
)
