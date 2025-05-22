# geobiotool_rumple_algorithm.py
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

class GeoBioToolRumpleAlgorithm(QgsProcessingAlgorithm):

    def name(self) -> str:
        return "compute_rumple_index_parker_2004"

    def displayName(self) -> str:
        return "Compute Rumple Index (Parker et al. 2004)"

    def group(self) -> str:
        return "2 ASCII"

    def groupId(self) -> str:
        return "ascii"

    def icon(self) -> QIcon:
        return QIcon(":/icons/icon.png")

    def tags(self) -> list[str]:
        return ["rumple", "canopy", "surface", "parker"]

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
            "Grid Size (m)",
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
            "Output Rumple Heatmap PNG",
            fileFilter="PNG files (*.png)"
        ))

    def processAlgorithm(
        self,
        parameters: dict,
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback
    ) -> dict:
        inp      = self.parameterAsFile(parameters, "INPUT", context)
        use_grid = self.parameterAsBool(parameters, "USE_GRID", context)
        gsz      = self.parameterAsInt(parameters, "GRID_SIZE", context)
        out_csv  = self.parameterAsFileOutput(parameters, "OUTPUT_CSV", context)
        out_png  = self.parameterAsFileOutput(parameters, "OUTPUT_PNG", context)

        try:
            df_all = pd.read_csv(inp, sep=r"\s+|,", engine="python", comment="#", encoding="utf-8")
        except Exception as e:
            raise QgsProcessingException(f"Cannot read input file: {e}")

        cols_map = {col.lower(): col for col in df_all.columns}
        x_col = next((orig for low, orig in cols_map.items() if low in ["x", "x_coord", "easting"]), None)
        y_col = next((orig for low, orig in cols_map.items() if low in ["y", "y_coord", "northing"]), None)
        z_col = next((orig for low, orig in cols_map.items() if low in ["z", "z_coord", "elevation", "height"]), None)
        if not all([x_col, y_col, z_col]):
            raise QgsProcessingException("Input must contain X, Y, Z columns or synonyms")

        df = df_all[[x_col, y_col, z_col]].copy()
        df.columns = ["x", "y", "z"]

        if use_grid:
            xmin, ymin = df["x"].min(), df["y"].min()
            df["xg"] = np.floor((df["x"] - xmin) / gsz) * gsz + xmin
            df["yg"] = np.floor((df["y"] - ymin) / gsz) * gsz + ymin
        else:
            df["xg"], df["yg"] = df["x"], df["y"]

        def rumple(group):
            zvals = group["z"].values
            mu, sd = zvals.mean(), zvals.std()
            return sd / mu if mu != 0 else np.nan

        df_out = df.groupby(["yg", "xg"]).apply(rumple).reset_index(name="rumple_index")

        df_out.to_csv(out_csv, index=False, encoding="utf-8")
        feedback.pushInfo(f"Saved CSV: {out_csv}")

        if not df_out.empty:
            pivot = df_out.pivot(index="yg", columns="xg", values="rumple_index")
            X, Y = np.meshgrid(np.sort(pivot.columns), np.sort(pivot.index))
            Z    = np.ma.masked_invalid(pivot.values)
            fig, ax = plt.subplots()
            mesh    = ax.pcolormesh(X, Y, Z, shading="auto")
            fig.colorbar(mesh, ax=ax, label="Rumple Index")
            ax.set_aspect("equal")
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            fig.tight_layout()
            fig.savefig(out_png, dpi=300)
            plt.close(fig)
            feedback.pushInfo(f"Saved PNG: {out_png}")

        return {"OUTPUT_CSV": out_csv, "OUTPUT_PNG": out_png}

    def createInstance(self):
        return GeoBioToolRumpleAlgorithm()
