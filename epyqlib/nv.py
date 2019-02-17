#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import logging
logger = logging.getLogger(__name__)

import attr
import collections
import can
import contextlib
import decimal
import enum
from epyqlib.abstractcolumns import AbstractColumns
import epyqlib.attrsmodel
import epyqlib.canneo
import epyqlib.pm.valuesetmodel
import epyqlib.twisted.busproxy
import epyqlib.twisted.nvs
import epyqlib.utils.general
import epyqlib.utils.qt
import epyqlib.utils.twisted
import functools
import itertools
import json
import epyqlib.pyqabstractitemmodel
from epyqlib.treenode import TreeNode
from PyQt5.QtCore import (Qt, QVariant, QModelIndex, pyqtSignal, pyqtSlot)
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
import textwrap
import time
import twisted.internet.defer
import twisted.internet.task
import weakref

# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class Columns(AbstractColumns):
    _members = [
        'name',
        'read_only',
        'factory',
        'value',
        'saturate',
        'reset',
        'clear',
        'scratch',
        'user_default',
        'factory_default',
        'minimum',
        'maximum',
        'comment',
    ]

Columns.indexes = Columns.indexes()


diffable_columns = [
    Columns.indexes.value,
    Columns.indexes.scratch,
    Columns.indexes.user_default,
    Columns.indexes.factory_default,
    Columns.indexes.minimum,
    Columns.indexes.maximum,
]

diff_highlight = QtGui.QColor('orange')
diff_highlight.setAlphaF(0.4)

reference_highlight = QtGui.QColor('green')
reference_highlight.setAlphaF(0.2)


class NoNv(Exception):
    pass


class NotFoundError(Exception):
    pass


class TooManyMetaSignalsError(Exception):
    pass


@attr.s
class Configuration:
    set_frame = attr.ib()
    status_frame = attr.ib()
    to_nv_command = attr.ib()
    to_nv_status = attr.ib()
    read_write_signal = attr.ib()
    read_write_status_signal = attr.ib()
    meta_signal = attr.ib()


configurations = {
    'original': Configuration(
        set_frame='CommandSetNVParam',
        status_frame='StatusNVParam',
        to_nv_command='SaveToEE_command',
        to_nv_status='SaveToEE_status',
        read_write_signal='ReadParam_command',
        read_write_status_signal='ReadParam_status',
        meta_signal=None,
    ),
    'j1939': Configuration(
        set_frame='ParameterQuery',
        status_frame='ParameterResponse',
        to_nv_command='SaveToEE_command',
        to_nv_status='SaveToEE_status',
        read_write_signal='ReadParam_command',
        read_write_status_signal = 'ReadParam_status',
        meta_signal='Meta',
    )
}


@attr.s(hash=True)
class Group(TreeNode):
    fields = attr.ib(default=attr.Factory(Columns))

    def __attrs_post_init__(self):
        super().__init__()


class MetaEnum(epyqlib.utils.general.AutoNumberIntEnum):
    value = 0
    user_default = 1
    factory_default = 2
    minimum = 3
    maximum = 4


meta_limits = (MetaEnum.minimum, MetaEnum.maximum)
meta_limits_first = (
    meta_limits + tuple(sorted(set(MetaEnum) - set(meta_limits)))
)

MetaEnum.non_value = tuple(sorted(set(MetaEnum) - {MetaEnum.value}))

meta_column_indexes = tuple(
    getattr(Columns.indexes, meta.name)
    for meta in MetaEnum
)


dynamic_column_indexes_by_meta = {
    MetaEnum.value: [
        Columns.indexes.value,
        Columns.indexes.saturate,
        Columns.indexes.reset,
        Columns.indexes.clear,
    ],
    **{
        meta: [getattr(Columns.indexes, meta.name)]
        for meta in MetaEnum.non_value
    },
}


column_index_by_meta = {
    meta: getattr(Columns.indexes, meta.name)
    for meta in MetaEnum
}


@attr.s
@epyqlib.utils.general.enumerated_attrs(MetaEnum, default=None)
class Meta:
    pass


