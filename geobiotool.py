from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider
from .geobiotool_algorithm import GeoBioToolAlgorithm
from . import resources  

class GeoBioToolProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(GeoBioToolAlgorithm())

    def id(self):
        return "geobiotool"

    def name(self):
        return "GeoBioTool"

    def longName(self):
        return "GeoBioTool: Biodiversity Indices"

class GeoBioToolPlugin:  
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.provider = None

    def initGui(self):
        self.action = QAction(QIcon(":/icons/icon.png"), "Run GeoBioTool", self.iface.mainWindow())
        self.action.triggered.connect(self.run_gui)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&GeoBioTool", self.action)

        from qgis.core import QgsApplication
        self.provider = GeoBioToolProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&GeoBioTool", self.action)

        from qgis.core import QgsApplication
        QgsApplication.processingRegistry().removeProvider(self.provider)

    def run_gui(self):
        raster_path, _ = QFileDialog.getOpenFileName(None, "Select classified raster", "", "TIFF files (*.tif *.tiff)")
        if not raster_path:
            return

        save_path, _ = QFileDialog.getSaveFileName(None, "Save output text", "", "Text files (*.txt)")
        if not save_path:
            return

        try:
            from osgeo import gdal
            import numpy as np
            from collections import Counter

            ds = gdal.Open(raster_path)
            band = ds.GetRasterBand(1)
            data = band.ReadAsArray().astype(np.float32)
            data[np.isnan(data)] = 0
            data[np.isinf(data)] = 0
            vals = data[(data > 0) & (data < 255)]
            cnt = Counter(vals)
            total = sum(cnt.values())

            def shannon(c):
                ps = [v / total for v in c.values()]
                return -sum(p * np.log(p) for p in ps if p > 0)

            def simpson(c):
                ps = [v / total for v in c.values()]
                return 1 - sum(p * p for p in ps)

            s = shannon(cnt)
            si = simpson(cnt)

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write("[GeoBioTool Results]\n")
                f.write(f"Total pixel count: {total}\n")
                f.write(f"Shannon-Wiener: {s:.4f}\n")
                f.write(f"Simpson: {si:.4f}\n")

            QMessageBox.information(None, "GeoBioTool", "Biodiversity indices saved successfully!")

        except Exception as e:
            QMessageBox.critical(None, "GeoBioTool Error", str(e))
