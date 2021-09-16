from abc import abstractmethod
from typing import List, Dict, Tuple

import pandas
import pyqtgraph as pg

from vnpy.trader.ui import QtCore, QtGui, QtWidgets
from vnpy.trader.object import BarData

from .base import BLACK_COLOR, UP_COLOR, DOWN_COLOR, PEN_WIDTH, BAR_WIDTH
from .manager import BarManager
from vnpy.trader.utility import BarGenerator, ArrayManager
import numpy as np
from vnpy.chart import CandleItem
import math
from itertools import combinations


class CustomizedCandleItem(CandleItem):
    """"""

    def __init__(self, manager):
        super(CustomizedCandleItem, self).__init__(manager)
        self._white_pen: QtGui.QPen = pg.mkPen(
            color=(255, 255, 255), width=2
        )


    def update_history(self, history):
        super().update_history(history)
        # bars = self._manager.get_all_bars()
        # for bar in bars:
        #     self.array_manager.update_bar(bar)
        #
        # self.macd = self.array_manager.macd(12, 26, 9, array=True)

    def __init__(self, manager: BarManager):
        """"""
        super().__init__(manager)
        # self.array_manager = ArrayManager(size=2000)
        self.macd = None

    def _draw_item_picture(self, min_ix: int, max_ix: int) -> None:
        bars = self._manager.get_all_bars()
        if bars:
            self.array_manager = ArrayManager(size=len(bars))
            for bar in bars:
                self.array_manager.update_bar(bar)

            self.macd = self.array_manager.macd(12, 26, 9, array=True)
            self.ema_long = self.array_manager.ema(26, True)
            self.ema_short = self.array_manager.ema(12, True)
            self.lines = self.array_manager.high
            self.sma = self.array_manager.sma(3, True)
            self.tops, self.buttoms, self.break_points, self.key_points = self.array_manager.vi_points()
            self.x_min = min_ix
            self.x_max = max_ix
        super()._draw_item_picture(min_ix, max_ix)

    def _draw_extra_bar_picture(self, ix: int, painter: QtGui.QPainter) -> None:
        """"""
        # Create objects
        # macd_painter = QtGui.QPainter(candle_picture)
        # macd_painter.setPen(self._up_pen)
        # macd_painter.setBrush(self._black_brush)

        # Draw MACD line
        painter.setPen(self._up_pen)
        painter.setBrush(self._black_brush)
        macd: np.ndarray = self.macd[0]
        # self._draw_extra_lines(ix, painter, macd)
        self._draw_lines(ix, painter, self.sma)
        painter.setPen(self._down_pen)
        # self._draw_extra_lines(ix, painter, self.ema_long)
        # self._draw_extra_lines(ix, painter, self.ema_short)
        self._draw_lines(ix, painter, self.lines)
        self._draw_lines(ix, painter, self.tops)

        painter.setPen(self._up_pen)
        self._draw_lines(ix, painter, self.buttoms)

        if hasattr(self, "_white_pen"):
            painter.setPen(self._white_pen)
        self._draw_mark(ix, painter, self.break_points)
        array = self.key_points.swapaxes(0, 1)
        top = array[0] * (array[1] > 0)
        buttom = array[0] * (array[1] < 0)

        self._draw_mark(ix, painter, top, shape=self.SHAPE_TRIANGLE_UP)
        self._draw_mark(ix, painter, buttom, shape=self.SHAPE_TRIANGLE_DOWN)

    def _draw_extra_lines(self, ix, painter, macd):
        prev = ix-1 if ix >= 1 else ix

        y_min, y_max = self.get_y_range()
        m_range = np.nanmax(macd) - np.nanmin(macd)
        m_min = np.nanmin(macd)

        def factor(v):
            return (v - m_min)/m_range*(y_max-y_min) + y_min

        pp = factor(macd[prev])
        pc = factor(macd[ix])
        if math.isnan(pp) or math.isnan(pc):
            return
        painter.drawLine(
            QtCore.QPointF(prev, pp),
            QtCore.QPointF(ix, pc)
        )

    def _draw_lines(self, ix, painter, array):
        prev = ix-1 if ix >= 1 else ix

        if math.isnan(array[prev]) or math.isnan(array[ix]):
            return
        painter.drawLine(
            QtCore.QPointF(prev, array[prev]),
            QtCore.QPointF(ix, array[ix])
        )

    SHAPE_CROSS = 'cross'
    SHAPE_TRIANGLE_UP = 'triangle_up'
    SHAPE_TRIANGLE_DOWN = 'triangle_down'

    def _draw_mark(self, ix, painter, array, shape=SHAPE_CROSS, text="X"):
        edge = 2
        y_min, y_max = self.get_y_range()
        edge = (y_max - y_min) * edge / 300.0

        def draw_elems(points):
            all = combinations(points, 2)
            for p1, p2 in all:
                painter.drawLine(QtCore.QPointF(*p1), QtCore.QPointF(*p2))

        if math.isnan(array[ix]):
            return

        if shape == self.SHAPE_CROSS:
            left = [ix-edge, array[ix]-edge]
            right = [ix+edge, array[ix]+edge]
            top = [ix-edge, array[ix]+edge]
            buttom = [ix+edge, array[ix]-edge]
            draw_elems([left, right, top, buttom])
        elif shape == self.SHAPE_TRIANGLE_UP:
            up = [ix, array[ix]+edge]
            left = [ix-edge, array[ix]-edge]
            right = [ix+edge, array[ix]-edge]
            draw_elems([up, left, right])
        elif shape == self.SHAPE_TRIANGLE_DOWN:
            up = [ix, array[ix]-edge]
            left = [ix-edge, array[ix]+edge]
            right = [ix+edge, array[ix]+edge]
            draw_elems([up, left, right])

        painter.drawText(ix, array[ix], edge, edge, 0, text)

        # painter.drawPie(ix, array[ix], edge, edge, 90, 180)

    def get_info_text(self, ix: int) -> str:
        """
        Get information text to show by cursor.
        """
        text = super().get_info_text(ix)
        if not text:
            return text

        def factor(v):
            return (v - m_min)/m_range*(y_max-y_min) + y_min

        if self.macd:
            macd: np.ndarray = self.macd[0]
            y_min, y_max = self.get_y_range()
            m_range = np.nanmax(macd) - np.nanmin(macd)
            m_min = np.nanmin(macd)
            macd = factor(macd[ix])
        else:
            macd = ""

        return "\n".join([text, "", "MACD", str(macd)])

