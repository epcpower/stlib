import itertools
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty, Qt
import sys
from math import pi, isinf, sqrt, asin, ceil, cos, sin, floor, ceil

# See file COPYING in this source tree
__copyright__ = "\n".join(
    [
        "Copyright 2008-2012 Meinert Jordan <meinert@gmx.at>",
        # Originally written in C++
        # http://qt-apps.org/content/show.php/QScale?content=148053
        "Copyright 2014, Fabián Inostroza",
        # Ported to PyQt4
        # http://pastebin.com/kzp7f7DS
        "Copyright 2017, EPC Power Corp.",
        # Ported to PyQt5
        # Max/min positions correct and vertical orientation can be flipped.
    ]
)
__license__ = "GPLv2+"


class QScale(QtWidgets.QWidget):
    def __init__(self, parent=None, in_designer=False):
        QtWidgets.QWidget.__init__(self, parent=parent)

        self.in_designer = in_designer

        self.m_minimum = 0  # Minimum value of scale; default value 0
        self.m_maximum = 100  # Maximum value of scale; default value 100
        self.m_value = 0  # Current value (where needle would point); def val = 0
        self.m_paintMode = 0  # The paint mode, which determines how much of
        # the scale is painted.
        # 0 = All, 1 = color ranges, scale markers, labels,
        # needle. 2 = only needle. 3 = needle, cover.

        self.m_labelsVisible = True  # Determines if numbers of scale would show
        self.m_scaleVisible = True  # Determines if markers of scale would show

        # Values that help represent values that make up the QScale widget.
        self.m_borderWidth = 6
        self.m_labelsFormat = "g"
        self.m_labelsPrecision = -1
        self.m_majorStepSize = 0
        self.m_minorStepCount = 0

        self.m_invertedAppearance = False  # This value is not currently used.
        self.m_orientations = QtCore.Qt.Horizontal | QtCore.Qt.Vertical

        self.vertically_flipped = False  # New property specifying if flipped.

        self.setBackgroundRole(QtGui.QPalette.Base)

        self.labelSample = ""
        self.updateLabelSample()
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

        self.breakpoints = []
        self.colors = []

        self.isBlue = False

    def setMinimumSize(self, width=None, height=None, painter=None):
        self.updateLabelSample()

        if painter is None:
            painter = QtGui.QPainter(self)

        # TODO: CAMPid 079370432832243267955437254329546425654321
        rect = painter.boundingRect(
            QtCore.QRectF(0, 0, self.width(), self.height()),
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter,
            self.labelSample,
        )

        # TODO: CAMPid 07899789654211527951677432169
        # Specify if the widget is vertical.
        if (not (self.m_orientations & QtCore.Qt.Vertical)) ^ (
            not (self.m_orientations & QtCore.Qt.Horizontal)
        ):
            vertical = self.m_orientations & QtCore.Qt.Vertical
        else:
            vertical = self.height() > self.width()

        wLabel = rect.width() if self.m_labelsVisible else 0
        hLabel = rect.height() if self.m_labelsVisible else 0

        if vertical:
            wLabel, hLabel = hLabel, wLabel

        if width is None:
            width = ceil(2 * self.m_borderWidth + wLabel + 1)
        if height is None:
            height = ceil(2 * (1 + self.m_borderWidth + hLabel))

        if vertical:
            height, width = width, height

        super().setMinimumSize(int(width), int(height))

    def setMinimum(self, max):
        if not isinf(max):
            self.m_maximum = max
        self.updateLabelSample()
        self.update()

    def maximum(self):
        return self.m_maximum

    def setRange(self, min, max):
        if not isinf(min):
            self.m_minimum = min
        if not isinf(max):
            self.m_maximum = max
        self.updateLabelSample()
        self.update()

    def setColorRanges(self, colors, breakpoints):
        if len(colors) == 0:
            # TODO: something better
            raise Exception("no colors")

        if not all(x < y for x, y in zip(breakpoints, breakpoints[1:])):
            # TODO: something better
            raise ValueError("Monotonicity")

        if len(colors) - len(breakpoints) != 1:
            # TODO: something better
            raise ValueError("Bad set of color range lists")

        self.breakpoints = breakpoints
        self.colors = colors

    def setValue(self, val):
        self.m_value = val
        self.update()

    def value(self):
        return self.m_value

    def setLabelsVisible(self, visible):
        self.m_labelsVisible = visible
        self.update()

    def isLabelsVisible(self):
        return self.m_labelsVisible

    def setScaleVisible(self, visible):
        self.m_scaleVisible = visible
        self.update()

    def isScaleVisible(self):
        return self.m_scaleVisible

    def setBorderWidth(self, width):
        self.m_borderWidth = width if width > 0 else 0
        self.update()

    def borderWidth(self):
        return self.m_borderWidth

    def setLabelsFormat(self, fmt, precision):
        self.m_labelsFormat = fmt
        self.m_labelsPrecision = precision
        self.updateLabelSample()
        self.update()

    def setMajorStepSize(self, stepsize):
        self.m_majorStepSize = stepsize
        self.update()

    def majorStepSize(self):
        return self.m_majorStepSize

    def setMinorStepSize(self, stepcount):
        self.m_minorStepCount = stepcount
        self.update()

    def minorStepCount(self):
        return self.m_minorStepCount

    def setInvertedAppearance(self, invert):
        self.m_invertedAppearance = invert
        self.update()

    def invertedAppearance(self):
        return self.m_invertedAppearance

    # orientations es Qt::Orientations
    def setOrientations(self, orientations):
        self.m_orientations = orientations
        self.update()

    def orientations(self):
        return self.m_orientations

    def resizeEvent(self, re):
        super(QScale, self).resizeEvent(re)

    def paintEvent(self, paintEvent):

        # Set the values.

        painter = QtGui.QPainter(self)

        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        self.setMinimumSize(painter=painter)

        # TODO: CAMPid 07899789654211527951677432169

        # Determine the criterion of what makes the widget vertical.
        if (not (self.m_orientations & QtCore.Qt.Vertical)) ^ (
            not (self.m_orientations & QtCore.Qt.Horizontal)
        ):
            vertical = self.m_orientations & QtCore.Qt.Vertical
        else:
            vertical = self.height() > self.width()

        # Acquire widget width and height values.
        wWidget = self.width()
        hWidget = self.height()

        # TODO: CAMPid 079370432832243267955437254329546425654321
        # Acquire the height and width of the individual labels.
        boundingRect = painter.boundingRect(
            QtCore.QRectF(0, 0, self.width(), self.height()),
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter,
            self.labelSample,
        )

        # Set the width and height of the labels.
        wLabel = boundingRect.width() if self.m_labelsVisible else 0
        hLabel = boundingRect.height() if self.m_labelsVisible else 0

        # Swap width and height values if the widget is vertical.
        if vertical:
            wWidget, hWidget = hWidget, wWidget
            wLabel, hLabel = hLabel, wLabel

        # Get the width and height of the scale itself
        # (based on the label and actual widget values)
        wScale = wWidget - wLabel - 2.0 * self.m_borderWidth

        hScale = 0.5 * hWidget - hLabel - self.m_borderWidth

        # Acquire radius of drawn scale based off of width and height of scale.
        radius = 0.125 * wScale ** 2 / hScale + 0.5 * hScale

        # Acquire the center point and modify radius if needed.
        if radius < hScale + 0.5 * hWidget - self.m_borderWidth:
            radius = (
                (
                    4.0 * (hLabel + self.m_borderWidth)
                    + sqrt(4.0 * (hLabel + self.m_borderWidth) ** 2 + 3.0 * wScale ** 2)
                )
                / 3.0
                - hLabel
                - 2.0 * self.m_borderWidth
            )
            center = QtCore.QPointF(0.5 * wWidget, hWidget - self.m_borderWidth)
        else:
            center = QtCore.QPointF(0.5 * wWidget, radius + hLabel + self.m_borderWidth)

        # Calculate where certain things start and their span.
        angleSpan = -360.0 / pi * asin(wScale / (2.0 * radius))
        angleStart = 90.0 - 0.5 * angleSpan

        valueSpan = self.m_maximum - self.m_minimum

        # Calculate the size of the tick marks.
        majorStep = (
            abs(valueSpan) * self.max(wLabel, 1.5 * boundingRect.height()) / wScale
        )
        order = 0

        while majorStep < 1:
            majorStep *= 10
            order -= 1

        while majorStep >= 10:
            majorStep /= 10
            order += 1

        if majorStep > 5:
            majorStep = 10 * 10 ** order
            minorSteps = 5
        elif majorStep > 2:
            majorStep = 5 * 10 ** order
            minorSteps = 5
        else:
            majorStep = 2 * 10 ** order
            minorSteps = 4

        if self.m_majorStepSize > 0:
            majorStep = self.m_majorStepSize
        if self.m_minorStepCount > 0:
            minorSteps = self.m_minorStepCount

        scaleWidth = self.min(
            self.min(0.25 * (hWidget - self.m_borderWidth), 0.25 * radius),
            2.5 * boundingRect.height(),
        )
        minorScaleWidth = scaleWidth * 0.4

        # Change the orientation of the scale if the scale is vertical.
        if vertical:
            painter.rotate(90)
            painter.translate(0, -hWidget + wLabel / 4.0)

        def drawColorRanges(self):

            # Make starting point be top left corner instead of top right corner
            if vertical and self.vertically_flipped:
                # Weird. Seems to get the position as if the angle is 0 degrees
                painter.translate(0, painter.transform().dx())
                # Correctly repositions color scale.
                painter.translate(0, -wLabel / 4.0)

            if len(self.colors) > 0:
                transform = painter.transform()
                valueSpan = self.m_maximum - self.m_minimum
                rangeValueStart = self.m_minimum

                for breakpoint, color in itertools.zip_longest(
                    self.breakpoints, self.colors
                ):
                    # Consider color for range [rangeValueStart, breakpoint]
                    if breakpoint is None or breakpoint > rangeValueStart:
                        if rangeValueStart < self.m_maximum:
                            if not vertical or self.vertically_flipped:
                                rangeAngleStart = (
                                    angleStart
                                    + angleSpan
                                    * (rangeValueStart - self.m_minimum)
                                    / valueSpan
                                )
                            elif vertical and not self.vertically_flipped:
                                if breakpoint is None:
                                    breakpoint = self.m_maximum
                                rangeAngleStart = (
                                    angleStart
                                    + angleSpan
                                    * (self.m_maximum - breakpoint)
                                    / valueSpan
                                )
                            try:
                                if not vertical or self.vertically_flipped:
                                    rangeAngleEnd = (
                                        angleStart
                                        + angleSpan
                                        * (breakpoint - self.m_minimum)
                                        / valueSpan
                                    )
                                elif vertical and not self.vertically_flipped:
                                    rangeAngleEnd = (
                                        angleStart
                                        + angleSpan
                                        * (self.m_maximum - rangeValueStart)
                                        / valueSpan
                                    )
                            except TypeError:
                                rangeAngleEnd = angleStart + angleSpan
                            # max because of angles going counter clockwise...
                            rangeAngleEnd = max(rangeAngleEnd, angleStart + angleSpan)
                            rangeAngleSpan = rangeAngleEnd - rangeAngleStart

                            if vertical and self.vertically_flipped:
                                rangeAngleStart += 180
                                rangeAngleEnd += 180

                            painter.setPen(color)
                            painter.setBrush(color)
                            qpp = QtGui.QPainterPath()
                            r = radius - 0.8 * scaleWidth
                            d = 2 * r
                            x = center.x() - r
                            y = center.y() - r

                            y_offset = y
                            # Color scale orientation changed if flipped.
                            # Keep in mind, it isn't a PERFECT flip.
                            if not (vertical and self.vertically_flipped):
                                y_offset = y
                            else:
                                y_offset = -y - d
                            qpp.arcMoveTo(x, y_offset, d, d, rangeAngleStart)
                            qpp.arcTo(
                                x, y_offset, d, d, rangeAngleStart, rangeAngleSpan
                            )

                            outer = QtGui.QPainterPath()
                            r = radius - 0.6 * scaleWidth
                            d = 2 * r
                            x = center.x() - r
                            y = center.y() - r

                            # Color scale orientation changed if flipped.
                            if not (vertical and self.vertically_flipped):
                                y_offset = y
                            else:
                                y_offset = -y - d

                            outer.arcMoveTo(
                                x, y_offset, d, d, rangeAngleStart + rangeAngleSpan
                            )
                            outer.arcTo(
                                x,
                                y_offset,
                                d,
                                d,
                                rangeAngleStart + rangeAngleSpan,
                                -rangeAngleSpan,
                            )

                            qpp.connectPath(outer)
                            qpp.closeSubpath()
                            painter.drawPath(qpp)
                            painter.setTransform(transform)

                            rangeValueStart = breakpoint

            painter.resetTransform()

        def drawScaleMarkers(self):
            painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.Text), 1))

            # Only draw if the scale is visible and enough space for tick marks.
            if self.m_scaleVisible and majorStep != 0:

                # Rotate the painter to accomodate for vertical scale.
                if vertical:
                    if not self.vertically_flipped:
                        painter.rotate(90)
                        painter.translate(0, -hWidget + wLabel / 4.0)
                    else:
                        painter.rotate(90)
                        painter.translate(0, -self.width())
                        painter.translate(0, -(-hWidget + wLabel / 4.0))

                # Account for flipping vertical scales.
                if vertical and self.vertically_flipped:
                    painter.translate(center.x(), -center.y())
                else:
                    painter.translate(center)

                # Turn 180 degrees to account for flipped vertical scales.
                if vertical and self.vertically_flipped:
                    painter.rotate(
                        self.m_minimum
                        % ceil(float(majorStep) / float(minorSteps))
                        / float(valueSpan)
                        * angleSpan
                        - angleStart
                        + 180
                    )
                else:
                    painter.rotate(
                        self.m_minimum
                        % ceil(float(majorStep) / float(minorSteps))
                        / float(valueSpan)
                        * angleSpan
                        - angleStart
                    )

                offsetCount = (
                    minorSteps
                    - ceil(self.m_minimum % majorStep) / float(majorStep) * minorSteps
                ) % minorSteps

                # Actual drawing of tick marks done here.
                for i in range(0, floor(minorSteps * abs(valueSpan) / majorStep) + 1):
                    if i % minorSteps == offsetCount:
                        # Draw bigger line for like every 5 or 10 or so.
                        painter.drawLine(
                            QtCore.QLineF(radius - scaleWidth, 0, radius, 0)
                        )
                    else:
                        # Draw smaller line for the other tick marks.
                        painter.drawLine(
                            QtCore.QLineF(
                                radius - scaleWidth, 0, radius - minorScaleWidth, 0
                            )
                        )
                    # Rotate the painter a bit for the next tick mark.
                    painter.rotate(
                        majorStep * angleSpan / (-abs(valueSpan) * minorSteps)
                    )

                painter.resetTransform()

        def drawLabels(self):

            # Draw the numbers on the scale.
            if self.m_labelsVisible and majorStep != 0:
                # x represents the amount tick marks on the scale.
                x = range(
                    int(ceil(self.min(self.m_minimum, self.m_maximum) / majorStep)),
                    int(self.max(self.m_minimum, self.m_maximum) / majorStep) + 1,
                )

                # Prep each tick mark, draw right value and at right positioning
                for i in x:
                    # Get the particular angle the number should be drawn at.
                    u = (
                        pi
                        / 180.0
                        * (
                            (majorStep * i - self.m_minimum)
                            / float(valueSpan)
                            * angleSpan
                            + angleStart
                        )
                    )
                    position = QtCore.QRect()

                    # Acquire the position of the number based on orientation.
                    if vertical:
                        if not self.vertically_flipped:
                            align = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
                            position = QtCore.QRect(
                                self.width() - center.y() + radius * sin(u),
                                0,
                                self.width(),
                                self.height() + 2 * radius * cos(u),
                            )
                        else:
                            align = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                            position = QtCore.QRect(
                                center.y() - radius * sin(u) - self.width(),
                                0,
                                self.width(),
                                self.height() + 2 * radius * cos(u),
                            )
                    else:
                        align = QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom
                        position = QtCore.QRect(
                            0,
                            0,
                            int(2.0 * (center.x() + radius * cos(u))),
                            int(center.y() - radius * sin(u)),
                        )
                    painter.resetTransform()
                    # TODO: add usage of m_labelsFormat and m_labelsPrecision

                    # Draw the number in an order that depends if the scale is
                    # vertical or not.
                    if vertical:
                        painter.drawText(
                            position,
                            align,
                            "{}".format((x.stop + x.start - i - 1) * majorStep),
                        )
                    else:
                        painter.drawText(position, align, "{}".format(i * majorStep))

        def drawNeedle(self):
            painter.resetTransform()
            # CHange the painter's orientation depending on scale's orientation.
            if vertical:
                if not self.vertically_flipped:
                    painter.rotate(90)
                    painter.translate(0, -hWidget + wLabel / 4.0)
                else:
                    painter.rotate(90)
                    painter.translate(0, -self.width())
                    painter.translate(0, -(-hWidget + wLabel / 4.0))

            if vertical and self.vertically_flipped:
                painter.translate(center.x(), -center.y())
            else:
                painter.translate(center)

            # Get the calibration of the needle.
            if vertical:
                if not self.vertically_flipped:
                    painter.rotate(
                        (-self.m_maximum + self.m_value) / float(valueSpan) * angleSpan
                        - angleStart
                    )
                else:
                    painter.rotate(
                        (self.m_minimum - self.m_value) / float(valueSpan) * angleSpan
                        - angleStart
                    )
                    painter.rotate(180)
            else:
                painter.rotate(
                    (self.m_minimum - self.m_value) / float(valueSpan) * angleSpan
                    - angleStart
                )

            # Actually draw the needle based off of the previous settings set up
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(self.palette().color(QtGui.QPalette.Text))
            self.polygon = QtGui.QPolygon()

            # python does not need the first parameter (number of points)
            self.polygon.setPoints(
                0, -2, int(radius) - 10, -2, int(radius), 0, int(radius) - 10, 2, 0, 2
            )

            painter.drawConvexPolygon(self.polygon)

            if not self.isBlue:
                painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.Base), 2))
            else:
                painter.setPen(QtGui.QPen(Qt.blue))
            painter.drawLine(0, 0, int(radius - 15), 0)
            painter.resetTransform()

        def drawCover(self, center):

            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(self.palette().color(QtGui.QPalette.Mid))

            # Draw rectangle component depending on the orientation of scale.
            # The circular part of scale also varies on orientation of scale.
            if vertical:
                if self.vertically_flipped:
                    painter.drawRect(
                        QtCore.QRect(
                            self.width() - self.m_borderWidth,
                            0,
                            self.m_borderWidth,
                            self.height(),
                        )
                    )
                else:
                    painter.drawRect(
                        QtCore.QRect(0, 0, self.m_borderWidth, self.height())
                    )
                center = QtCore.QPoint(
                    self.width() - center.y() - wLabel / 4.0, 0.5 * self.height()
                )
                u = 0.25 * (hWidget - wLabel) - center.x() - self.m_borderWidth
                if self.vertically_flipped:
                    center = QtCore.QPoint(-center.x() + self.width(), center.y())
            else:
                pass
                painter.drawRect(QtCore.QRect(0, hWidget, wWidget, -self.m_borderWidth))
                u = center.y() - self.m_borderWidth - 0.75 * hWidget

            # Draw the circular part of scale. It will be a very small portion
            # of a very large ellipse for the most part.
            u = self.max(u, 0.25 * radius)
            u = min(u, (radius - scaleWidth) - minorScaleWidth)
            painter.drawEllipse(center, u, u)

        if self.m_paintMode == 0 or self.m_paintMode == 1:
            drawColorRanges(self)
            drawScaleMarkers(self)
            drawLabels(self)
        drawNeedle(self)
        if self.m_paintMode == 0 or self.m_paintMode == 3:
            drawCover(self, center)

    def updateLabelSample(self):
        margin = self.max(abs(self.m_minimum), abs(self.m_maximum))
        if self.min(self.m_minimum, self.m_maximum) < 0:
            wildcard = float(-8)
        else:
            wildcard = float(8)

        while margin < 1:
            margin *= 10
            wildcard /= 10

        while margin >= 10:
            margin /= 10
            wildcard *= 10

        # self.labelSample = QtCore.QString.number(wildcard,
        #                        self.m_labelsFormat, self.m_labelsPrecision)
        # TODO: add usage of m_labelsFormat and m_labelsPrecision
        self.labelSample = "{}".format(wildcard)

    def max(self, val1, val2):
        return val1 if val1 > val2 else val2

    def min(self, val1, val2):
        return val1 if val1 < val2 else val2

    # New functions help determining flip status.
    @pyqtProperty(bool)
    def flipped(self):
        return self.vertically_flipped

    @flipped.setter
    def flipped(self, value):
        self.vertically_flipped = value


if __name__ == "__main__":
    global j
    j = 100

    def update():
        global j
        if j == 0:
            j = 100
        else:
            j -= 1
        scale.setValue(j)

    app = QtGui.QApplication(sys.argv)
    scale = QScale()
    timer = QtCore.QTimer()
    timer.setInterval(100)
    timer.timeout.connect(update)
    timer.start()
    scale.show()
    sys.exit(app.exec_())
