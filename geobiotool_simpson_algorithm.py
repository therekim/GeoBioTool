# -*- coding: utf-8 -*-
import numpy as np
from collections import Counter
from osgeo import gdal
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingException
)
from qgis.PyQt.QtGui import QIcon

class GeoBioToolSimpsonAlgorithm(QgsProcessingAlgorithm):

    def name(self):
        return "compute_simpson_1949"
    def displayName(self):
        return "Compute Simpson (1949)"
    def group(self):
        return "1 Raster"
    def groupId(self):
        return "raster"
    def icon(self):
        return QIcon(":/icons/icon.png")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer("INPUT", ""))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT", "", fileFilter="Text files (*.txt)"))
        self.addParameter(QgsProcessingParameterString("CLASSES", "", optional=True))

    def parse_classes(self, s):
        if not s: return None
        cs = set()
        for t in s.split(','):
            t = t.strip()
            if '-' in t:
                a, b = map(int, t.split('-'))
                cs.update(range(a, b+1))
            else:
                cs.add(int(t))
        return cs

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback):
        layer = self.parameterAsRasterLayer(parameters, "INPUT", context)
        out   = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        sel   = self.parse_classes(self.parameterAsString(parameters, "CLASSES", context))

        ds   = gdal.Open(layer.source()); band = ds.GetRasterBand(1)
        data = band.ReadAsArray().astype(np.float32)
        data[np.isnan(data)] = 0; data[np.isinf(data)] = 0
        flat = data.flatten()
        valid = flat[np.isin(flat, list(sel))] if sel else flat[(flat>0)&(flat<255)]

        cnt    = Counter(valid); total = sum(cnt.values())
        if total == 0:
            raise QgsProcessingException("No valid pixels")

        # Simpson
        ps    = [v/total for v in cnt.values()]
        si_idx = 1 - sum(p*p for p in ps)

        props = {k: v/total for k, v in cnt.items()}

        with open(out, "w", encoding="utf-8") as f:
            f.write(f"Total pixels: {total}\n")
            f.write(f"Simpson: {si_idx:.4f}\n\n")

            f.write("By class (asc):\n")
            for k in sorted(props):
                f.write(f"  {int(k)}: {props[k]:.4f} ({cnt[k]} pixels)\n")

            f.write("\nBy proportion (desc):\n")
            for k, p in sorted(props.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {int(k)}: {p:.4f} ({cnt[k]} pixels)\n")

        return {"OUTPUT": out}

    def createInstance(self):
        return GeoBioToolSimpsonAlgorithm()
