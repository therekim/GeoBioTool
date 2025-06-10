# -*- coding: utf-8 -*-
import numpy as np
from collections import Counter
from osgeo import gdal
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsProcessingParameterFileDestination,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingException
)
from qgis.PyQt.QtGui import QIcon

class GeoBioToolSimpsonAlgorithm(QgsProcessingAlgorithm):

    def name(self) -> str:
        return "compute_simpson_1949"

    def displayName(self) -> str:
        return "Compute Simpson (1949)"

    def group(self) -> str:
        return "1 Raster"

    def groupId(self) -> str:
        return "raster"

    def icon(self) -> QIcon:
        return QIcon(":/icons/icon.png")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            "INPUT", "Input classified raster"
        ))
        self.addParameter(QgsProcessingParameterString(
            "CLASSES", "Target classes (e.g., 1,4,6 or 0-9)", optional=True
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_TEXT", "Output text file", fileFilter="Text files (*.txt)"
        ))

    def parse_classes(self, s: str):
        if not s:
            return None
        classes = set()
        for token in s.split(','):
            token = token.strip()
            if '-' in token:
                a, b = map(int, token.split('-'))
                classes.update(range(a, b+1))
            else:
                classes.add(int(token))
        return classes

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict:
        layer    = self.parameterAsRasterLayer(parameters, "INPUT", context)
        selected = self.parse_classes(self.parameterAsString(parameters, "CLASSES", context))
        out_txt  = self.parameterAsFileOutput(parameters, "OUTPUT_TEXT", context)

        ds   = gdal.Open(layer.source())
        band = ds.GetRasterBand(1)
        data = band.ReadAsArray().astype(np.float32)
        data[np.isnan(data)] = 0
        data[np.isinf(data)] = 0
        flat = data.flatten()

        if selected:
            vals = flat[np.isin(flat, list(selected))]
        else:
            vals = flat[(flat > 0) & (flat < 255)]

        cnt   = Counter(vals)
        total = sum(cnt.values())
        if total == 0:
            raise QgsProcessingException("No valid pixels found.")
        ps    = [v/total for v in cnt.values()]
        si    = 1 - sum(p * p for p in ps)

        with open(out_txt, "w", encoding="utf-8") as f:
            f.write(f"Total pixels: {total}\n")
            f.write(f"Simpson Index: {si:.4f}\n\n")
            f.write("Class ID order and proportions:\n")
            for cls in sorted(cnt.keys()):
                f.write(f"  Class {int(cls)}: {cnt[cls]/total:.4f} ({cnt[cls]} pixels)\n")
            f.write("\nTop classes by proportion:\n")
            for cls, prop in sorted({k:v/total for k,v in cnt.items()}.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  Class {int(cls)}: {prop:.4f} ({cnt[cls]} pixels)\n")

        return {"OUTPUT_TEXT": out_txt}

    def createInstance(self):
        return GeoBioToolSimpsonAlgorithm()
