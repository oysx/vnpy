from datetime import datetime
from vnpy.trader.ui import QtWidgets
from .widget import ChartWizardWidget
from vnpy.trader.utility import load_json, save_json

from vnpy.trader.utility_customized import WrapIt, is_self


class CustomizedChartWizardWidget(ChartWizardWidget):
    def init_ui(self) -> None:
        def custom(hbox: QtWidgets.QHBoxLayout):
            if not is_self(self):
                return

            hbox.addWidget(QtWidgets.QLabel("Duration"))

            self.time_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self.params.get("time_line", ""))
            hbox.addWidget(self.time_line)
            self.symbol_line.setText(self.params.get("symbol_line", ""))
            self.chart_engine.widget = self

        with WrapIt(QtWidgets.QHBoxLayout, "addStretch", custom):
            # load
            self.filename: str = "chart_wizard.json"
            self.params = load_json(self.filename)

            super(CustomizedChartWizardWidget, self).init_ui()

    def new_chart(self) -> None:
        try:
            DT_FMT = "%Y.%m.%d_%H:%M:%S"
            duration = self.time_line.text()
            start, end = duration.split("-")
            start, end = datetime.strptime(start, DT_FMT), datetime.strptime(end, DT_FMT)
            self.config = {
                "time_start": start,
                "time_end": end,
            }
        except Exception as e:
            self.config = {}
            print(e)

        # save content to file
        self.params["symbol_line"] = self.symbol_line.text()
        self.params["time_line"] = self.time_line.text()
        save_json(self.filename, self.params)

        saved = self.main_engine.get_contract
        self.main_engine.get_contract = lambda x: True
        super(CustomizedChartWizardWidget, self).new_chart()
        self.main_engine.get_contract = saved

    def get_config(self):
        if not hasattr(self, "config"):
            return None

        return self.config
