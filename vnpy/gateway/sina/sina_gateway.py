import copy
import json
import threading

import requests

from vnpy.event import Event
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    SubscribeRequest,
    CancelRequest,
    OrderRequest
)
from vnpy.trader.event import EVENT_TIMER

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
from vnpy.trader.constant import Product


class SinaGateway(BaseGateway):
    """
    VN Trader Gateway for sina API.
    """

    default_setting = {
        "主动请求地址": "tcp://127.0.0.1:2014",
        "推送订阅地址": "tcp://127.0.0.1:4102"
    }

    exchanges = list(Exchange)

    def __init__(self, event_engine):
        """Constructor"""
        super().__init__(event_engine, "SINA")
        self.timer_started = False
        self.symbol_gateway_map = {}
        self.subscribed_symbols = {}
        self.saved_serial = None

    def connect(self, setting: dict):
        """"""
        self.write_log("服务器连接成功，开始初始化查询")

        self.query_all()

    def sina_quote(self, vt_symbol):
        symbol, exchange = extract_vt_symbol(vt_symbol)
        # symbol = symbol.lower()
        keys = [
            "",             #0:name
            "",             #1:time
            "open_price",   #2:
            "high_price",   #3
            "low_price",    #4
            "pre_close",    #5
            "bid_price_1",  #6
            "ask_price_1",  #7
            "last_price",   #8
            "",             #9
            "",             #10
            "bid_volume_1", #11
            "ask_volume_1", #12
            "open_interest",#13
            "volume",       #14
        ]

        url = "http://hq.sinajs.cn/list={}".format(symbol)
        result = requests.get(url).text
        result = result.split("=\"")[1][:-3]
        result = result.split(",")
        print(result)
        if len(result) < len(keys):
            print("Invalid data")
            return None

        data = {}
        for i, v in enumerate(keys):
            if not v:
                continue
            data[v] = float(result[i])

        data["name"] = result[0]
        data["gateway_name"] = "SINA"
        data["symbol"] = symbol
        data["exchange"] = exchange
        data["datetime"] = datetime.fromisoformat(result[17] + " " + ":".join([result[1][:2],result[1][2:4],result[1][4:]]))
        return data

    def process_timer_event(self, event: Event):
        """"""
        for vt_symbol in self.subscribed_symbols.values():
            tick = self.sina_quote(vt_symbol)
            if not tick:
                continue
            tick = TickData(**tick)
            self.event_engine.put(Event(EVENT_TICK, tick))

    def subscribe(self, req: SubscribeRequest):
        """"""
        if not self.timer_started:
            self.timer_started = True
            self.subscribed_symbols[req.vt_symbol] = req.vt_symbol
            self.event_engine.register(EVENT_TIMER, self.process_timer_event)

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

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """
        Query bar history data.
        """
        symbol, exchange = extract_vt_symbol(req.vt_symbol)
        interval = "15m"   #req.interval
        url = "http://stock2.finance.sina.com.cn/futures/api/json.php/IndexService.getInnerFuturesMiniKLine{}?symbol={}".format(interval, symbol)
        result = requests.get(url)
        self.saved_serial = result.json()
        result: List[BarData] = []
        mapper = [
            "",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
        ]
        for data in self.saved_serial:
            prices = {k: float(data[i]) for i, k in enumerate(mapper) if k}
            result.append(BarData(
                gateway_name=self.gateway_name,
                symbol=symbol,
                exchange=exchange,
                datetime=datetime.fromisoformat(data[0]),
                open_interest=0.0,
                interval=req.interval,
                **prices
            ))
        return result

    def query_all(self):
        """"""
        symbol, exchange = extract_vt_symbol("AG2107.SHFE")
        for i in range(1):
            contract = ContractData(
                symbol=symbol,
                exchange=exchange,
                name=symbol,
                product=Product.FUTURES,
                size=7,
                pricetick=1,
                history_data=True,
                gateway_name=self.gateway_name
            )
            self.on_contract(contract)

        self.write_log("合约信息查询成功")

    def close(self):
        """"""
        pass
