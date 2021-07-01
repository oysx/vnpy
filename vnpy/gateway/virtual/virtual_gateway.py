import copy
import json
import sys
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
from vnpy.trader.utility import extract_vt_symbol, extract_sec_id, vt_symbol_to_index_symbol
from typing import List
from pandas import DataFrame
from vnpy.trader.constant import Product


class VirtualGateway(BaseGateway):
    """
    VN Trader Gateway for sina API.
    """

    default_setting = {
        "class": "CtpGateway",
    }

    exchanges = list(Exchange)

    def __init__(self, event_engine):
        """Constructor"""
        super().__init__(event_engine, "VIRTUAL")
        self.backend = None
        self.contracts = {}

    def connect(self, setting: dict):
        """"""
        backend_gateway = setting['class']
        for mod in sys.modules:
            if hasattr(mod, backend_gateway):
                backend_gateway = mod[backend_gateway]

        self.backend = backend_gateway(self.event_engine)

        self.event_engine.register(EVENT_CONTRACT, self.process_contract_event)
        return self.backend.connect()

    def __getattr__(self, item):
        return getattr(self.backend, item)

    def process_contract_event(self, event: Event) -> None:
        """"""
        contract = event.data
        if contract.vt_symbol not in self.contracts.keys():
            self.contracts[contract.vt_symbol] = contract
            # 插入指数合约contract
            sec_id = extract_sec_id(contract.vt_symbol)
            index_id = f"{sec_id}99"
            index_symbol_id = f"{index_id}.{contract.exchange.value}"
            if index_symbol_id not in self.contracts.keys():
                index_contract = ContractData(
                    symbol=index_id,
                    exchange=contract.exchange,
                    name=f"{index_id}指数合约",
                    product=contract.product,
                    size=contract.size,
                    pricetick=contract.pricetick,
                    history_data=contract.history_data,
                    # margin_ratio=contract.margin_ratio,
                    # open_date="19990101",
                    # expire_date="20990101",
                    gateway_name=contract.gateway_name
                )
                index_contract.is_index_contract = True

                self.contracts[index_symbol_id] = index_contract
                self.on_contract(index_contract)

    def _get_all_index_trade_contract(self, vt_symbol):
        # 查询该合约对应品种的所有在市合约
        contract_list = []
        target_sec_id = extract_sec_id(vt_symbol)
        contracts = self.contracts
        for vt_symbol, contract_data in contracts.items():
            sec_id = extract_sec_id(vt_symbol)
            if target_sec_id == sec_id and not contract_data.is_index_contract:
                contract_list.append(contract_data)
        return contract_list

    def _get_index_contract(self, vt_symbol):
        contract_id = vt_symbol_to_index_symbol(vt_symbol)
        return self.get_contract(contract_id)

    def subscribe(self, req: SubscribeRequest):
        """"""
        gateway = self.backend
        # 同类账户全部订阅
        if req.vt_symbol == vt_symbol_to_index_symbol(req.vt_symbol):
            # 指数订阅
            contract_list = self._get_all_index_trade_contract(req.vt_symbol)
            print(contract_list)
            for contract in contract_list:
                symbol, exchange = extract_vt_symbol(contract.vt_symbol)
                contract_req = SubscribeRequest(symbol, exchange)
                gateway.subscribe(contract_req)
            self.index_generator.subscribe(req)
        else:
            gateway.subscribe(req)

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """
        Query bar history data.
        """
        gateway = self.backend
        result = {}
        if gateway:
            if req.vt_symbol == vt_symbol_to_index_symbol(req.vt_symbol):
                contract_list = self._get_all_index_trade_contract(req.vt_symbol)
                print(contract_list)
                for contract in contract_list:
                    symbol, exchange = extract_vt_symbol(contract.vt_symbol)
                    contract_req = HistoryRequest(symbol, exchange, start=req.start, end=req.end, interval=req.interval)
                    result[contract.vt_symbol] = gateway.query_history(contract_req)
                return self.index_generator.query_history(result)
            else:
                return gateway.query_history(req)
        else:
            return None
