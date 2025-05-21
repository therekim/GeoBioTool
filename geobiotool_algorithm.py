# -*- coding: utf-8 -*-
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
from . import resources
from osgeo import gdal
import numpy as np
from collections import Counter

class GeoBioToolAlgorithm(QgsProcessingAlgorithm):

    def name(self) -> str:
        """유니크 ID (소문자, 언더바)"""
        return "geobiotool"

    def displayName(self) -> str:
        """툴박스에 보일 이름"""
        return "GeoBioTool: Compute Biodiversity Indices"

    def group(self) -> str:
        """툴이 속할 그룹명 (한글/영문 혼합 가능)"""
        return "GeoBioTool Tools"

    def groupId(self) -> str:
        """툴 그룹의 고유 ID (영문 소문자/언더바)"""
        return "geobiotool_tools"

    def createInstance(self):
        """새 인스턴스 생성"""
        return GeoBioToolAlgorithm()

    def icon(self) -> QIcon:
        """툴바/메뉴 아이콘"""
        return QIcon(":/icons/icon.png")

    def initAlgorithm(self, config=None):
        # 입력 래스터 레이어 (분류된 래스터)
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                "INPUT",
                "Input classified raster"
            )
        )
        # 출력 텍스트 파일
        self.addParameter(
            QgsProcessingParameterFileDestination(
                "OUTPUT",
                "Output text file",
                fileFilter="Text files (*.txt)"
            )
        )
        # 선택할 클래스 라벨 (예: 1,4,6 or 0-9)
        self.addParameter(
            QgsProcessingParameterString(
                "CLASSES",
                "Target classes (e.g., 1,4,6 or 0-9)",
                optional=True
            )
        )

    def parse_classes(self, input_str: str):
        """'1,3-5' 같은 문자열을 집합으로 반환"""
        if not input_str:
            return None
        classes = set()
        for token in input_str.split(','):
            token = token.strip()
            if '-' in token:
                start, end = map(int, token.split('-'))
                classes.update(range(start, end + 1))
            else:
                classes.add(int(token))
        return classes

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict:
        # 1) 레이어 로드
        layer = self.parameterAsRasterLayer(parameters, "INPUT", context)
        if layer is None:
            raise QgsProcessingException("Cannot load raster layer. Check the input.")

        # 2) 파라미터 취득
        output_path = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        class_input = self.parameterAsString(parameters, "CLASSES", context)
        selected = self.parse_classes(class_input)

        # 3) GDAL 열기
        ds = gdal.Open(layer.source())
        if ds is None:
            raise QgsProcessingException("Failed to open raster via GDAL.")
        band = ds.GetRasterBand(1)
        if band is None:
            raise QgsProcessingException("No band 1 found in the raster.")

        # 4) 배열 읽기 & NaN/Inf 제거
        data = band.ReadAsArray().astype(np.float32)
        data[np.isnan(data)] = 0
        data[np.isinf(data)] = 0

        # 5) 클래스 필터링
        flat = data.flatten()
        if selected is not None:
            valid = flat[np.isin(flat, list(selected))]
        else:
            valid = flat[(flat > 0) & (flat < 255)]

        # 6) 빈도 계산 및 지수 정의
        from collections import Counter
        count = Counter(valid)
        total = sum(count.values())
        if total == 0:
            raise QgsProcessingException("No valid pixels found for selected class range.")

        def shannon(cnt):
            ps = [v/total for v in cnt.values()]
            return -sum(p*np.log(p) for p in ps if p>0)

        def simpson(cnt):
            ps = [v/total for v in cnt.values()]
            return 1 - sum(p*p for p in ps)

        s_idx = shannon(count)
        si_idx = simpson(count)
        props = {k: v/total for k,v in count.items()}

        # 7) 결과 쓰기
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[GeoBioTool Results]\n")
            f.write(f"Total pixel count: {total}\n")
            f.write(f"Shannon-Wiener Index: {s_idx:.4f}\n")
            f.write(f"Simpson Index: {si_idx:.4f}\n\n")

            f.write("Class-wise Proportions (sorted by class):\n")
            for cls in sorted(props.keys()):
                f.write(f"Class {int(cls)}: {props[cls]:.4f} ({count[cls]} pixels)\n")

            f.write("\nClass-wise Proportions (sorted by proportion):\n")
            for cls, prop in sorted(props.items(), key=lambda x: x[1], reverse=True):
                f.write(f"Class {int(cls)}: {prop:.4f} ({count[cls]} pixels)\n")

        # 8) 반환
        return {"OUTPUT": output_path}
