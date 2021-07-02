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


class CustomizedCandleItem(CandleItem):
    """"""

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
        self._draw_extra_lines(ix, painter, macd)
        painter.setPen(self._down_pen)
        self._draw_extra_lines(ix, painter, self.ema_long)
        self._draw_extra_lines(ix, painter, self.ema_short)

    def _draw_extra_lines(self, ix, painter, macd):
        prev = ix-1 if ix >= 1 else ix

        y_min, y_max = self.get_y_range()
        m_range = np.nanmax(macd) - np.nanmin(macd)
        m_min = np.nanmin(macd)

        def factor(v):
            return (v - m_min)/m_range*(y_max-y_min) + y_min

        pp = factor(macd[prev])
        pc = factor(macd[ix])
        painter.drawLine(
            QtCore.QPointF(prev, pp),
            QtCore.QPointF(ix, pc)
        )

    def get_info_text(self, ix: int) -> str:
        """
        Get information text to show by cursor.
        """
        text = super().get_info_text(ix)

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

