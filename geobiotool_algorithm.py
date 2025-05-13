from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFileDestination
)
from qgis.PyQt.QtGui import QIcon
from . import resources  # 아이콘 리소스 등록

from osgeo import gdal
import numpy as np
from collections import Counter


class GeoBioToolAlgorithm(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            "INPUT", "Input classified raster"))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT", "Output text file", fileFilter="Text files (*.txt)"))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsRasterLayer(parameters, "INPUT", context)
        if layer is None:
            raise Exception("Cannot load raster layer. Check the input.")

        output_path = self.parameterAsFileOutput(parameters, "OUTPUT", context)

        ds = gdal.Open(layer.source())
        if ds is None:
            raise Exception("Failed to open raster via GDAL.")

        band = ds.GetRasterBand(1)
        if band is None:
            raise Exception("No band 1 found in the raster.")

        data = band.ReadAsArray().astype(np.float32)
        data[np.isnan(data)] = 0
        data[np.isinf(data)] = 0

        flat = data.flatten()
        valid_values = flat[(flat > 0) & (flat < 255)]
        count = Counter(valid_values)
        total = sum(count.values())

        def shannon(c):
            ps = [v / total for v in c.values()]
            return -sum(p * np.log(p) for p in ps if p > 0)

        def simpson(c):
            ps = [v / total for v in c.values()]
            return 1 - sum(p * p for p in ps)

        s = shannon(count)
        si = simpson(count)

        # 클래스별 비율 계산
        proportions = {k: v / total for k, v in count.items()}

        # 우점종 3종 추출
        dominant = sorted(proportions.items(), key=lambda x: x[1], reverse=True)[:3]

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[GeoBioTool Results]\n")
            f.write(f"Total pixel count: {total}\n")
            f.write(f"Shannon-Wiener Index: {s:.4f}\n")
            f.write(f"Simpson Index: {si:.4f}\n\n")

            f.write("Class-wise Proportions:\n")
            for cls, p in sorted(proportions.items()):
                f.write(f"Class {int(cls)}: {p:.4f} ({count[cls]} pixels)\n")

            f.write("\nTop 3 Dominant Classes:\n")
            for cls, p in dominant:
                f.write(f"Class {int(cls)}: {p:.4f} ({count[cls]} pixels)\n")

        return {"OUTPUT": output_path}

    def name(self): return "geobiotool"
    def displayName(self): return "GeoBioTool: Compute Biodiversity Indices"
    def group(self): return "GeoBioTool Tools"
    def groupId(self): return "geobiotool_tools"
    def createInstance(self): return GeoBioToolAlgorithm()
    def icon(self): return QIcon(":/icons/icon.png")