class Nvs(TreeNode, epyqlib.canneo.QtCanListener):
    changed = epyqlib.utils.qt.Signal(
        TreeNode,
        int,
        TreeNode,
        int,
        list,
    )
    activity_started = epyqlib.utils.qt.Signal(str)
    activity_ended = epyqlib.utils.qt.Signal(str)

    def __init__(self, neo, bus=None, stop_cyclic=None, start_cyclic=None,
                 configuration=None, hierarchy=None, metas=(MetaEnum.value,),
                 access_level_path=None, access_password_path=None,
                 parent=None):
        TreeNode.__init__(self)
        epyqlib.canneo.QtCanListener.__init__(self, parent=parent)

        if configuration is None:
            configuration = 'original'

        self.stop_cyclic = stop_cyclic
        self.start_cyclic = start_cyclic
        self.configuration = configurations[configuration]

        from twisted.internet import reactor
        self.protocol = epyqlib.twisted.nvs.Protocol()
        self.transport = epyqlib.twisted.busproxy.BusProxy(
            protocol=self.protocol,
            reactor=reactor,
            bus=bus)

        self.bus = bus
        self.neo = neo
        self.message_received_signal.connect(self.message_received)

        self.access_level_node = None
        if access_level_path is not None:
            self.access_level_node = self.neo.signal_by_path(*access_level_path)
            self.access_level_node.write_only = True

        self.password_node = None
        if access_password_path is not None:
            self.password_node = self.neo.signal_by_path(*access_password_path)

        self.set_frames = [f for f in self.neo.frames
                       if f.name == self.configuration.set_frame]
        try:
            self.set_frames = self.set_frames[0]
        except IndexError:
            # TODO: custom error
            raise NoNv()

        self.set_frames = self.set_frames.multiplex_frames
        self.status_frames = [
            f for f in self.neo.frames
            if f.name == self.configuration.status_frame
        ][0].multiplex_frames

        self.save_frame = None
        self.save_signal = None
        self.save_value = None
        self.confirm_save_frame = None
        self.confirm_save_multiplex_value = None
        self.confirm_save_signal = None
        self.confirm_save_value = None
        for frame in self.set_frames.values():
            for signal in frame.signals:
                if signal.name == self.configuration.to_nv_command:
                    for key, value in signal.enumeration.items():
                        if value == 'Enable':
                            self.save_frame = frame
                            self.save_signal = signal
                            self.save_value = key

        save_status_name = self.configuration.to_nv_status
        for frame in self.status_frames.values():
            for signal in frame.signals:
                if signal.name == save_status_name:
                    for key, value in signal.enumeration.items():
                        if value == 'Enable':
                            self.confirm_save_frame = frame
                            self.confirm_save_multiplex_value = signal.multiplex
                            self.confirm_save_signal = signal
                            self.confirm_save_value = key

        if self.confirm_save_frame is None:
            raise Exception(
                "'{}' signal not found in NV parameter interface".format(
                    save_status_name
                ))

        self.nv_by_path = {}
        # TODO: kind of an ugly manual way to connect this
        self.status_frames[0].set_frame = self.set_frames[0]
        for value, frame in self.set_frames.items():
            signals = [s for s in frame.signals]
            signals = [s for s in signals if s.multiplex is not 'Multiplexor']
            signals = [
                s for s in signals
                if s.name not in [
                    self.configuration.read_write_signal,
                    self.configuration.meta_signal,
                    '{}_MUX'.format(self.configuration.set_frame)
                ]
            ]

            if len(signals) > 0:
                def ignore_timeout(failure):
                    acceptable_errors = (
                        epyqlib.twisted.nvs.RequestTimeoutError,
                        epyqlib.twisted.nvs.SendFailedError,
                        epyqlib.twisted.nvs.CanceledError,
                    )
                    if failure.type in acceptable_errors:
                        return None

                    return epyqlib.utils.twisted.errbackhook(
                        failure)

                def send(signals=None, all_signals=signals):
                    if signals is None:
                        signals = all_signals

                    d = twisted.internet.defer.Deferred()
                    d.callback(None)

                    for enumerator in metas:
                        d.addCallback(lambda _: self.protocol.write_multiple(
                            nv_signals=signals,
                            meta=enumerator,
                            priority=epyqlib.twisted.nvs.Priority.user
                        ))
                    d.addErrback(ignore_timeout)

                frame._send.connect(send)

            frame.parameter_signals = []
            for nv in signals:
                if nv.name not in [self.configuration.to_nv_command]:
                    self.nv_by_path[nv.signal_path()] = nv
                    frame.parameter_signals.append(nv)
                    nv.changed.connect(self.changed)

                try:
                    nv.frame.status_frame = self.status_frames[value]
                except KeyError:
                    raise Exception('Unable to find: {}:{} with mux id {}'.format(
                        self.configuration.status_frame,
                        frame.mux_name,
                        frame.mux_value,
                    ))

                self.status_frames[value].set_frame = nv.frame

                search = (s for s in self.status_frames[value].signals
                          if s.start_bit == nv.start_bit)
                try:
                    nv.status_signal, = search
                except ValueError:
                    raise Exception(
                        'NV status signal not found for {}:{}'.format(nv.frame.mux_name, nv.name)
                    )
                nv.status_signal.set_signal = nv


        unreferenced_paths = set(self.nv_by_path)
        if hierarchy is not None:
            def handle(children, tree_parent,
                       unreferenced_paths=unreferenced_paths):
                unreferenced_groups = []
                logger.info(children, tree_parent)
                for child in children:
                    logger.info(child)
                    if isinstance(child, dict):
                        group = Group(
                            fields=Columns(
                                name=child['name'],
                            )
                        )
                        tree_parent.append_child(group)
                        logger.info('added group: {}'.format(group.fields.name))
                        if child.get('unreferenced'):
                            unreferenced_groups.append(group)
                        else:

                            unreferenced_groups.extend(handle(
                                children=child.get('children', ()),
                                tree_parent=group
                            ))
                    else:
                        path = ('ParameterQuery',) + tuple(child)
                        if path in unreferenced_paths:
                            tree_parent.append_child(self.nv_by_path[path])
                            unreferenced_paths.discard(path)
                        elif path not in self.nv_by_path:
                            logger.info('Unknown parameter referenced: {}'
                                  .format(path))
                        else:
                            raise Exception('Attempted to put parameter in '
                                            'multiple groups: {}'.format(path))

                return tuple(g for g in unreferenced_groups if g is not None)

            unreferenced_groups = handle(children=hierarchy['children'],
                                      tree_parent=self)

            logger.info('\\/ \\/ \\/ unreferenced parameter paths')
            logger.info(
                json.dumps(
                    tuple(p[1:] for p in sorted(unreferenced_paths)),
                    indent=4
                )
            )
            logger.info('/\\ /\\ /\\ unreferenced parameter paths')
        else:
            unreferenced_groups = (self,)

        for group in unreferenced_groups:
            for path in unreferenced_paths:
                group.append_child(self.nv_by_path[path])

        def remove_empty_groups(node):
            if isinstance(node, Group) and len(node.children) == 0:
                node.tree_parent.remove_child(child=node)
            else:
                for child in node.children:
                    remove_empty_groups(child)

        remove_empty_groups(self)

        duplicate_names = set()
        found_names = set()
        for child in self.all_nv():
            name = child.fields.name
            if name not in found_names:
                found_names.add(name)
            else:
                duplicate_names.add(name)

        if len(duplicate_names) > 0:
            raise Exception('Duplicate NV parameter names found: {}'.format(
                ', '.join(duplicate_names)))

        missing_read_write_signals = []

        for i, set_frame in self.set_frames.items():
            status_frame = self.status_frames[i]
            try:
                set_frame.command_signal, = (
                    s
                    for s in set_frame.signals
                    if s.name == self.configuration.read_write_signal
                )
            except ValueError:
                missing_read_write_signals.append('{}:{}:{}'.format(
                    set_frame.name,
                    set_frame.mux_name,
                    self.configuration.read_write_signal,
                ))

            try:
                status_frame.command_signal, = (
                    s
                    for s in status_frame.signals
                    if s.name == self.configuration.read_write_status_signal
                )
            except ValueError:
                missing_read_write_signals.append('{}:{}:{}'.format(
                    status_frame.name,
                    status_frame.mux_name,
                    self.configuration.read_write_status_signal,
                ))

        if len(missing_read_write_signals) > 0:
            raise Exception('Unable to find needed signals: {}'.format(
                ', '.join(missing_read_write_signals),
            ))

        self.cyclic_reader = CyclicReader(
            nvs=self.all_nv(),
            read_call=self.read_all_from_device,
            metas=metas,
        )

    def terminate(self):
        self.cancel_cyclic_read_all()

    def set_stale(self):
        for nv in self.all_nv():
            nv.set_stale()

    def set_bus(self, bus):
        self.transport.set_bus(bus=bus)
        self.bus = bus

    def all_nv(self):
        def visit(node, all):
            if isinstance(node, Nv):
                all.add(node)
            else:
                for child in node.children:
                    visit(child, all)

        all = set()
        visit(self, all)

        return all

    def names(self):
        return '\n'.join([n.fields.name for n in self.all_nv()])

    def write_all_to_device(
            self,
            only_these=None,
            values=(),
            callback=None,
            meta=None,
            background=False,
    ):
        return self._read_write_all(
            read=False,
            only_these=only_these,
            values=values,
            callback=callback,
            meta=meta,
            background=background,
        )

    def read_all_from_device(
            self,
            only_these=None,
            callback=None,
            meta=None,
            background=False,
    ):
        return self._read_write_all(
            read=True,
            only_these=only_these,
            callback=callback,
            meta=meta,
            background=background,
        )

    def _read_write_all(
            self,
            read,
            only_these=None,
            values=(),
            callback=None,
            meta=None,
            background=False,
    ):
        if meta is None:
            meta = meta_limits_first

        activity = ('Reading from device' if read
                    else 'Writing to device')

        if not background:
            self.activity_started.emit('{}...'.format(activity))
        d = twisted.internet.defer.Deferred()
        d.callback(None)

        def handle_frame(frame, signals, enumerator):
            if read:
                d.addCallback(
                    lambda _, enumerator=enumerator: self.protocol.read_multiple(
                        nv_signals=signals,
                        meta=enumerator,
                        priority=epyqlib.twisted.nvs.Priority.user,
                        passive=True,
                        all_values=True,
                    )
                )
            elif frame.read_write.min <= 0:
                not_none_signals = {}
                for signal in signals:
                    values_key = (signal, enumerator)
                    if values_key in values:
                        value = values[values_key]
                    elif enumerator == MetaEnum.value:
                        value = signal.value
                    else:
                        value = getattr(signal.meta, enumerator.name).value

                    if value is not None:
                        not_none_signals[signal] = value

                if len(not_none_signals) == 0:
                    return

                d.addCallback(
                    lambda _, enumerator=enumerator, not_none_signals=not_none_signals: self.protocol.write_multiple(
                        nv_signals=not_none_signals,
                        meta=enumerator,
                        priority=epyqlib.twisted.nvs.Priority.user,
                        passive=True,
                        all_values=True,
                    )
                )
            else:
                return

            if callback is not None:
                d.addCallback(callback)

        if only_these is None:
            only_these = self.all_nv()

        frames = set(nv.frame for nv in only_these)
        for frame in frames:
            signals = tuple(nv for nv in only_these
                            if nv.frame is frame)

            frame.update_from_signals()
            for enumerator in meta:
                handle_frame(
                    frame=frame,
                    signals=signals,
                    enumerator=enumerator,
                )

        if not background:
            d.addCallback(epyqlib.utils.twisted.detour_result,
                          self.activity_ended.emit,
                          'Finished {}...'.format(activity.lower()))
            d.addErrback(epyqlib.utils.twisted.detour_result,
                         self.activity_ended.emit,
                         'Failed while {}...'.format(activity.lower()))

        return d

    def message_received(self, msg):
        if (msg.arbitration_id == self.status_frames[0].id
                and msg.id_type == self.status_frames[0].extended):
            multiplex_message, multiplex_value =\
                self.neo.get_multiplex(msg)

            if multiplex_message is None:
                return

            if multiplex_value is not None and multiplex_message in self.status_frames.values():
                values = multiplex_message.unpack(msg.data, only_return=True)

                if multiplex_message.meta_signal is not None:
                    meta = epyqlib.nv.MetaEnum(
                        values[multiplex_message.meta_signal],
                    )
                    if meta != epyqlib.nv.MetaEnum.value:
                        return

                multiplex_message.unpack(msg.data)
                # multiplex_message.frame.update_canneo_from_matrix_signals()

                status_signals = multiplex_message.signals
                sort_key = lambda s: s.start_bit
                status_signals = sorted(status_signals, key=sort_key)
                set_signals = multiplex_message.set_frame.signals
                set_signals = sorted(set_signals, key=sort_key)
                for status, set in zip(status_signals, set_signals):
                    set.set_value(status.value)

    def unique(self):
        # TODO: actually identify the object
        return '-'

    def to_dict(self, include_secrets=False):
        d = {}
        for child in self.all_nv():
            if include_secrets or not child.secret:
                d[child.fields.name] = child.scratch.get_human_value(
                    for_file=True,
                )

        return d

    def to_value_set(self, include_secrets=False):
        value_set = epyqlib.pm.valuesetmodel.create_blank()

        for child in self.all_nv():
            if not child.secret:
                parameter = epyqlib.pm.valuesetmodel.Parameter(
                    name=child.fields.name,
                    value=child.get_human_value(for_file=True),
                    user_default=child.meta.user_default.get_human_value(
                        for_file=True
                    ),
                    factory_default=child.meta.factory_default.get_human_value(
                        for_file=True
                    ),
                    minimum=child.meta.minimum.get_human_value(for_file=True),
                    maximum=child.meta.maximum.get_human_value(for_file=True),
                    readable=not child.is_write_only(),
                    writable=not child.is_read_only(),
                )
            elif include_secrets:
                def format_float(value):
                    was_secret = child.secret
                    child.secret = False
                    result = child.format_float(value=value, for_file=True)
                    child.secret = was_secret

                    return result

                parameter = epyqlib.pm.valuesetmodel.Parameter(
                    name=child.fields.name,
                    value=format_float(value=0),
                    user_default=format_float(value=0),
                    factory_default=format_float(value=0),
                    minimum=format_float(value=child.min),
                    maximum=format_float(value=child.max),
                )
            else:
                continue

            value_set.model.root.append_child(parameter)

        return value_set

    def from_dict(self, d):
        only_in_file = list(d.keys())

        for child in self.all_nv():
            value = d.get(child.fields.name, None)
            if value is not None:
                child.scratch.set_human_value(decimal.Decimal(value))
                child.fields.scratch = child.scratch.full_string
                only_in_file.remove(child.fields.name)
            else:
                logger.info("Nv value named '{}' not found when loading from dict"
                      .format(child.fields.name))

        for name in only_in_file:
            logger.info("Unrecognized NV value named '{}' found when loading "
                  "from dict".format(name))

    def from_value_set(self, value_set):
        parameter_nodes = value_set.model.root.nodes_by_filter(
            filter=lambda node: isinstance(
                node,
                epyqlib.pm.valuesetmodel.Parameter,
            ),
        )
        only_in_file = {
            parameter.name
            for parameter in parameter_nodes
        }
        only_in_file = {
            (name, meta)
            for name, meta in itertools.product(
                only_in_file,
                epyqlib.nv.MetaEnum,
            )
        }

        d = collections.defaultdict(list)
        for parameter in parameter_nodes:
            d[parameter.name].append(parameter)

        for child in self.all_nv():
            name = child.fields.name

            parameters = d.get(name, [])

            not_found_format = (
                "Nv value named '{}' ({{}}) not found when loading "
                "from value set".format(name)
            )

            if len(parameters) == 1:
                parameter, = parameters

                for meta in MetaEnum:
                    only_in_file.discard((name, meta))

                if parameter.value is not None:
                    child.set_human_value(parameter.value)
                else:
                    logger.info(not_found_format.format('value'))

                for meta in MetaEnum:
                    if meta == MetaEnum.value:
                        continue

                    v = getattr(parameter, meta.name)
                    if v is not None:
                        child.set_meta(
                            data=v,
                            meta=meta,
                            check_range=False,
                        )
                    else:
                        logger.info(not_found_format.format(meta.name))
            elif len(parameters) > 1:
                logger.info(
                    "Nv value named '{}' occurred {} times when loading "
                    "from value set".format(name, len(parameters)),
                )
            else:
                logger.info(
                    "Nv value named '{}' not found when loading from "
                    "value set".format(name),
                )

        for name, meta in sorted(only_in_file):
            logger.info("Unrecognized NV value named '{}' ({}) found when loading "
                  "from value set".format(name, meta.name))

    def defaults_from_dict(
            self,
            d,
            default_metas=(MetaEnum.factory_default,),
    ):
        only_in_file = list(d.keys())

        for child in self.all_nv():
            value = d.get(child.fields.name, None)
            if value is not None:
                for meta in default_metas:
                    child.set_meta(
                        data=value,
                        meta=meta,
                    )
                    self.changed.emit(
                        child, meta_column_indexes[meta],
                        child, meta_column_indexes[meta],
                        [Qt.DisplayRole],
                    )
                only_in_file.remove(child.fields.name)
            else:
                logger.info("Nv value named '{}' not found when loading from dict"
                      .format(child.fields.name))

        for name in only_in_file:
            logger.info("Unrecognized NV value named '{}' found when loading to "
                  "defaults from dict".format(name))

    def module_to_nv(self):
        self.activity_started.emit('Requested save to NV...')
        self.save_signal.set_value(self.save_value)
        self.save_frame.update_from_signals()
        d = self.protocol.write(
            nv_signal=self.save_signal,
            passive=True,
            meta=MetaEnum.value,
        )
        d.addBoth(
            epyqlib.utils.twisted.detour_result,
            self.module_to_nv_off,
        )
        d.addCallback(self._module_to_nv_response)
        d.addErrback(
            epyqlib.utils.twisted.detour_result,
            self._module_to_nv_response,
            (0, None),
        )
        d.addErrback(epyqlib.utils.twisted.errbackhook)

    def module_to_nv_off(self):
        self.save_signal.set_value(not self.save_value)
        d = self.protocol.write(
            nv_signal=self.save_signal,
            passive=True,
            meta=MetaEnum.value,
        )
        d.addErrback(lambda _: None)

    def _module_to_nv_response(self, result):
        if result[0] == 1:
            feedback = 'Save to NV confirmed'
        else:
            feedback = 'Save to NV failed ({})'.format(
                self.confirm_save_signal.full_string
            )

        self.activity_ended.emit(feedback)

    def logger_set_frames(self):
        frames = [frame for frame in self.set_frames.values()
                  if frame.mux_name.startswith('LoggerChunk')]
        frames.sort(key=lambda frame: frame.mux_name)

        return frames

    def signal_from_names(self, frame_name, value_name):
        frame = [f for f in self.set_frames.values()
                 if f.mux_name == frame_name]

        try:
            frame, = frame
        except ValueError as e:
            raise NotFoundError(
                'Frame not found: {}'.format(frame_name)) from e

        signal = [s for s in frame.signals
                   if s.name == value_name]

        try:
            signal, = signal
        except ValueError as e:
            raise NotFoundError(
                'Signal not found: {}:{}'.format(frame_name, value_name)) from e

        return signal

    def cyclic_read_all(self):
        self.cyclic_reader.start()

    def cancel_cyclic_read_all(self):
        self.cyclic_reader.cancel()


