from abc import ABC, abstractmethod
from typing import Any, Sequence, Dict, List, Optional, Callable, Set
from copy import copy

from .utility import vt_symbol_to_index_symbol, extract_sec_id, round_to
from vnpy.event import Event, EventEngine
from .event import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
    EVENT_QUOTE,
)
from .object import (
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    LogData,
    QuoteData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
    HistoryRequest,
    QuoteRequest,
    Exchange,
    BarData
)


class IndexGenerator(ABC):

    def __init__(self, main_engine, event_engine: EventEngine):
        self.main_engine = main_engine
        self.event_engine = event_engine

        self.subscribe_index_symbol: Set[str] = set()  # 保存已订阅的指数编号
        self.subscribe_index_contract: Dict[str, ContractData] = {}  # 指数合约
        self.subscribe_sec_id: Set[str] = set()  # 保存已经订阅的sec编号
        self.symbol_tick_dict: Dict[str, dict] = {}  # 保存每个指数的每个合约的最新tick
        self.symbol_last_tick: Dict[str, TickData] = {}  # 保存每个指数的下的最后一个tick

        self.register_event()

    def register_event(self):
        self.event_engine.register(EVENT_TICK, self.process_tick_event)

    def subscribe(self, req: SubscribeRequest):
        index_symbol_id = vt_symbol_to_index_symbol(req.vt_symbol)
        self.subscribe_index_symbol.add(index_symbol_id)
        sec_id = extract_sec_id(req.vt_symbol)
        self.subscribe_sec_id.add(sec_id)
        self.subscribe_index_contract[sec_id] = self.main_engine._get_index_contract(req.vt_symbol)

    def query_history(self, data: Dict[str, List[BarData]]) -> List[BarData]:
        result = []
        for group in zip(*data.values()):
            tick_data = group[0]
            sec_id = extract_sec_id(tick_data.symbol)

            index_tick = BarData(
                symbol=f"{sec_id}99",
                exchange=tick_data.exchange,
                datetime=tick_data.datetime,
                interval=tick_data.interval,
                gateway_name=tick_data.gateway_name,
            )
            for tick in group:
                index_tick.open_interest += tick.open_interest
            if index_tick.open_interest:
                for tick in group:
                    tick_weight = float(tick.open_interest) / index_tick.open_interest
                    index_tick.volume += tick.volume

                    index_tick.open_price += tick.open_price * tick_weight
                    index_tick.high_price += tick.high_price * tick_weight
                    index_tick.low_price += tick.low_price * tick_weight
                    index_tick.close_price += tick.close_price * tick_weight
                    # 价格取整到最小价位变动
                # price_tick = self.subscribe_index_contract[sec_id].pricetick
                #
                # index_tick.open_price = round_to(index_tick.open_price, price_tick)
                # index_tick.high_price = round_to(index_tick.high_price, price_tick)
                # index_tick.low_price = round_to(index_tick.low_price, price_tick)
                # index_tick.close_price = round_to(index_tick.close_price, price_tick)
                result.append(index_tick)

        return result

    def process_tick_event(self, event: Event):
        tick_data = event.data
        vt_symbol = tick_data.vt_symbol
        # 过滤掉指数数据
        if vt_symbol == vt_symbol_to_index_symbol(vt_symbol):
            return
        sec_id = extract_sec_id(vt_symbol)
        if sec_id not in self.subscribe_sec_id:
            return
        if tick_data.bid_price_1 > 9999999 or tick_data.ask_price_1 > 9999999:
            return
        # 下面合成最新的指数tick：每秒合成1个
        symbol_tick_dict = self.symbol_tick_dict.setdefault(sec_id, {})
        symbol_last_tick = self.symbol_last_tick.get(sec_id)
        if symbol_last_tick and tick_data.datetime.second != symbol_last_tick.datetime.second and symbol_tick_dict:
            index_tick = TickData(
                symbol=f"{sec_id}99",
                exchange=tick_data.exchange,
                datetime=tick_data.datetime,
                gateway_name=tick_data.gateway_name,
                name=self.subscribe_index_contract[sec_id].name
            )
            for tick in symbol_tick_dict.values():
                index_tick.open_interest += tick.open_interest
            if index_tick.open_interest:
                for tick in symbol_tick_dict.values():
                    tick_weight = float(tick.open_interest) / index_tick.open_interest
                    index_tick.last_price += tick.last_price * tick_weight
                    index_tick.volume += tick.volume
                    index_tick.last_volume += tick.last_volume
                    index_tick.limit_up += tick.limit_up * tick_weight
                    index_tick.limit_down += tick.limit_down * tick_weight

                    index_tick.open_price += tick.open_price * tick_weight
                    index_tick.high_price += tick.high_price * tick_weight
                    index_tick.low_price += tick.low_price * tick_weight
                    index_tick.pre_close += tick.pre_close * tick_weight

                    index_tick.bid_price_1 += tick.bid_price_1 * tick_weight
                    index_tick.ask_price_1 += tick.ask_price_1 * tick_weight
                    index_tick.bid_volume_1 += tick.bid_volume_1
                    index_tick.ask_volume_1 += tick.ask_volume_1

                    # 5档有需要再加进来吧，省点计算资源
                    # tick_data.ask_price_2 += tick.ask_price_2 * tick_weight
                    # tick_data.ask_price_3 += tick.ask_price_3 * tick_weight
                    # tick_data.ask_price_4 += tick.ask_price_4 * tick_weight
                    # tick_data.ask_price_5 += tick.ask_price_5 * tick_weight
                    # tick_data.bid_price_2 += tick.bid_price_2 * tick_weight
                    # tick_data.bid_price_3 += tick.bid_price_3 * tick_weight
                    # tick_data.bid_price_4 += tick.bid_price_4 * tick_weight
                    # tick_data.bid_price_5 += tick.bid_price_5 * tick_weight
                    # tick_data.bid_volume_2 += tick.bid_volume_2 * tick_weight
                    # tick_data.bid_volume_3 += tick.bid_volume_3 * tick_weight
                    # tick_data.bid_volume_4 += tick.bid_volume_4 * tick_weight
                    # tick_data.bid_volume_5 += tick.bid_volume_5 * tick_weight
                    # tick_data.ask_volume_2 += tick.ask_volume_2 * tick_weight
                    # tick_data.ask_volume_3 += tick.ask_volume_3 * tick_weight
                    # tick_data.ask_volume_4 += tick.ask_volume_4 * tick_weight
                    # tick_data.ask_volume_5 += tick.ask_volume_5 * tick_weight
                # 价格取整到最小价位变动
                price_tick = self.subscribe_index_contract[sec_id].pricetick
                index_tick.last_price = round_to(index_tick.last_price, price_tick)

                index_tick.bid_price_1 = round_to(index_tick.bid_price_1, price_tick)
                index_tick.ask_price_1 = round_to(index_tick.ask_price_1, price_tick)
                index_tick.limit_up = round_to(index_tick.limit_up, price_tick)
                index_tick.limit_down = round_to(index_tick.limit_down, price_tick)
                index_tick.open_price = round_to(index_tick.open_price, price_tick)
                index_tick.high_price = round_to(index_tick.high_price, price_tick)
                index_tick.low_price = round_to(index_tick.low_price, price_tick)
                index_tick.pre_close = round_to(index_tick.pre_close, price_tick)

                event = Event(EVENT_TICK, index_tick)
                self.event_engine.put(event)

        symbol_tick_dict[vt_symbol] = tick_data
        self.symbol_last_tick[sec_id] = tick_data
