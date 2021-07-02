import sys

from vnpy.event import Event
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    SubscribeRequest,
    CancelRequest,
    OrderRequest
)

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import ContractData, TickData, HistoryRequest, BarData
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
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.index_generator import extract_sec_id, vt_symbol_to_index_symbol
from typing import List
from vnpy.trader.index_generator import IndexGenerator, is_index_contract
from vnpy.gateway.ctp import CtpGateway
from vnpy.gateway.tqsdk import TqsdkGateway


class VirtualGateway(TqsdkGateway):
    """
    VN Trader Gateway for complement index contract API.
    """

    def __init__(self, event_engine, gateway_name: str = "VIRTUAL"):
        """Constructor"""
        event_engine.register(EVENT_CONTRACT, self.process_contract_event)
        self.backend = None
        self.contracts = {}
        self.index_generator: IndexGenerator = IndexGenerator(self, event_engine)
        super().__init__(event_engine, gateway_name)

    def connect(self, setting: dict):
        """"""
        return super(VirtualGateway, self).connect(setting)

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

                self.contracts[index_symbol_id] = index_contract
                self.on_contract(index_contract)

    def _get_all_index_trade_contract(self, vt_symbol):
        # 查询该合约对应品种的所有在市合约
        contract_list = []
        target_sec_id = extract_sec_id(vt_symbol)
        contracts = self.contracts
        for vt_symbol, contract_data in contracts.items():
            sec_id = extract_sec_id(vt_symbol)
            if target_sec_id == sec_id and not is_index_contract(vt_symbol):
                contract_list.append(contract_data)
        return contract_list

    def _get_index_contract(self, vt_symbol):
        contract_id = vt_symbol_to_index_symbol(vt_symbol)
        return self.contracts.get(contract_id, None)

    def subscribe(self, req: SubscribeRequest):
        """"""
        # 同类账户全部订阅
        if req.vt_symbol == vt_symbol_to_index_symbol(req.vt_symbol):
            # 指数订阅
            contract_list = self._get_all_index_trade_contract(req.vt_symbol)
            print(contract_list)
            for contract in contract_list:
                symbol, exchange = extract_vt_symbol(contract.vt_symbol)
                contract_req = SubscribeRequest(symbol, exchange)
                super(VirtualGateway, self).subscribe(contract_req)
            self.index_generator.subscribe(req)
        else:
            super(VirtualGateway, self).subscribe(req)

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """
        Query bar history data.
        """
        result = {}
        if req.vt_symbol == vt_symbol_to_index_symbol(req.vt_symbol):
            contract_list = self._get_all_index_trade_contract(req.vt_symbol)
            print(contract_list)
            for contract in contract_list:
                symbol, exchange = extract_vt_symbol(contract.vt_symbol)
                contract_req = HistoryRequest(symbol, exchange, start=req.start, end=req.end, interval=req.interval)
                result[contract.vt_symbol] = super(VirtualGateway, self).query_history(contract_req)
            return self.index_generator.query_history(result)
        else:
            return super(VirtualGateway, self).query_history(req)

#################################
    # def process_timer_event(self, event: Event):
    #     """"""
    #     return self.backend.process_timer_event(event)
    #
    # def send_order(self, req: OrderRequest):
    #     """"""
    #     return self.backend.send_order(req)
    #
    # def cancel_order(self, req: CancelRequest):
    #     """"""
    #     return self.backend.cancel_order(req)
    #
    # def query_account(self):
    #     """"""
    #     return self.backend.query_account()
    #
    # def query_position(self):
    #     """"""
    #     return self.backend.query_position()
    #
    # def close(self):
    #     """"""
    #     return self.backend.close()
