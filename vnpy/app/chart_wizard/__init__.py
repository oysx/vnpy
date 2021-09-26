from pathlib import Path
from vnpy.trader.app import BaseApp
from .engine import ChartWizardEngine, APP_NAME
from .engine_customized import CustomizedChartWizardEngine


class ChartWizardApp(BaseApp):
    """"""
    app_name = APP_NAME
    app_module = __module__
    app_path = Path(__file__).parent
    display_name = "K线图表"
    engine_class = CustomizedChartWizardEngine
    widget_name = "CustomizedChartWizardWidget"
    icon_name = "cw.ico"
