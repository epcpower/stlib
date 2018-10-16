import logging
import os
import shutil

import epyqlib.busproxy
import epyqlib.device
import epyqlib.twisted.busproxy
import epyqlib.tests.common


def assert_device_ok(device):
    attributes = (
        'name',
        'ui',
    )

    for attribute in attributes:
        assert hasattr(device, attribute)


def test_epc(customer_device_path, qtbot):
    path = os.path.splitext(customer_device_path)[0] + '.ePC'
    shutil.move(customer_device_path, path)

    device = epyqlib.device.Device(
        file=path,
        node_id=247,
    )

    assert_device_ok(device)
    device.terminate()


def test_json(customer_device_path, qtbot):
    path = os.path.splitext(customer_device_path)[0] + '.json'
    shutil.move(customer_device_path, path)

    device = epyqlib.device.Device(
        file=path,
        node_id=247,
    )

    assert_device_ok(device)
    device.terminate()


def test_epz(qtbot, zipped_customer_device_path, tmpdir):
    path = os.path.join(tmpdir, 'customer.ePZ')

    shutil.move(
        zipped_customer_device_path,
        path,
    )

    device = epyqlib.device.Device(
        file=path,
        node_id=247,
    )

    assert_device_ok(device)
    device.terminate()


def test_zip(qtbot, zipped_customer_device_path, tmpdir):
    path = os.path.join(tmpdir, 'customer.zIP')

    shutil.move(
        zipped_customer_device_path,
        path,
    )

    device = epyqlib.device.Device(
        file=path,
        node_id=247,
    )

    assert_device_ok(device)
    device.terminate()
