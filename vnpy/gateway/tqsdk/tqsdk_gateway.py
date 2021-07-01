import copy
import threading
import time

from vnpy.event import Event
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    SubscribeRequest,
    CancelRequest,
    OrderRequest
)
from vnpy.trader.constant import Exchange, Interval
from tqsdk import TqApi
from tqsdk.objs import Quote as TqQuote
from vnpy.trader.object import ContractData, TickData, HistoryRequest, BarData
from threading import Thread
from vnpy.trader.event import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
    EVENT_QUOTE,
)
from datetime import datetime
from pytz import utc as UTC_TZ
from vnpy.trader.utility import extract_vt_symbol
from typing import List
from pandas import DataFrame


class TqsdkTask(Thread):
    def __init__(self, gw):
        self.gw = gw
        super(TqsdkTask, self).__init__()

    def run(self):
        while True:
            self.gw.api.wait_update()
            if self.gw.closed:
                return
            if self.gw.saved_serial is not None and self.gw.api.is_serial_ready(self.gw.saved_serial):
                self.gw.notify()
            for symbol, quote in self.gw.subscribed_symbols.items():
                name = symbol
                symbol, exchange = extract_vt_symbol(symbol)
                if self.gw.api.is_changing(quote):
                    tick = TickData(
                        symbol=symbol,
                        exchange=exchange,
                        datetime=datetime.fromisoformat(quote.datetime),
                        name=name,
                        volume=quote.volume,
                        open_price=quote.open,
                        high_price=quote.highest,
                        low_price=quote.lowest,
                        last_price=quote.last_price,
                        open_interest=quote.open_interest,
                        bid_price_1=quote.bid_price1,
                        bid_volume_1=quote.bid_volume1,
                        ask_price_1=quote.ask_price1,
                        ask_volume_1=quote.ask_volume1,
                        gateway_name=self.gw.gateway_name
                    )
                    self.gw.client_callback(Event(EVENT_TICK, tick))


class TqsdkGateway(BaseGateway):
    """
    VN Trader Gateway for TQ SDK service.
    """

    default_setting = {
        "主动请求地址": "tcp://127.0.0.1:2014",
        "推送订阅地址": "tcp://127.0.0.1:4102"
    }

    exchanges = list(Exchange)

    def __init__(self, event_engine):
        """Constructor"""
        super().__init__(event_engine, "TQSDK")

        self.symbol_gateway_map = {}
        self.api = None
        self.subscribed_symbols = {}
        self.saved_serial = None
        self.cond = threading.Condition(threading.Lock())
        self.closed = False

    def connect(self, setting: dict):
        """"""
        self.api = TqApi(debug=True)
        self.write_log("服务器连接成功，开始初始化查询")

        self.query_all()

        self.task = TqsdkTask(self)
        self.task.start()

    @staticmethod
    def _symbol_to_tq(vt_symbol):
        vt_symbol = TqsdkGateway._symbol_swap(vt_symbol)
        if vt_symbol.endswith("77"):
            vt_symbol = "KQ.i@"+vt_symbol[:-2]
        return vt_symbol

    @staticmethod
    def _symbol_swap(vt_symbol):
        vt_symbol = vt_symbol.split(".")
        vt_symbol.reverse()
        vt_symbol = ".".join(vt_symbol)
        return vt_symbol

    @staticmethod
    def _symbol_from_tq(vt_symbol):
        if vt_symbol.startswith("KQ.i@"):
            vt_symbol = vt_symbol.split("@")[1]+"77"

        return TqsdkGateway._symbol_swap(vt_symbol)

    def subscribe(self, req: SubscribeRequest):
        """"""
        vt_symbol = self._symbol_to_tq(req.vt_symbol)
        self.subscribed_symbols[req.vt_symbol] = self.api.get_quote(vt_symbol)

    def send_order(self, req: OrderRequest):
        """"""
        gateway_name = self.symbol_gateway_map.get(req.vt_symbol, "")
        pass

    def cancel_order(self, req: CancelRequest):
        """"""
        gateway_name = self.symbol_gateway_map.get(req.vt_symbol, "")
        pass

    def query_account(self):
        """"""
        pass

    def query_position(self):
        """"""
        pass

    def notify(self):
        with self.cond:
            self.cond.notify()

    def wait(self):
        with self.cond:
            self.cond.wait()

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """
        Query bar history data.
        """
        vt_symbol = self._symbol_to_tq(req.vt_symbol)
        interval = self.interval_convert(req.interval)
        data_length = self.length_calculate(vt_symbol, req.start, req.end, interval)
        self.saved_serial = self.api.get_kline_serial(vt_symbol, interval, data_length)
        self.wait()
        data: List[BarData] = []
        rcv: DataFrame = self.saved_serial
        for i in range(len(rcv)):
            d = rcv.iloc[i]
            symbol, exchange = extract_vt_symbol(TqsdkGateway._symbol_from_tq(d.symbol))
            data.append(BarData(
                gateway_name=self.gateway_name,
                symbol=symbol,
                exchange=exchange,
                volume=d.volume,
                datetime=datetime.fromtimestamp(d.datetime/1000000000.0),
                open_interest=d.open_oi,
                open_price=d.open,
                close_price=d.close,
                low_price=d.low,
                high_price=d.high,
                interval=self.interval_convert(d.duration)
            ))
        return data

    def length_calculate(self, vt_symbol: str, start: datetime, end: datetime, interval):
        # trading_time = self.api._data["quotes"][vt_symbol]["trading_time"]

        return 2000

    @staticmethod
    def interval_convert(interval: object):
        if isinstance(interval, Interval):
            mapper = {
                Interval.MINUTE: 60,
                Interval.HOUR: 3600,
                Interval.DAILY: 3600 * 24,
                Interval.WEEKLY: 3600 * 24 * 7,
                Interval.TICK: 1,
            }
        else:
            mapper = {
                60: Interval.MINUTE,
                3600: Interval.HOUR,
                3600 * 24: Interval.DAILY,
                3600 * 24 * 7: Interval.WEEKLY,
                1: Interval.TICK,
            }
        return mapper[interval]

    def query_all(self):
        """"""
        contracts = []
        name_set = set()
        for name, quote in self.api._data["quotes"].items():
            quote: TqQuote = quote
            name_set.add(name)
            try:
                symbol, exchange = extract_vt_symbol(self._symbol_from_tq(name))
            except Exception as e:
                print(e)
                continue
            if quote.expired:
                print("Expired: %s", name)
                continue
            contracts.append(ContractData(
                symbol=symbol,
                exchange=exchange,
                name=quote.underlying_symbol,
                product=quote.product_id,
                size=quote.volume_multiple,
                pricetick=quote.price_tick,
                history_data=True,
                is_index_contract=symbol.endswith("77"),
                # margin_ratio=contract.margin_ratio,
                # open_date="19990101",
                # expire_date="20990101",
                gateway_name=self.gateway_name
            ))

        print(name_set)
        for contract in contracts:
            self.symbol_gateway_map[contract.vt_symbol] = contract.gateway_name
            contract.gateway_name = self.gateway_name
            self.on_contract(contract)
        self.write_log("合约信息查询成功")

    def close(self):
        """"""
        if self.api:
            self.closed = True
            self.api._set_wait_timeout()
            self.api._loop.call_soon_threadsafe(lambda : None)
            time.sleep(3)
            self.api.close()

    def client_callback(self, event: Event):
        """"""
        data = event.data

        if hasattr(data, "gateway_name"):
            data.gateway_name = self.gateway_name

        self.event_engine.put(event)