@attr.s
class CyclicReader:
    nvs = attr.ib()
    read_call = attr.ib()
    metas = attr.ib()
    pause_requests = attr.ib(factory=weakref.WeakSet)
    _deferred = attr.ib(init=False, default=None)

    def start(self):
        self._deferred = self._cyclic_read_all()

    def cancel(self):
        if self._deferred is not None:
            self._deferred.cancel()
            self._deferred = None

    @contextlib.contextmanager
    def pause_manager(self, id):
        self.pause(id)
        try:
            yield
        finally:
            self.unpause(id)

    def pause(self, id):
        self.pause_requests.add(id)

    def unpause(self, id):
        self.pause_requests.discard(id)

    @epyqlib.utils.twisted.ensure_deferred
    @epyqlib.utils.twisted.errback_dialog
    @epyqlib.utils.twisted.ignore_cancelled
    async def _cyclic_read_all(self):
        x = collections.defaultdict(list)
        for nv in self.nvs:
            x[nv.frame].append(nv)

        while True:
            for meta in self.metas:
                for frame, nvs in x.items():
                    try:
                        while len(self.pause_requests) > 0:
                            await epyqlib.utils.twisted.sleep(0.250)

                        await epyqlib.utils.twisted.sleep(0.02)

                        d, _ = await self.read_call(
                            only_these=nvs,
                            background=True,
                            meta=(meta,),
                        )
                    except (
                            epyqlib.twisted.nvs.CanceledError,
                            epyqlib.twisted.nvs.SendFailedError,
                    ):
                        continue

                    # TODO: CAMPid 0347987975t427567139419439349
                    for nv in nvs:
                        if not nv.status_signal.write_only:
                            value = d[nv.status_signal]
                            nv.set_meta(value, meta=meta, check_range=False)
                            nv.set_from_device(
                                column=getattr(Columns.indexes, meta.name),
                            )


