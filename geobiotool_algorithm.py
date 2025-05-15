from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString
)
from qgis.PyQt.QtGui import QIcon
from . import resources

from osgeo import gdal
import numpy as np
from collections import Counter


class GeoBioToolAlgorithm(QgsProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            "INPUT", "Input classified raster"))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT", "Output text file", fileFilter="Text files (*.txt)"))
        self.addParameter(QgsProcessingParameterString(
            "CLASSES", "Target classes (e.g., 1,4,6 or 0-9)", optional=True))

    def parse_classes(self, input_str):
        classes = set()
        if not input_str:
            return None
        tokens = input_str.split(',')
        for token in tokens:
            if '-' in token:
                start, end = map(int, token.split('-'))
                classes.update(range(start, end + 1))
            else:
                classes.add(int(token))
        return classes

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsRasterLayer(parameters, "INPUT", context)
        if layer is None:
            raise Exception("Cannot load raster layer. Check the input.")

        output_path = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        class_input = self.parameterAsString(parameters, "CLASSES", context)
        selected_classes = self.parse_classes(class_input)

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
        if selected_classes is not None:
            valid_values = flat[np.isin(flat, list(selected_classes))]
        else:
            valid_values = flat[(flat > 0) & (flat < 255)]

        count = Counter(valid_values)
        total = sum(count.values())
        if total == 0:
            raise Exception("No valid pixels found for selected class range.")

        def shannon(c):
            ps = [v / total for v in c.values()]
            return -sum(p * np.log(p) for p in ps if p > 0)

        def simpson(c):
            ps = [v / total for v in c.values()]
            return 1 - sum(p * p for p in ps)

        s = shannon(count)
        si = simpson(count)
        proportions = {k: v / total for k, v in count.items()}

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[GeoBioTool Results]\n")
            f.write(f"Total pixel count: {total}\n")
            f.write(f"Shannon-Wiener Index: {s:.4f}\n")
            f.write(f"Simpson Index: {si:.4f}\n\n")

            f.write("Class-wise Proportions (sorted by class):\n")
            for cls in sorted(proportions.keys()):
                f.write(f"Class {int(cls)}: {proportions[cls]:.4f} ({count[cls]} pixels)\n")

            f.write("\nClass-wise Proportions (sorted by proportion):\n")
            for cls, prop in sorted(proportions.items(), key=lambda x: x[1], reverse=True):
                f.write(f"Class {int(cls)}: {prop:.4f} ({count[cls]} pixels)\n")

        return {"OUTPUT": output_path}

    def name(self): return "geobiotool"
    def displayName(self): return "GeoBioTool: Compute Biodiversity Indices"
    def group(self): return "GeoBioTool Tools"
    def groupId(self): return "geobiotool_tools"
    def createInstance(self): return GeoBioToolAlgorithm()
    def icon(self): return QIcon(":/icons/icon.png")
