# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import variation
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

class GeoBioToolLAIVCIAlgorithm(QgsProcessingAlgorithm):

    def name(self) -> str:
        return "compute_lai_vci"

    def displayName(self) -> str:
        return "Compute LAI & VCI"

    def group(self) -> str:
        return "2 ASCII"

    def groupId(self) -> str:
        return "ascii"

    def icon(self) -> QIcon:
        return QIcon(":/icons/icon.png")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "INPUT", "Input ASCII File (.csv/.txt)",
            behavior=QgsProcessingParameterFile.File
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            "USE_GRID", "Use Grid Analysis", defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "GRID_SIZE", "Grid Size (m)",
            type=QgsProcessingParameterNumber.Integer, defaultValue=20
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_CSV", "Output CSV File", fileFilter="CSV files (*.csv)"
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_PNG_LAI", "Output LAI Heatmap PNG", fileFilter="PNG files (*.png)"
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_PNG_VCI", "Output VCI Heatmap PNG", fileFilter="PNG files (*.png)"
        ))

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict:
        inp         = self.parameterAsFile(parameters, "INPUT", context)
        use_grid    = self.parameterAsBool(parameters, "USE_GRID", context)
        gsz         = self.parameterAsInt(parameters, "GRID_SIZE", context)
        out_csv     = self.parameterAsFileOutput(parameters, "OUTPUT_CSV", context)
        out_png_lai = self.parameterAsFileOutput(parameters, "OUTPUT_PNG_LAI", context)
        out_png_vci = self.parameterAsFileOutput(parameters, "OUTPUT_PNG_VCI", context)

        try:
            df_all = pd.read_csv(inp, sep=r"\s+|,", engine="python", comment="#", encoding="utf-8")
        except Exception as e:
            raise QgsProcessingException(f"Cannot read input file: {e}")

        cols = {c.lower(): c for c in df_all.columns}
        xcol = next((orig for low, orig in cols.items() if low in ("x","x_coord","easting")), None)
        ycol = next((orig for low, orig in cols.items() if low in ("y","y_coord","northing")), None)
        zcol = next((orig for low, orig in cols.items() if low in ("z","z_coord","elevation","height")), None)
        if not (xcol and ycol and zcol):
            raise QgsProcessingException("Input must contain X, Y, Z columns (or synonyms)")

        df = df_all[[xcol, ycol, zcol]].copy().rename(columns={xcol:"x", ycol:"y", zcol:"z"})

        if use_grid:
            xmin, ymin = df.x.min(), df.y.min()
            df["xg"] = np.floor((df.x - xmin)/gsz)*gsz + xmin
            df["yg"] = np.floor((df.y - ymin)/gsz)*gsz + ymin
        else:
            df["xg"], df["yg"] = df["x"], df["y"]

        def compute_lai_vci(zvals, z0=3, dz=1):
            # filter points above z0
            above = zvals[zvals >= z0]
            if len(above) < 1:
                return np.nan, np.nan

            max_h = above.max()
            layers = np.arange(z0, max_h + dz, dz)

            # compute Ni = #points ≥ layers[i]
            counts = np.array([(above >= h).sum() for h in layers])

            # compute LAD per layer: LAD[i] = log(Ni / N(i+1))
            # note: skip last layer
            lad_vals = []
            for i in range(len(counts) - 1):
                Ni  = counts[i]
                Nj  = counts[i+1]
                if Ni > 0 and Nj > 0:
                    lad_vals.append(np.log(Ni / Nj))
                else:
                    lad_vals.append(np.nan)

            lai_val = float(np.nansum(lad_vals))  # sum of LAD gives LAI

            # VCI: coeff. of variation of histogram of 1m bins
            hist_counts, _ = np.histogram(above, bins=layers)
            if hist_counts.sum() > 0 and hist_counts.mean() != 0:
                vci_val = float(variation(hist_counts))
            else:
                vci_val = np.nan

            return lai_val, vci_val

        records = []
        for (yg, xg), sub in df.groupby(["yg","xg"]):
            if len(sub) < 20:
                continue
            zvals = sub["z"].values
            lai_val, vci_val = compute_lai_vci(zvals)
            records.append({"yg": yg, "xg": xg, "LAI": lai_val, "VCI": vci_val})

        out_df = pd.DataFrame.from_records(records)
        out_df.to_csv(out_csv, index=False, encoding="utf-8")
        feedback.pushInfo(f"Saved CSV: {out_csv}")

        if not out_df.empty:
            xs = np.sort(out_df["xg"].unique())
            ys = np.sort(out_df["yg"].unique())
            XX, YY = np.meshgrid(xs, ys)

            def pivot_mask(df_in, col):
                pv = df_in.pivot(index="yg", columns="xg", values=col)
                pv = pv.reindex(index=ys, columns=xs)
                return np.ma.masked_invalid(pv.values)

            Z_lai = pivot_mask(out_df, "LAI")
            plt.figure(figsize=(6,5))
            plt.pcolormesh(XX, YY, Z_lai, shading='auto')
            plt.colorbar(label="LAI")
            plt.xlabel("X")
            plt.ylabel("Y")
            plt.tight_layout()
            plt.savefig(out_png_lai, dpi=300)
            plt.close()
            feedback.pushInfo(f"Saved LAI PNG: {out_png_lai}")

            Z_vci = pivot_mask(out_df, "VCI")
            plt.figure(figsize=(6,5))
            plt.pcolormesh(XX, YY, Z_vci, shading='auto')
            plt.colorbar(label="VCI")
            plt.xlabel("X")
            plt.ylabel("Y")
            plt.tight_layout()
            plt.savefig(out_png_vci, dpi=300)
            plt.close()
            feedback.pushInfo(f"Saved VCI PNG: {out_png_vci}")

        return {
            "OUTPUT_CSV":    out_csv,
            "OUTPUT_PNG_LAI": out_png_lai,
            "OUTPUT_PNG_VCI": out_png_vci
        }

    def createInstance(self):
        return GeoBioToolLAIVCIAlgorithm()
