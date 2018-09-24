import logging

import pytest

import epyqlib.busproxy
import epyqlib.device
import epyqlib.twisted.busproxy
import epyqlib.tests.common


def test_range_override_hidden(qtbot):
    device = epyqlib.device.Device(
        file=epyqlib.tests.common.devices['customer'],
        node_id=247,
    )

    children = device.ui.findChildren(epyqlib.nvview.NvView)

    assert len(children) > 0

    for view in children:
        checkbox = view.ui.enforce_range_limits_check_box
        assert not checkbox.isVisibleTo(checkbox.parent())


@pytest.mark.factory
def test_range_override_visible(qtbot):
    device = epyqlib.device.Device(
        file=epyqlib.tests.common.devices['factory'],
        node_id=247,
    )

    children = device.ui.findChildren(epyqlib.nvview.NvView)

    assert len(children) > 0

    for view in children:
        checkbox = view.ui.enforce_range_limits_check_box
        assert checkbox.isVisibleTo(checkbox.parent())


@pytest.mark.factory
def test_secret_masked(qtbot):
    secret_mask = '<secret>'

    device = epyqlib.device.Device(
        file=epyqlib.tests.common.devices['factory'],
        node_id=247,
    )

    secret_nv = tuple(nv for nv in device.nvs.all_nv() if nv.secret)

    assert len(secret_nv) > 0
    for nv in secret_nv:
        nv.set_meta('1234', epyqlib.nv.MetaEnum.user_default)
        assert nv.fields.user_default == secret_mask
        nv.set_meta('1234', epyqlib.nv.MetaEnum.factory_default)
        assert nv.fields.factory_default == secret_mask
        nv.set_meta('1234', epyqlib.nv.MetaEnum.value)
        assert nv.fields.value == secret_mask


def logit(it):
    logging.debug('logit(): ({}) {}'.format(type(it), it))
