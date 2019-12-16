import io
from fontTools.ttLib import TTFont
from fontTools.pens.pointPen import PointToSegmentPen
import freetype
from ..mac.makePathFromOutline import makePathFromOutline


class FTFont:

    @classmethod
    def fromPath(cls, path, **kwargs):
        with open(path, "rb") as f:
            fontData = f.read()
        return cls(fontData, **kwargs)

    def __init__(self, fontData, *, fontNumber=0, ttFont=None):
        if ttFont is None:
            stream = io.BytesIO(fontData)
            ttFont = TTFont(stream, fontNumber=fontNumber, lazy=True)
        self._ttFont = ttFont
        stream = io.BytesIO(fontData)
        self._ftFace = freetype.Face(stream, index=fontNumber)
        self._ftFace.set_char_size(self._ftFace.units_per_EM)

    def setVariableFontLocation(self, location):
        if "fvar" not in self._ttFont:
            return
        coordinates = []
        for axis in self._ttFont["fvar"].axes:
            coordinates.append(location.get(axis.axisTag, axis.defaultValue))
        coordinates = [round(v * 0x10000) for v in coordinates]
        c_coordinates = (freetype.FT_Fixed * len(coordinates))(*coordinates)
        freetype.FT_Set_Var_Design_Coordinates(self._ftFace._FT_Face, len(coordinates), c_coordinates)

    def drawGlyphToPointPen(self, glyphName, pen):
        glyphID = self._ttFont.getGlyphID(glyphName)
        face = self._ftFace
        face.load_glyph(glyphID, freetype.FT_LOAD_NO_SCALE)
        contours = (i + 1 for i in face.glyph.outline.contours)
        points = face.glyph.outline.points
        flags = face.glyph.outline.tags
        curveType = "curve" if any(t & 0x02 for t in flags) else "qcurve"
        fromIndex = 0
        for toIndex in contours:
            cPoints = points[fromIndex:toIndex]
            cFlags = flags[fromIndex:toIndex]
            pen.beginPath()
            for i in range(len(cPoints)):
                if not cFlags[i] & 0x01:
                    segmentType = None
                elif cFlags[i - 1] & 0x01:
                    segmentType = "line"
                else:
                    segmentType = curveType
                pen.addPoint(cPoints[i], segmentType)
            pen.endPath()
            fromIndex = toIndex

    def drawGlyphToPen(self, glyphName, pen):
        self.drawGlyphToPointPen(glyphName, PointToSegmentPen(pen))

    def getOutlinePath(self, glyphName):
        glyphID = self._ttFont.getGlyphID(glyphName)
        face = self._ftFace
        face.load_glyph(glyphID, freetype.FT_LOAD_NO_SCALE)
        return makePathFromOutline(face.glyph.outline._FT_Outline)
