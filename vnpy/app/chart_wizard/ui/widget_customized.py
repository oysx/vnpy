from datetime import datetime
from vnpy.trader.ui import QtWidgets
from .widget import ChartWizardWidget
import traceback
from vnpy.trader.utility import load_json, save_json


class WrapIt(object):
    def __init__(self, cls, name, func):
        self.cls = cls
        self.name = name
        self.func = func
        self.origin = getattr(cls, name)

    def wrap(self):
        def origin(*args, **kwargs):
            self.func(*args, **kwargs)
            return self.origin(*args, **kwargs)

        return origin

    def __enter__(self):
        setattr(self.cls, self.name, self.wrap())
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        # setattr(self.cls, self.name, self.origin)
        pass


class CustomizedChartWizardWidget(ChartWizardWidget):
    def init_ui(self) -> None:
        def custom(hbox: QtWidgets.QHBoxLayout):
            for tb in traceback.walk_stack(None):
                caller = tb[0].f_locals.get("self")
                if caller and caller is self:
                    print("Execute custom")
                    break
            else:
                print("Skip custom")
                return

            hbox.addWidget(QtWidgets.QLabel("Duration"))

            self.time_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self.params.get("time_line", ""))
            hbox.addWidget(self.time_line)
            self.symbol_line.setText(self.params.get("symbol_line", ""))

            # for i in hbox.count():
            #     widget = hbox.itemAt(i).widget()
            #     if widget is self.symbol_line:
            #         self.symbol_line.setText(self.params.get("symbol_line", ""))
            #         break

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
