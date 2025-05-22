# geobiotool_fhd_algorithm.py
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFileDestination,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingException
)
from qgis.PyQt.QtGui import QIcon

class GeoBioToolFHDAlgorithm(QgsProcessingAlgorithm):

    def name(self) -> str:
        return "compute_fhd_index_macarthur_1961"

    def displayName(self) -> str:
        return "Compute FHD Index (MacArthur & MacArthur, 1961)"

    def group(self) -> str:
        return "2 ASCII"

    def groupId(self) -> str:
        return "ascii"

    def icon(self) -> QIcon:
        return QIcon(":/icons/icon.png")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "INPUT",
            "Input ASCII File (.csv/.txt)",
            behavior=QgsProcessingParameterFile.File
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            "USE_GRID",
            "Use Grid Analysis",
            defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "GRID_SIZE",
            "Grid Size",
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=20
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_CSV",
            "Output CSV File",
            fileFilter="CSV files (*.csv)"
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_PNG",
            "Output Heatmap PNG",
            fileFilter="PNG files (*.png)"
        ))

    def processAlgorithm(
        self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> dict:
        inp      = self.parameterAsFile(parameters, "INPUT", context)
        use_grid = self.parameterAsBool(parameters, "USE_GRID", context)
        grid     = self.parameterAsInt(parameters, "GRID_SIZE", context)
        out_csv  = self.parameterAsFileOutput(parameters, "OUTPUT_CSV", context)
        out_png  = self.parameterAsFileOutput(parameters, "OUTPUT_PNG", context)

        # load CSV or whitespace-delimited ASCII
        df = None
        try:
            tmp = pd.read_csv(inp, sep=",", engine="python", encoding="utf-8")
            tmp.columns = [c.strip().lower() for c in tmp.columns]
            if {"x","y","z"}.issubset(tmp.columns):
                df = tmp[["x","y","z"]].copy()
        except:
            pass
        if df is None:
            tmp = pd.read_csv(inp, sep=r"\s+", engine="python", comment="#", encoding="utf-8")
            tmp.columns = [c.strip().lower() for c in tmp.columns]
            if {"x","y","z"}.issubset(tmp.columns):
                df = tmp[["x","y","z"]].copy()
        if df is None:
            raise QgsProcessingException("Invalid file: must contain columns X, Y, Z")

        # FHD calculation function
        def compute_fhd(zvals):
            bins = np.arange(np.min(zvals), np.max(zvals) + 0.5, 0.5)
            h, _ = np.histogram(zvals, bins=bins)
            p = h[h>0] / h.sum()
            return -np.sum(p * np.log(p)) if len(p)>0 else np.nan

        # zone-wise calculation
        results = []
        if use_grid:
            xmin, xmax = df.x.min(), df.x.max()
            ymin, ymax = df.y.min(), df.y.max()
            x_edges = np.arange(xmin, xmax + grid, grid)
            y_edges = np.arange(ymin, ymax + grid, grid)
            for i in range(len(x_edges)-1):
                for j in range(len(y_edges)-1):
                    cell = df[(df.x>=x_edges[i]) & (df.x< x_edges[i+1]) &
                              (df.y>=y_edges[j]) & (df.y< y_edges[j+1])]
                    if len(cell) < 20: 
                        continue
                    fhd = compute_fhd(cell.z.values)
                    results.append({
                        "x_min":     x_edges[i],
                        "y_min":     y_edges[j],
                        "point_count": len(cell),
                        "zmean":       cell.z.mean(),
                        "zmax":        cell.z.max(),
                        "FHD":         fhd
                    })
        else:
            z = df.z.values
            results.append({
                "x_min":       df.x.min(),
                "y_min":       df.y.min(),
                "point_count": len(z),
                "zmean":       z.mean(),
                "zmax":        z.max(),
                "FHD":         compute_fhd(z)
            })

        df_out = pd.DataFrame(results)
        df_out.to_csv(out_csv, index=False, encoding="utf-8")
        feedback.pushInfo(f"Saved CSV: {out_csv}")

        # heatmap
        if use_grid and not df_out.empty:
            pivot = df_out.pivot(index="y_min", columns="x_min", values="FHD")
            X, Y = np.meshgrid(np.sort(pivot.columns), np.sort(pivot.index))
            Z    = np.ma.masked_invalid(pivot.values)
            fig, ax = plt.subplots(figsize=(8,6))
            mesh = ax.pcolormesh(X, Y, Z, shading="auto")
            fig.colorbar(mesh, ax=ax, label="FHD")
            ax.set_aspect("equal")
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            fig.tight_layout()
            fig.savefig(out_png, dpi=300)
            plt.close(fig)
            feedback.pushInfo(f"Saved PNG: {out_png}")

        return {"OUTPUT_CSV": out_csv, "OUTPUT_PNG": out_png}

    def createInstance(self):
        return GeoBioToolFHDAlgorithm()