class Nv(epyqlib.canneo.Signal, TreeNode):
    changed = epyqlib.utils.qt.Signal(
        TreeNode,
        int,
        TreeNode,
        int,
        list,
    )

    def __init__(
        self,
        signal,
        frame,
        parent=None,
        meta=None,
        meta_value=None,
        base=True,
        for_remote_data=True,
    ):
        epyqlib.canneo.Signal.__init__(self, signal=signal, frame=frame,
                                    parent=parent)
        TreeNode.__init__(self)

        if meta_value is None:
            self.meta_value = MetaEnum.value
        else:
            self.meta_value = meta_value

        default = self.default_value
        if default is None:
            default = 0

        if self.frame is not None:
            self.factory = '<factory>' in (self.comment + self.frame.comment)

        self.reset_value = None

        self.clear(mark_modified=False)

        self.fields = Columns(
            value=self.full_string,
            comment=self.comment,
        )
        if self.frame is not None:
            self.fields.name = '{}:{}'.format(self.frame.mux_name, self.name)

        if meta is None:
            self.meta = Meta()
        else:
            self.meta = meta

        self.base = base
        self.for_remote_data = for_remote_data

        if self.base:
            metas = (
                MetaEnum.user_default,
                MetaEnum.factory_default,
                MetaEnum.minimum,
                MetaEnum.maximum,
            )
            for meta in metas:
                setattr(
                    self.meta,
                    meta.name,
                    Nv(signal, frame=None, meta=self.meta, meta_value=meta, base=False)
                )

            for meta in metas:
                getattr(self.meta, meta.name).set_value(None)

                setattr(
                    self.fields,
                    meta.name,
                    getattr(self.meta, meta.name).full_string,
                )

            self.scratch = Nv(
                signal,
                frame=None,
                meta=self.meta,
                base=False,
                for_remote_data=False,
            )
            self.scratch.set_value(None)
            self.fields.scratch = self.scratch.full_string

        self.write_only = False

        self._stale = self.for_remote_data

        self.stale_role = Qt.ForegroundRole

    def _changed(self, column_start=None, column_end=None, roles=(
            Columns.indexes.value,)):
        if column_start is None:
            column_start = Columns.indexes.value
        if column_end is None:
            column_end = column_start

        self.changed.emit(
            self, column_start,
            self, column_end,
            list(roles),
        )

    def set_from_user(self):
        pass

    def set_from_device(self, column):
        self._set_stale(stale=False, column=column)

    def stale(self, column):
        subnode = self._get_signal_for_column(column)

        if subnode is None:
            return False

        return subnode._stale

    def _set_stale(self, stale, column):
        subnode = self._get_signal_for_column(column)
        was_stale = subnode._stale

        subnode._stale = stale

        if was_stale != subnode._stale:
            self._changed(column, column, roles=[self.stale_role])

    def set_stale(self):
        for column in Columns.indexes:
            subnode = self._get_signal_for_column(column)

            if subnode is not None and subnode.for_remote_data:
                self._set_stale(stale=True, column=column)

    def _get_signal_for_column(self, column):
        if not self.base:
            raise Exception('This should only be called on the base signal')

        if column == Columns.indexes.value:
            return self

        if column == Columns.indexes.scratch:
            return self.scratch

        column_name = Columns().index_from_attribute(column)

        return getattr(self.meta, column_name, None)

    def get_meta_signal(self, meta):
        if meta == MetaEnum.value:
            return self

        return getattr(self.meta, meta.name)

    def get_human_value(self, for_file=False, column=None):
        if column is None:
            column = Columns.indexes.value

        if column == Columns.indexes.scratch:
            signal = self.scratch
        else:
            column_name = Columns().index_from_attribute(column)

            signal = self.get_meta_signal(getattr(MetaEnum, column_name))

        if signal is self:
            return super().get_human_value(for_file=for_file)

        return signal.get_human_value(
            for_file=for_file,
            column=Columns.indexes.value,
        )

    def signal_path(self):
        return self.frame.signal_path() + (self.name,)

    def can_be_saturated(self, meta=MetaEnum.value):
        signal = self.get_meta_signal(meta)

        if signal.value is None:
            return False

        return signal.to_human(signal.value) != signal.saturation_value()

    def saturate(self, meta=MetaEnum.value):
        signal = self.get_meta_signal(meta)

        if not signal.can_be_saturated():
            return

        self.set_meta(signal.saturation_value(), meta=meta, mark_modified=True)

    def saturation_value(self):
        if self.value is None:
            return None

        s = self.to_human(self.value)

        if self.meta.minimum.value is not None:
            s = max(self.to_human(self.meta.minimum.value), s)

        if self.meta.maximum.value is not None:
            s = min(self.to_human(self.meta.maximum.value), s)

        return s

    def can_be_reset(self, meta=MetaEnum.value):
        signal = self.get_meta_signal(meta)
        return signal.reset_value != signal.value

    def reset(self, meta=MetaEnum.value):
        signal = self.get_meta_signal(meta)

        if not signal.can_be_reset():
            return

        self.set_meta(signal.reset_value, meta=meta)

    def check_value(self, value, force=False, check_range=False):
        min_max = {MetaEnum.minimum, MetaEnum.maximum}

        extras = {}

        if self.meta is not None:
            if self.meta.minimum.value is None or self.meta_value in min_max:
                extras['minimum'] = self.to_human(self.raw_minimum)
            else:
                extras['minimum'] = self.meta.minimum.to_human(
                    self.meta.minimum.value,
                )

            if self.meta.maximum.value is None or self.meta_value in min_max:
                extras['maximum'] = self.to_human(self.raw_maximum)
            else:
                extras['maximum'] = self.meta.maximum.to_human(
                    self.meta.maximum.value,
                )

        return super().check_value(
            value=value,
            check_range=check_range,
            **extras,
        )

    def set_value(self, value, force=False, check_range=False):
        ok = self.check_value(
            value=value,
            check_range=check_range,
        )
        if not ok:
            return False

        self.reset_value = value

        min_max = {MetaEnum.minimum, MetaEnum.maximum}

        if self.meta is not None:
            extras = {}
            if self.meta.minimum.value is None or self.meta_value in min_max:
                extras['minimum'] = self.to_human(self.raw_minimum)
            else:
                extras['minimum'] = self.meta.minimum.to_human(
                    self.meta.minimum.value,
                )

            if self.meta.maximum.value is None or self.meta_value in min_max:
                extras['maximum'] = self.to_human(self.raw_maximum)
            else:
                extras['maximum'] = self.meta.maximum.to_human(
                    self.meta.maximum.value,
                )

        super().set_value(
            value=value,
            force=force,
            check_range=check_range,
            **extras,
        )
        self.fields.value = self.full_string
        self._changed()

    def check_data(self, data, check_range=True):
        try:
            if data is None:
                return self.check_value(data)
            else:
                return self.check_human_value(data, check_range=check_range)
        except ValueError:
            return False

        return True

    def set_data(self, data, mark_modified=False, check_range=True):
        if not self.check_data(data=data, check_range=check_range):
            return False

        # self.fields.value = value
        reset_value = self.reset_value
        try:
            if data is None:
                self.set_value(data)
            else:
                self.set_human_value(data, check_range=check_range)
        except ValueError:
            return False
        finally:
            if mark_modified:
                self.reset_value = reset_value
        self.fields.value = self.full_string

        return True

    def check_meta(self, data, meta, *args, **kwargs):
        if meta == MetaEnum.value:
            extras = {}
            if 'check_range' in kwargs:
                extras['check_range'] = kwargs['check_range']
            return self.check_data(data, *args, **extras)

        meta_signal = getattr(self.meta, meta.name)

        return meta_signal.check_data(
            data=data,
            *args,
            **kwargs,
        )

    def set_meta(self, data, meta, *args, **kwargs):
        if data is not None:
            result = self.check_meta(data, meta, *args, **kwargs)
            if not result:
                return result

        if meta == MetaEnum.value:
            return self.set_data(data=data, *args, **kwargs)

        meta_signal = getattr(self.meta, meta.name)

        result = meta_signal.set_data(
            data=data,
            *args,
            **kwargs,
        )
        setattr(self.fields, meta.name, meta_signal.full_string)

        return result

    def can_be_cleared(self, meta=MetaEnum.value):
        signal = self.get_meta_signal(meta)

        return signal.value is not None

    def clear(self, mark_modified=True, meta=MetaEnum.value):
        signal = self.get_meta_signal(meta)

        if not signal.can_be_cleared():
            return

        self.set_meta(None, meta=meta, mark_modified=mark_modified)
        if hasattr(signal, 'status_signal'):
            signal.status_signal.set_value(None)

    def is_factory(self):
        return self.factory

    def is_read_only(self):
        return self.frame.read_write.min > 0 or self.is_summary

    def is_write_only(self):
        return self.frame.read_write.max < 1

    def unique(self):
        # TODO: make it more unique
        return str(self.fields.name) + '__'


