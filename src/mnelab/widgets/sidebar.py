# © MNELAB developers
#
# License: BSD (3-clause)

import sys

from PySide6.QtCore import QEvent, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
)

ROW_HEIGHT = 30

DTYPE_COLORS = {
    "raw": ("#2563EB", "#FFFFFF"),  # blue-600 bg, white text
    "epochs": ("#92400E", "#FFFFFF"),  # amber-800 bg, white text
}


class TypeBadgeDelegate(QStyledItemDelegate):
    """Renders a rounded-rectangle badge for the data type column."""

    def paint(self, painter, option, index):
        dtype = index.data(Qt.DisplayRole)
        if not dtype:
            return
        bg_hex, fg_hex = DTYPE_COLORS.get(dtype.lower(), ("#6B7280", "#FFFFFF"))
        label = dtype.capitalize()

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect
        pad_y = 5
        badge_h = rect.height() - 2 * pad_y
        badge_rect = QRectF(rect.x() + 2, rect.y() + pad_y, rect.width() - 4, badge_h)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(bg_hex))
        painter.drawRoundedRect(badge_rect, badge_h / 2, badge_h / 2)

        font = painter.font()
        font.setPointSizeF(max(6.0, font.pointSizeF() - 1))
        painter.setFont(font)
        painter.setPen(QColor(fg_hex))
        painter.drawText(badge_rect, Qt.AlignCenter, label)

        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setWidth(56)
        return hint


class SpanningHeaderView(QHeaderView):
    """Horizontal header where a contiguous range of sections is painted as one."""

    def __init__(self, orientation, span_start=0, span_count=1, parent=None):
        super().__init__(orientation, parent)
        self._span_start = span_start
        self._span_count = span_count

    def paintSection(self, painter, rect, logical_index):
        span_cols = range(self._span_start, self._span_start + self._span_count)
        if logical_index in span_cols and logical_index != self._span_start:
            return
        if logical_index == self._span_start:
            total_width = sum(self.sectionSize(self._span_start + i) for i in range(self._span_count))
            rect = QRect(rect.x(), rect.y(), total_width, rect.height())
        super().paintSection(painter, rect, logical_index)


class SidebarTableWidget(QTableWidget):
    rowsMoved = Signal(int, int)  # custom signal emitted when drag-and-dropping rows

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(False)
        self.setDragDropOverwriteMode(False)
        self.setFrameStyle(QFrame.NoFrame)
        self.setFocusPolicy(Qt.NoFocus)
        self.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.setColumnCount(4)
        self.setShowGrid(False)
        self.drop_row = -1

        header = SpanningHeaderView(Qt.Horizontal, span_start=1, span_count=3, parent=self)
        self.setHorizontalHeader(header)
        self.setHorizontalHeaderLabels(["#", "Dataset", "", ""])
        self.horizontalHeaderItem(0).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.verticalHeader().hide()
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.setColumnWidth(2, 56)
        self.setColumnWidth(3, 20)
        self.resizeColumnToContents(0)
        self.setItemDelegateForColumn(2, TypeBadgeDelegate(self))

        if sys.platform == "darwin":
            self.setStyleSheet("""
                QTableWidget::item:selected {
                    background-color: palette(highlight);
                    color: palette(highlighted-text);
                }
            """)

        self.setMouseTracking(True)
        self.viewport().installEventFilter(self)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            super().mousePressEvent(event)
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        elif event.source() == self:
            event.accept()
            super().dragEnterEvent(event)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        elif event.source() == self:
            drop_row = self.indexAt(event.pos()).row()
            if drop_row == -1:
                drop_row = self.rowCount()
            if drop_row != self.drop_row:
                self.drop_row = drop_row
            event.accept()
            super().dragMoveEvent(event)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_row = -1
        self.viewport().update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.drop_row >= 0:
            painter = QPainter(self.viewport())
            if self.drop_row < self.rowCount():
                y = self.visualRect(self.model().index(self.drop_row, 0)).top()
            else:
                y = self.visualRect(self.model().index(self.rowCount() - 1, 0)).bottom()
            painter.drawLine(0, y, self.viewport().width(), y)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.parent.event(event)
        elif event.source() == self:
            drop_row = self.indexAt(event.pos()).row()
            if drop_row == -1:
                drop_row = self.rowCount()
            selected_rows = sorted(
                index.row() for index in self.selectionModel().selectedRows()
            )
            if selected_rows and drop_row > selected_rows[-1]:
                drop_row -= len(selected_rows)

            self.drop_row = -1
            self.viewport().update()
            self.rowsMoved.emit(selected_rows[0], drop_row)
            event.setDropAction(Qt.IgnoreAction)
            event.accept()
        else:
            event.ignore()

    def set_dtype(self, row, dtype):
        """Set the data type badge for the given row."""
        item = QTableWidgetItem(dtype)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setTextAlignment(Qt.AlignCenter)
        item.setToolTip(f"Data type: {dtype.capitalize()}")
        self.setItem(row, 2, item)

    def style_rows(self):
        self.resizeColumnToContents(0)
        for i in range(self.rowCount()):
            self.resizeRowToContents(i)
            self.setRowHeight(i, ROW_HEIGHT)
            self.item(i, 0).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.item(i, 0).setForeground(QColor("gray"))
            self.item(i, 0).setFlags(self.item(i, 0).flags() & ~Qt.ItemIsEditable)
            self.item(i, 1).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.item(i, 1).setFlags(self.item(i, 1).flags() | Qt.ItemIsEditable)
            if self.item(i, 2) is not None:
                self.item(i, 2).setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

    def update_vertical_header(self):
        row_count = self.rowCount()
        self.setVerticalHeaderLabels([str(i) for i in range(row_count)])

    def eventFilter(self, source, event):
        if source == self.viewport() and event.type() == QEvent.MouseMove:
            index = self.indexAt(event.pos())
            if index.isValid():
                self.showCloseButton(index.row())
            else:
                self.showCloseButton(-1)
        elif source == self.viewport() and event.type() == QEvent.Leave:
            self.showCloseButton(-1)

        return False

    def showCloseButton(self, row_index):
        for i in range(self.rowCount()):
            if i == row_index:
                delete_button = QPushButton(self)
                delete_button.setIcon(QIcon.fromTheme("close-data"))
                delete_button.setStyleSheet(
                    "background: transparent; border: none; margin: auto;"
                )
                delete_button.clicked.connect(
                    lambda _, index=row_index: self.parent.model.remove_data(index)
                )
                self.setCellWidget(row_index, 3, delete_button)
            else:
                self.removeCellWidget(i, 3)
