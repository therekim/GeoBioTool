# -*- coding: utf-8 -*-
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
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

class GeoBioToolFHDAlgorithm(QgsProcessingAlgorithm):

    def name(self) -> str:
        """유니크 ID"""
        return "compute_fhd"

    def displayName(self) -> str:
        """툴박스에 보일 이름"""
        return "GeoBioTool: Compute FHD Index from ASCII Point File (CSV/TXT)"

    def group(self) -> str:
        """툴 그룹명"""
        return "GeoBioTool Tools"

    def groupId(self) -> str:
        """툴 그룹 ID"""
        return "geobiotool_tools"

    def createInstance(self):
        """새 인스턴스 생성"""
        return GeoBioToolFHDAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                'INPUT',
                'Input ASCII File (.csv/.txt)',
                behavior=QgsProcessingParameterFile.File
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                'USE_GRID',
                'Use Grid Analysis',
                defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                'GRID_SIZE',
                'Grid Size',
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=20
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                'OUTPUT_CSV',
                'Output CSV File',
                fileFilter='CSV files (*.csv)'
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                'OUTPUT_PNG',
                'Output Heatmap PNG',
                fileFilter='PNG files (*.png)'
            )
        )

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict:
        # 파라미터 읽기
        inp = self.parameterAsFile(parameters, 'INPUT', context)
        use_grid = self.parameterAsBool(parameters, 'USE_GRID', context)
        grid = self.parameterAsInt(parameters, 'GRID_SIZE', context)
        out_csv = self.parameterAsFileOutput(parameters, 'OUTPUT_CSV', context)
        out_png = self.parameterAsFileOutput(parameters, 'OUTPUT_PNG', context)

        # 파일 로드
        df = None
        for delim in [',', '\t', ' ']:
            try:
                tmp = pd.read_csv(inp, delimiter=delim, engine='python', encoding='utf-8')
                tmp.columns = [c.strip().lower() for c in tmp.columns]
                if {'x','y','z'}.issubset(tmp.columns):
                    df = tmp[['x','y','z']].copy()
                    break
            except Exception:
                continue
        if df is None:
            raise QgsProcessingException("Invalid file: must contain columns X, Y, Z")

        # FHD 계산 함수
        def compute_fhd(zvals):
            if len(zvals) < 20:
                return None
            bins = np.arange(np.min(zvals), np.max(zvals)+0.5, 0.5)
            h, _ = np.histogram(zvals, bins=bins)
            p = h[h>0] / h.sum()
            return -np.sum(p * np.log(p))

        # 분석
        results = []
        if use_grid:
            xmin, xmax = df.x.min(), df.x.max()
            ymin, ymax = df.y.min(), df.y.max()
            x_edges = np.arange(xmin, xmax+grid, grid)
            y_edges = np.arange(ymin, ymax+grid, grid)
            for i in range(len(x_edges)-1):
                for j in range(len(y_edges)-1):
                    cell = df[(df.x>=x_edges[i]) & (df.x< x_edges[i+1]) &
                              (df.y>=y_edges[j]) & (df.y< y_edges[j+1])]
                    if len(cell) < 20:
                        continue
                    fhd = compute_fhd(cell.z.values)
                    results.append({
                        'x_min': x_edges[i],
                        'y_min': y_edges[j],
                        'point_count': len(cell),
                        'zmean': cell.z.mean(),
                        'zmax': cell.z.max(),
                        'FHD': fhd
                    })
            df_out = pd.DataFrame(results)
        else:
            z = df.z.values
            df_out = pd.DataFrame([{
                'x_min': df.x.min(),
                'y_min': df.y.min(),
                'point_count': len(z),
                'zmean': z.mean(),
                'zmax': z.max(),
                'FHD': compute_fhd(z)
            }])

        # CSV 저장
        df_out.to_csv(out_csv, index=False)
        feedback.pushInfo(f"Saved CSV: {out_csv}")

        # 히트맵 저장
        if use_grid and not df_out.empty:
            pivot = df_out.pivot(index='y_min', columns='x_min', values='FHD')
            X, Y = np.meshgrid(np.sort(pivot.columns), np.sort(pivot.index))
            Z = np.ma.masked_invalid(pivot.values)
            fig, ax = plt.subplots(1,1, figsize=(8,6))
            c = ax.pcolormesh(X, Y, Z, shading='auto')
            fig.colorbar(c, ax=ax, label="FHD")
            ax.set_aspect('equal')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            fig.tight_layout()
            fig.savefig(out_png, dpi=300)
            plt.close(fig)
            feedback.pushInfo(f"Saved PNG: {out_png}")

        return {'OUTPUT_CSV': out_csv, 'OUTPUT_PNG': out_png}
