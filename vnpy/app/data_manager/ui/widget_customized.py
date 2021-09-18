from vnpy.trader.ui import QtWidgets
from .widget import ManagerWidget
from vnpy.trader.utility_customized import is_self, WrapIt
from vnpy.trader.utility import generate_vt_symbol
from vnpy.app.chart_wizard.ui.widget_customized import CustomizedChartWizardWidget
from functools import partial
import datetime


class CustomizedManagerWidget(ManagerWidget):
    def init_ui(self) -> None:
        def custom(hbox: QtWidgets.QHBoxLayout):
            if not is_self(self):
                return

            download_button = QtWidgets.QPushButton("CHART")
            download_button.clicked.connect(self.chart_data)

            hbox.addWidget(download_button)

        with WrapIt(QtWidgets.QHBoxLayout, "addStretch", custom):
            super(CustomizedManagerWidget, self).init_ui()

    def init_tree(self) -> None:
        super(CustomizedManagerWidget, self).init_tree()

        old = self.tree.columnCount()
        self.tree.setColumnCount(old+1)

    def refresh_tree(self) -> None:
        super(CustomizedManagerWidget, self).refresh_tree()
        overviews = self.engine.get_bar_overview()

        for overview in overviews:
            key = (overview.symbol, overview.exchange, overview.interval)
            item = self.tree_items.get(key, None)

            if not item:
                return

            output_button = QtWidgets.QPushButton("CHART")
            func = partial(self.chart_data, overview)
            output_button.clicked.connect(func)
            self.tree.setItemWidget(item, 10, output_button)

    def chart_data(self, overview) -> None:
        """"""
        print("hello world")
        chart = CustomizedChartWizardWidget(self.engine.main_engine, self.engine.event_engine)

        # set symbol_line and time_line Editor
        vt_symbol = generate_vt_symbol(overview.symbol, overview.exchange)
        start = overview.start.strftime("%Y.%m.%d_%H:%M:%S")
        end = overview.end.strftime("%Y.%m.%d_%H:%M:%S")
        chart.symbol_line.setText(vt_symbol)
        chart.time_line.setText(start + "-" + end)

        chart.show()
