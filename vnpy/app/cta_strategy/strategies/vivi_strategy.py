from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)

from vnpy.trader.utility_customized import ShapeFinder, Strategy, Incremental
from vnpy.trader.vi_layer import ViFlow
import numpy as np


class ViviStrategy(CtaTemplate):
    author = "vivi"

    minutes = 0

    sma_width = 3
    peak_width = 10
    peak_margin = 3
    peak_percent = 0.1
    break_percent = 0.001

    parameters = ["minutes", "sma_width", "peak_width", "peak_margin", "peak_percent", "break_percent"]
    variables = ["sma_width", "peak_width", "peak_margin", "peak_percent", "break_percent"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # minutes must be: 0, 2, 3, 5, 6, 10, 15, 20, 30
        self.minutes = setting["minutes"]
        self.bg = BarGenerator(self.on_bar, self.minutes, self.on_x_min_bar)
        self.am = ArrayManager(size=2525)
        # self.data = Incremental()
        self.flow = ViFlow()
        self.flow.setup(SmaWidth=self.sma_width,
                        PeakWidth=self.peak_width,
                        PeakMargin=self.peak_margin,
                        PeakPercent=self.peak_percent,
                        BreakPercent=self.break_percent)

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(0)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

        self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        if self.minutes == 0:
            self.evaluate(bar)
        else:
            self.bg.update_bar(bar)

    def on_x_min_bar(self, bar: BarData):
        self.evaluate(bar)
    
    def evaluate(self, bar: BarData):
        price = bar.high_price
        # result = self.data.update(price)
        result = self.flow.run(price)
        if result:
            print(result)
        result = 0 if not result else 1 if result[0][1] else -1
        if result == 0:
            return

        # print(result, self.data.idx)
        if result > 0:
            if self.pos == 0:
                self.buy(price, 1)
            elif self.pos < 0:
                self.cover(price, 1)
                self.buy(price, 1)

        elif result < 0:
            if self.pos == 0:
                self.short(price, 1)
            elif self.pos > 0:
                self.sell(price, 1)
                self.short(price, 1)

        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        print(self.result)