class Frame(epyqlib.canneo.Frame, TreeNode):
    _send = epyqlib.utils.qt.Signal(tuple)

    def __init__(self, message=None, tx=False, frame=None,
                 multiplex_value=None, signal_class=Nv, mux_frame=None,
                 parent=None, **kwargs):
        epyqlib.canneo.Frame.__init__(self, frame=frame,
                                   multiplex_value=multiplex_value,
                                   signal_class=signal_class,
                                   set_value_to_default=False,
                                   mux_frame=mux_frame,
                                   parent=parent,
                                   **kwargs)
        TreeNode.__init__(self, parent)

        meta_signals = [
            signal
            for signal in self.signals
            if signal.name == 'Meta'
        ]

        if len(meta_signals) == 0:
            self.meta_signal = None
        else:
            try:
                self.meta_signal, = meta_signals
            except ValueError as e:
                raise TooManyMetaSignalsError(
                    'Too many meta signals in {}:{}'.format(self.name, self.mux_name),
                ) from e

        for signal in self.signals:
            if signal.name in ("ReadParam_command", "ReadParam_status"):
                self.read_write = signal
                break

        for signal in self.signals:
            if signal.name.endswith("_MUX"):
                self.mux = signal
                break

    def signal_path(self):
        if self.mux_name is None:
            return self.name,
        else:
            return self.name, self.mux_name

    def update_from_signals(self, for_read=False, data=None, function=None,
                            only_return=False):
        return super().update_from_signals(
            data=data,
            function=function,
            only_return=only_return,
        )

    def send_now(self, signals):
        self._send.emit(signals)


