from .bidi import textSegments


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
        return self._text

    @text.setter
    def text(self, text):
        self._text = text
        self._segments, self.baseLevel = textSegments(text)

    @property
    def segments(self):
        if self.shouldApplyBiDi:
            return self._segments
        else:
            return [(self._text, None, None, 0)]

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
