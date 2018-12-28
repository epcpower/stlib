import io
import textwrap

from PyQt5 import QtWidgets
import PyQt5.uic

import epyqlib.filesview


def test_init(qtbot):
    view = epyqlib.filesview.FilesView()
    qtbot.add_widget(view)

    view.show()
    qtbot.wait_for_window_shown(widget=view)

    assert view.parent() is None
    assert isinstance(view.ui, epyqlib.filesview.Ui)
    assert not hasattr(view.ui, 'something')


def test_build(qtbot):
    view = epyqlib.filesview.FilesView.build()
    qtbot.add_widget(view)

    view.show()
    qtbot.wait_for_window_shown(widget=view)

    assert view.parent() is None
    assert isinstance(view.ui, epyqlib.filesview.Ui)
    assert hasattr(view.ui, 'something')


def test_qt_build(qtbot):
    widget = QtWidgets.QWidget()
    qtbot.add_widget(widget)

    view = epyqlib.filesview.FilesView.qt_build(parent=widget)
    qtbot.add_widget(view)

    view.show()
    qtbot.wait_for_window_shown(widget=view)

    assert view.parent() is widget
    assert isinstance(view.ui, epyqlib.filesview.Ui)
    assert hasattr(view.ui, 'something')


def test_from_ui(qtbot):
    ui_src = io.StringIO(textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <ui version="4.0">
     <class>Form</class>
     <widget class="QWidget" name="Form">
      <property name="geometry">
       <rect>
        <x>0</x>
        <y>0</y>
        <width>400</width>
        <height>300</height>
       </rect>
      </property>
      <property name="windowTitle">
       <string>Form</string>
      </property>
      <layout class="QGridLayout" name="gridLayout">
       <item row="0" column="0">
        <widget class="FilesViewQtBuilder" name="widget" native="true"/>
       </item>
      </layout>
     </widget>
     <customwidgets>
      <customwidget>
       <class>FilesViewQtBuilder</class>
       <extends>QWidget</extends>
       <header>epyqlib.filesview</header>
      </customwidget>
     </customwidgets>
     <resources/>
     <connections/>
    </ui>
    """))

    widget = PyQt5.uic.loadUi(ui_src)
    qtbot.add_widget(widget)

    view = widget.widget

    view.show()
    qtbot.wait_for_window_shown(widget=view)

    assert view.parent() is widget
    assert isinstance(view.ui, epyqlib.filesview.Ui)
    assert hasattr(view.ui, 'something')
