from .bidi import applyBiDi


alignments = dict(LTR="left", RTL="right", TTB="top", BBT="bottom")


class TextInfo:

    def __init__(self, text):
        self.originalText = text
        self.biDiText, self.baseDirection, self.toBiDi, self.fromBiDi = applyBiDi(self.originalText)
        self.shouldApplyBiDi = True
        self.directionOverride = None

    @property
    def text(self):
        if self.shouldApplyBiDi:
            return self.biDiText
        else:
            return self.originalText

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
            alignments = dict(LTR="left", RTL="right", TTB="top", BBT="bottom")
            return alignments[self.directionOverride]
        else:
            alignments = dict(L="left", R="right")
            return alignments[self.baseDirection]