@attr.s
class Icon:
    character = attr.ib()
    check = attr.ib()
    font = attr.ib(QtGui.QFont('fontawesome'))


@attr.s
class TransactionAction:
    only_these = attr.ib()
    values = attr.ib()
    callback = attr.ib()
    meta = attr.ib()


class NvModel(epyqlib.pyqabstractitemmodel.PyQAbstractItemModel):
    activity_started = pyqtSignal(str)
    activity_ended = pyqtSignal(str)

    def __init__(self, root, parent=None):
        editable_columns = Columns.fill(False)
        for enumerator in MetaEnum:
            setattr(editable_columns, enumerator.name, True)
        editable_columns.scratch = True

        epyqlib.pyqabstractitemmodel.PyQAbstractItemModel.__init__(
                self, root=root, editable_columns=editable_columns,
                alignment=Qt.AlignVCenter | Qt.AlignLeft, parent=parent)

        self.check_range = True

        self.headers = Columns(name='Name',
                               value='Active',
                               scratch='Scratch',
                               minimum='Min',
                               maximum='Max',
                               user_default='User Default',
                               factory_default='Factory Default',
                               comment='Comment')

        root.activity_started.connect(self.activity_started)
        root.activity_ended.connect(self.activity_ended)

        self.icons = Columns(
            reset=Icon(character='\uf0e2', check='can_be_reset'),
            clear=Icon(character='\uf057', check='can_be_cleared'),
            saturate=Icon(character='\uf066', check='can_be_saturated'),
            factory=Icon(character='\uf084', check='is_factory'),
            read_only=Icon(character='\uf023', check='is_read_only')
        )

        self.meta_columns = {
            getattr(Columns.indexes, enumerator.name)
            for enumerator in MetaEnum
        }

        self.icon_columns = set(
            index
            for index, icon in zip(self.icons.indexes, self.icons)
            if icon is not None
        )

        self.force_action_decorations = False

        self.role_functions[epyqlib.utils.qt.UserRoles.sort] = (
            self.data_sort
        )

        self.transaction_actions = None

        palette = QtGui.QPalette(QtWidgets.QWidget().palette())
        color = QtGui.QColor(palette.windowText().color())
        color.setAlphaF(0.3)
        self.stale_foreground = color

    def all_nv(self):
        return self.root.all_nv()

    def flags(self, index):
        flags = super().flags(index)
        node = self.node_from_index(index)

        if not isinstance(node, epyqlib.nv.Nv) or node.is_read_only():
            flags &= ~Qt.ItemIsEditable

        return flags

    def data_sort(self, index):
        node = self.node_from_index(index)

        return '{}{}'.format(
            'a' if isinstance(node, Group) else 'b',
            self.data_display(index),
        )

    def data_font(self, index):
        icon = self.icons[index.column()]
        if icon is not None:
            return icon.font

        return None

    def data_display(self, index):
        node = self.node_from_index(index)
        column = index.column()
        icon = self.icons[column]
        if icon is not None:
            if self.force_action_decorations:
                return icon.character
            else:
                if isinstance(node, epyqlib.nv.Nv):
                    check = getattr(node, icon.check)
                    if check():
                        return icon.character

        super_result = super().data_display(index)

        return super_result

    def data_foreground(self, index):
        node = self.node_from_index(index)

        if isinstance(node, Nv):
            if node.stale(index.column()):
                return self.stale_foreground

        return None

    def data_tool_tip(self, index):
        if index.column() == Columns.indexes.saturate:
            node = self.node_from_index(index)
            if isinstance(node, epyqlib.nv.Nv):
                if node.can_be_saturated():
                    return node.format_strings(
                        value=node.from_human(node.saturation_value()))[0]
        if index.column() == Columns.indexes.reset:
            node = self.node_from_index(index)
            if isinstance(node, epyqlib.nv.Nv):
                if node.can_be_reset():
                    return node.format_strings(value=node.reset_value)[0]
        elif index.column() == Columns.indexes.comment:
            node = self.node_from_index(index)
            if isinstance(node, epyqlib.nv.Nv):
                comment = node.fields.comment
                if comment is None:
                    comment = ''
                return '\n'.join(textwrap.wrap(comment, 60))

    def dynamic_columns_changed(
            self,
            node,
            columns=None,
            meta=MetaEnum.value,
            roles=(Qt.DisplayRole,),
    ):
        if columns is None:
            columns = dynamic_column_indexes_by_meta[meta]

        for column in columns:
            self.changed(node, column, node, column, roles)

    def saturate_node(self, node, meta=MetaEnum.value):
        node.saturate(meta=meta)
        self.dynamic_columns_changed(node, meta=meta)

    def reset_node(self, node, meta=MetaEnum.value):
        node.reset(meta=meta)
        self.dynamic_columns_changed(node, meta=meta)

    def clear_node(self, node, meta=MetaEnum.value):
        node.clear(meta=meta)
        self.dynamic_columns_changed(node, meta=meta)

    def check_range_changed(self, state):
        self.check_range = state == Qt.Checked

    def start_transaction(self):
        self.transaction_actions = collections.defaultdict(list)

    def submit_transaction(self):
        d = twisted.internet.defer.ensureDeferred(self._submit_transaction())
        d.addErrback(epyqlib.utils.twisted.catch_expected)
        d.addErrback(epyqlib.utils.twisted.errbackhook)

    async def _submit_transaction(self):
        try:
            for meta, actions in self.transaction_actions.items():
                values = {}
                callback = None
                nodes = set()

                for action in actions:
                    values.update(action.values)

                    if action.callback is not None:
                        if callback is None:
                            callback = action.callback
                        elif action.callback != callback:
                            raise Exception('ack')

                    if action.meta is not None:
                        if meta is None:
                            meta = action.meta
                        elif action.meta != meta:
                            raise Exception('ack')

                    nodes = nodes.union(action.only_these)

                if callback is not None:
                    callback = functools.partial(
                        callback,
                        only_these=nodes,
                    )

                await self.root.write_all_to_device(
                    only_these=nodes,
                    values=values,
                    callback=callback,
                    meta=(meta,),
                    # TODO: maybe not really...
                    background=True,
                )
        finally:
            self.transaction_done()

    def cancel_transaction(self):
        self.transaction_actions = None

    def transaction_done(self):
        self.transaction_actions = None

    @contextlib.asynccontextmanager
    async def transaction_manager(self):
        self.start_transaction()
        try:
            yield
        except:
            self.cancel_transaction()
            raise

        await self._submit_transaction()

    def setData(self, index, data, role=None):
        column = index.column()

        if data == '':
            data = None

        if column == Columns.indexes.scratch:
            if role == Qt.EditRole:
                node = self.node_from_index(index)
                valid = node.check_data(
                    data,
                    check_range=self.check_range,
                )
                if valid:
                    node.scratch.set_human_value(data, check_range=self.check_range)
                    node.fields.scratch = node.scratch.full_string
        elif column in self.meta_columns:
            if role == Qt.EditRole:
                node = self.node_from_index(index)
                meta = getattr(
                    MetaEnum,
                    Columns().index_from_attribute(column),
                )
                valid = node.check_meta(
                    data,
                    meta=meta,
                    check_range=self.check_range,
                )

                if valid:
                    nodes = (node,)

                    if self.transaction_actions is None:
                        callback = functools.partial(
                            self.update_signals,
                            only_these=nodes,
                        )

                        d = self.root.write_all_to_device(
                            only_these=nodes,
                            values={(node, meta): node.calc_human_value(data)},
                            callback=callback,
                            meta=(meta,),
                        )
                        d.addErrback(epyqlib.utils.twisted.catch_expected)
                        d.addErrback(epyqlib.utils.twisted.errbackhook)
                    else:
                        self.transaction_actions[meta].append(
                            TransactionAction(
                                only_these=nodes,
                                values={(node, meta): node.calc_human_value(data)},
                                callback=self.update_signals,
                                meta=meta,
                            ),
                        )

        return False

    # TODO: CAMPid 0347987975t427567139419439349
    def update_signals(self, arg, only_these):
        d, meta = arg
        model = self

        frame = next(iter(d)).frame

        signals = set(only_these) & set(frame.set_frame.parameter_signals)

        for signal in signals:
            if signal.status_signal in d:
                if not signal.status_signal.write_only:
                    value = d[signal.status_signal]
                    signal.set_meta(value, meta=meta, check_range=False)
                    signal.set_from_device(
                        column=getattr(Columns.indexes, meta.name),
                    )

        for signal in frame.set_frame.parameter_signals:
            QtWidgets.QApplication.instance().processEvents()

            model.dynamic_columns_changed(
                signal,
                columns=(getattr(epyqlib.nv.Columns.indexes, meta.name),)
            )

    @pyqtSlot()
    def module_to_nv(self):
        # TODO: monitor and report success/failure of write
        self.root.module_to_nv()

    @pyqtSlot()
    def write_to_module(self):
        # TODO: device or module!?!?
        d = self.root.write_all_to_device()
        d.addErrback(epyqlib.utils.twisted.catch_expected)
        d.addErrback(epyqlib.utils.twisted.errbackhook)

    @pyqtSlot()
    def read_from_module(self):
        d = self.root.read_all_from_device()
        d.addErrback(epyqlib.utils.twisted.catch_expected)
        d.addErrback(epyqlib.utils.twisted.errbackhook)

    @pyqtSlot()
    def write_to_file(self, parent=None):
        filters = [
            ('EPC Parameters', ['epp']),
            ('All Files', ['*'])
        ]
        filename = epyqlib.utils.qt.file_dialog(
            filters, save=True, parent=parent)

        if filename is None:
            return

        if len(filename) > 0:
            with open(filename, 'w') as file:
                d = self.root.to_dict()
                s = json.dumps(d, sort_keys=True, indent=4)
                file.write(s)
                file.write('\n')

                self.activity_ended.emit(
                    'Saved to "{}"'.format(filename)
                )

    @pyqtSlot()
    def write_to_value_set_file(self, parent=None):
        fields = attr.fields(epyqlib.pm.valuesetmodel.ValueSet)
        filters = fields.filters.default
        path = epyqlib.utils.qt.file_dialog(
            filters,
            save=True,
            parent=parent,
        )

        if path is not None:
            value_set = self.root.to_value_set()
            value_set.path = path

            try:
                value_set.save()
            except epyqlib.pm.valuesetmodel.SaveCancelled:
                message = 'Save cancelled'
            else:
                message = 'Saved to "{}"'.format(path)

            self.activity_ended.emit(message)

    @pyqtSlot()
    def read_from_file(self, parent=None):
        filters = [
            ('EPC Parameters', ['epp']),
            ('All Files', ['*'])
        ]
        filename = epyqlib.utils.qt.file_dialog(filters, parent=parent)

        if filename is None:
            return

        if len(filename) > 0:
            with open(filename, 'r') as file:
                s = file.read()
                d = json.loads(s)
                self.root.from_dict(d)

                self.activity_ended.emit(
                    'Loaded from "{}"'.format(filename)
                )

    @contextlib.contextmanager
    def activity_manager(self, start, success, failure):
        self.activity_started.emit(start)

        try:
            yield
        except:
            message = failure
            raise
        else:
            message = success
        finally:
            self.activity_ended.emit(message)

    def read_from_value_set_file(self, parent=None):
        d = twisted.internet.defer.ensureDeferred(
            self._read_from_value_set_file(parent=parent),
        )
        d.addErrback(epyqlib.utils.twisted.catch_expected)
        d.addErrback(epyqlib.utils.twisted.errbackhook)

        return d

    async def _read_from_value_set_file(self, parent=None):
        fields = attr.fields(epyqlib.pm.valuesetmodel.ValueSet)
        filters = fields.filters.default
        # filters = epyqlib.pm.valuesetmodel.ValueSet.filters.default
        path = epyqlib.utils.qt.file_dialog(filters, parent=parent)

        if path is None:
            return

        value_set = epyqlib.pm.valuesetmodel.loadp(path)

        parameter_nodes = value_set.model.root.nodes_by_filter(
            filter=lambda node: isinstance(
                node,
                epyqlib.pm.valuesetmodel.Parameter,
            ),
        )
        only_in_file = {
            parameter.name
            for parameter in parameter_nodes
        }
        only_in_file = {
            (name, meta)
            for name, meta in itertools.product(
                only_in_file,
                epyqlib.nv.MetaEnum,
            )
        }

        d = collections.defaultdict(list)
        for parameter in parameter_nodes:
            d[parameter.name].append(parameter)

        skip_nodes = (
            self.root.access_level_node,
            self.root.password_node,
        )

        @contextlib.asynccontextmanager
        async def cm():
            with self.activity_manager(
                start='Loading value set from "{}"'.format(path),
                success='Loaded value set from "{}"'.format(path),
                failure='Failed to load value set from "{}"'.format(path),
            ):
                with self.root.cyclic_reader.pause_manager(self):
                    async with self.transaction_manager():
                        yield

        async with cm():
            for child in self.root.all_nv():
                if child in skip_nodes:
                    continue

                name = child.fields.name

                parameters = d.get(name, [])

                not_found_format = (
                    "Nv value named '{}' ({{}}) not found when loading "
                    "from value set".format(name)
                )

                if len(parameters) == 1:
                    parameter, = parameters

                    index = self.index_from_node(child)

                    for meta in MetaEnum:
                        only_in_file.discard((name, meta))

                        v = getattr(parameter, meta.name)
                        if v is not None:
                            self.setData(
                                index.siblingAtColumn(
                                    getattr(Columns.indexes, meta.name),
                                ),
                                v,
                                Qt.EditRole,
                            )
                        else:
                            logger.info(not_found_format.format(meta.name))
                elif len(parameters) > 1:
                    logger.info(
                        "Nv value named '{}' occurred {} times when loading "
                        "from value set".format(name, len(parameters)),
                    )
                else:
                    logger.info(
                        "Nv value named '{}' not found when loading from "
                        "value set".format(name),
                    )

            for name, meta in sorted(only_in_file):
                logger.info("Unrecognized NV value named '{}' ({}) found when loading "
                      "from value set".format(name, meta.name))


if __name__ == '__main__':
    import sys

    logger.info('No script functionality here')
    sys.exit(1)     # non-zero is a failure
