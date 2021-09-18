""""""
from datetime import datetime

from vnpy.event import Event
from vnpy.trader.constant import Interval
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.database import database_manager
from .engine import ChartWizardEngine, EVENT_CHART_HISTORY


class CustomizedChartWizardEngine(ChartWizardEngine):
    def _query_history(
        self,
        vt_symbol: str,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> None:
        config = self.widget.get_config()
        time_start = config.get("time_start")
        time_end = config.get("time_end")
        if time_start and time_end:
            # Load data from database
            start = time_start
            end = time_end

            symbol, exchange = extract_vt_symbol(vt_symbol)
            data = database_manager.load_bar_data(
                symbol,
                exchange,
                interval,
                start,
                end
            )

            event = Event(EVENT_CHART_HISTORY, data)
            self.event_engine.put(event)
        else:
            return super(CustomizedChartWizardEngine, self)._query_history(vt_symbol, interval, start, end)