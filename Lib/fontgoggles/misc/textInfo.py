from .segmenting import textSegments


alignments = dict(LTR="left", RTL="right", TTB="top", BTT="bottom")


class TextInfo:

    def __init__(self, text):
        self.text = text
        self.shouldApplyBiDi = True  # More like .shouldApplyBiDiAndSegmentation but that's looong
        self.directionOverride = None
        self.scriptOverride = None
        self.languageOverride = None

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text):
        self._text = text
        self._segments, self.baseLevel = textSegments(text)

        indexedSegments = []
        for segmentText, segmentScript, segmentBiDiLevel, firstCluster in self._segments:
            charIndices = []
            for index in range(firstCluster, firstCluster + len(segmentText)):
                charIndices.append(index)
            indexedSegments.append((charIndices, segmentBiDiLevel))

        if text:
            assert indexedSegments[-1][0][-1] == len(text) - 1

        toBiDi = {}
        fromBiDi = {}
        if self.baseLevel % 2:
            indexedSegments = reversed(indexedSegments)
        afterIndex = 0
        for charIndices, segmentBiDiLevel in indexedSegments:
            if segmentBiDiLevel % 2:
                charIndices = reversed(charIndices)
            for beforeIndex in charIndices:
                toBiDi[beforeIndex] = afterIndex
                fromBiDi[afterIndex] = beforeIndex
                afterIndex += 1
        assert len(toBiDi) == len(text)
        assert len(fromBiDi) == len(text)
        self._toBiDi = toBiDi
        self._fromBiDi = fromBiDi

    @property
    def segments(self):
        if self.shouldApplyBiDi:
            return self._segments
        else:
            return [(self._text, None, None, 0)]

    def mapToBiDi(self, charIndices):
        toBiDi = self._toBiDi
        return [toBiDi[charIndex] for charIndex in charIndices]

    def mapFromBiDi(self, charIndices):
        fromBiDi = self._fromBiDi
        return [fromBiDi[charIndex] for charIndex in charIndices]

    @property
    def baseDirection(self):
        return ("L", "R")[self.baseLevel % 2]

    @property
    def direction(self):
        if self.directionOverride is not None:
            return self.directionOverride
        else:
            return ("LTR", "RTL")[self.baseLevel % 2]

    @property
    def suggestedAlignment(self):
        alignments = dict(LTR="left", RTL="right", TTB="top", BTT="bottom")
        return alignments[self.direction]
