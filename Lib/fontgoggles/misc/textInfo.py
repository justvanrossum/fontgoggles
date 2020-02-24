from .bidi import applyBiDi


alignments = dict(LTR="left", RTL="right", TTB="top", BTT="bottom")


class TextInfo:

    def __init__(self, text):
        self.text = text
        self.shouldApplyBiDi = True
        self.directionOverride = None
        self.scriptOverride = None
        self.languageOverride = None

    @property
    def text(self):
        if self.shouldApplyBiDi:
            return self.biDiText
        else:
            return self.originalText

    @text.setter
    def text(self, text):
        self.originalText = text
        self.biDiText, self._runLengths, self.baseDirection, self.toBiDi, self.fromBiDi = applyBiDi(self.originalText)
        # assert len(self.biDiText) == len(self.originalText), (len(self.biDiText), len(self.originalText))

    def mapToBiDi(self, charIndices):
        toBiDi = self.toBiDi
        return [toBiDi[charIndex] for charIndex in charIndices]

    def mapFromBiDi(self, charIndices):
        fromBiDi = self.fromBiDi
        return [fromBiDi[charIndex] for charIndex in charIndices]

    @property
    def runLengths(self):
        # TODO XXX: for now, disable segmenting, because I don't really know what I'm doing.
        # Segmenting (as I implemented it) pro: Latin embedded in Arabic shows latin features.
        # Segmenting con: numbers embedded in Arabic do _not_ get localized number variants.
        # I may be doing segmenting wrong, but right now it's better to not do any segmenting
        # at all than to possibly do it embarrasingly wrong.
        if self.shouldApplyBiDi and False:
            return self._runLengths
        else:
            return [len(self.originalText)]

    @property
    def directionForShaper(self):
        if self.directionOverride is not None:
            return self.directionOverride
        elif self.shouldApplyBiDi:
            return "LTR"
        else:
            return None  # let the shaper figure it out

    @property
    def suggestedAlignment(self):
        if self.directionOverride is not None:
            alignments = dict(LTR="left", RTL="right", TTB="top", BTT="bottom")
            return alignments[self.directionOverride]
        else:
            alignments = dict(L="left", R="right")
            return alignments[self.baseDirection]
