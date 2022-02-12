from datetime import datetime
from vnpy.trader.ui import QtWidgets
from .widget import ChartWizardWidget
from vnpy.trader.utility import load_json, save_json

from vnpy.trader.utility_customized import WrapIt, is_self
from vnpy.trader.constant import Interval
from time import sleep
from threading import Thread
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.database import database_manager
from vnpy.event import Event
EVENT_CHART_HISTORY = "eChartHistory"


class CustomizedChartWizardWidget(ChartWizardWidget):
    def init_ui(self) -> None:
        def custom(hbox: QtWidgets.QHBoxLayout):
            if not is_self(self):
                return

            hbox.addWidget(QtWidgets.QLabel("Duration"))
            hbox.addWidget(QtWidgets.QLabel("Interval"))

            self.time_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self.params.get("time_line", ""))
            self.time_interval: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self.params.get("time_interval", ""))
            hbox.addWidget(self.time_line)
            hbox.addWidget(self.time_interval)

            self.animation = QtWidgets.QPushButton("animation")
            self.animation.clicked.connect(self.switch_animation)
            hbox.addWidget(self.animation)
            hbox.addWidget(QtWidgets.QLabel("animation"))
            self.animation_interval: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self.params.get("animation_interval", "0.5"))
            hbox.addWidget(self.animation_interval)
            self.animation_pause = False

            self.symbol_line.setText(self.params.get("symbol_line", ""))
            self.chart_engine.widget = self

        # with WrapIt(QtWidgets.QHBoxLayout, "addStretch", custom):
        #     # load
        #     self.filename: str = "chart_wizard.json"
        #     self.params = load_json(self.filename)
        #
        #     super(CustomizedChartWizardWidget, self).init_ui()

        super(CustomizedChartWizardWidget, self).init_ui()
        # find out hbox
        hbox = self.findChildren(QtWidgets.QVBoxLayout)[0].children()[0]
        self.filename: str = "chart_wizard.json"
        self.params = load_json(self.filename)
        custom(hbox)

    def new_chart(self) -> None:
        try:
            DT_FMT = "%Y.%m.%d_%H:%M:%S"
            duration = self.time_line.text()
            interval = self.time_interval.text()
            start, end = duration.split("-")
            start, end = datetime.strptime(start, DT_FMT), datetime.strptime(end, DT_FMT)
            animation_interval = float(self.animation_interval.text())
            self.config = {
                "time_start": start,
                "time_end": end if animation_interval <= 0 else start,
                "time_interval": interval,
                "time_animation_end": end,
                "animation_interval": animation_interval,
            }
        except Exception as e:
            self.config = {}
            print(e)

        # save content to file
        self.params["symbol_line"] = self.symbol_line.text()
        self.params["time_line"] = self.time_line.text()
        self.params["time_interval"] = self.time_interval.text()
        self.params["animation_interval"] = self.animation_interval.text()
        save_json(self.filename, self.params)

        saved = self.main_engine.get_contract
        self.main_engine.get_contract = lambda x: True
        super(CustomizedChartWizardWidget, self).new_chart()
        self.main_engine.get_contract = saved
        if self.config["animation_interval"] > 0:
            self.thread_update = Thread(target=self.update)
            self.thread_update.start()
            self.animation_exit = False

    def get_config(self):
        if not hasattr(self, "config"):
            return None

        return self.config

    def switch_animation(self):
        self.animation_pause = not self.animation_pause

    def closeEvent(self, event):
        super().closeEvent(event)
        if hasattr(self, "thread_update"):
            self.animation_exit = True
            self.thread_update.join()

    def update(self):
        print("Starting steps")
        vt_symbol = self.symbol_line.text()
        symbol, exchange = extract_vt_symbol(vt_symbol)
        interval = self.config["animation_interval"]

        history = database_manager.load_bar_data(
            symbol,
            exchange,
            Interval.MINUTE,
            self.config["time_start"],
            self.config["time_animation_end"]
        )

        for i in range(len(history)-1):
            start = history[i].datetime
            end = history[i+1].datetime
            print(start)
            data = database_manager.load_bar_data(
                symbol,
                exchange,
                Interval.MINUTE,
                start,
                end
            )

            event = Event(EVENT_CHART_HISTORY, data)
            self.event_engine.put(event)
            sleep(interval)

            if hasattr(self, "animation_exit"):
                if self.animation_exit:
                    return

            # check if we need to pause
            while self.animation_pause:
                sleep(1)
