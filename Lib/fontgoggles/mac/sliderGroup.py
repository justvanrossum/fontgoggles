import AppKit
from vanilla import *
from fontgoggles.misc.properties import weakrefCallbackProperty


class SliderGroup(Group):

    _callback = weakrefCallbackProperty()

    def __init__(self, width, sliderInfo, continuous=True, callback=None):
        super().__init__((0, 0, width, 0))
        self._callback = callback
        self._continuous = continuous
        self.setSliderInfo(sliderInfo)

    def _breakCycles(self):
        self._callback = None
        super()._breakCycles()

    def setSliderInfo(self, sliderInfo):
        # clear all subviews
        for attr, value in list(self.__dict__.items()):
            if isinstance(value, VanillaBaseObject):
                delattr(self, attr)
        margin = 10
        y = margin
        self._tags = []
        for tag, (label, minValue, defaultValue, maxValue) in sliderInfo.items():
            self._tags.append(tag)
            attrName = f"slider_{tag}"
            slider = SliderPlus((margin, y, -margin, 40), label, minValue, defaultValue, maxValue,
                                continuous=self._continuous, callback=self._sliderChanged)
            setattr(self, attrName, slider)
            y += 50
        posSize = (0, 0, self.getPosSize()[2], y)
        self.setPosSize(posSize)

    def _sliderChanged(self, sender):
        callCallback(self._callback, self)

    def get(self):
        state = {}
        for tag in self._tags:
            attrName = f"slider_{tag}"
            slider = getattr(self, attrName)
            state[tag] = slider.get()
        return state

    def set(self, state):
        for tag in self._tags:
            attrName = f"slider_{tag}"
            slider = getattr(self, attrName)
            slider.set(state[tag])


class SliderPlus(Group):

    _callback = weakrefCallbackProperty()

    def __init__(self, posSize, label, minValue, value, maxValue, continuous=True, callback=None):
        super().__init__(posSize)
        self._callback = callback
        self.label = TextBox((0, 0, 0, 20), label)
        self.slider = Slider((0, 18, -60, 20), value=minValue, minValue=minValue, maxValue=maxValue,
                             continuous=continuous, callback=self._sliderCallback)
        self.editField = EditText((-50, 16, 0, 24), "", continuous=False, callback=self._editFieldCallback)
        self.editField._nsObject.setAlignment_(AppKit.NSRightTextAlignment)
        self._setSliderFromValue(value)
        self._setEditFieldFromValue(value)

    def _breakCycles(self):
        self._callback = None
        super()._breakCycles()

    def _sliderCallback(self, sender):
        value = sender.get()
        self._setEditFieldFromValue(value)
        callCallback(self._callback, self)

    def _editFieldCallback(self, sender):
        value = sender.get()
        if not value:
            self._setSliderFromValue(None)
            callCallback(self._callback, self)
            return
        value = value.replace(",", ".")
        try:
            f = float(value)
        except ValueError:
            pass
        else:
            self.slider.set(f)
            sliderValue = self.slider.get()
            if sliderValue != f:
                self._setEditFieldFromValue(sliderValue)
            callCallback(self._callback, self)

    def _setSliderFromValue(self, value):
        if value is None:
            minValue = self.slider._nsObject.minValue()
            maxValue = self.slider._nsObject.maxValue()
            value = (minValue + maxValue) / 2
        self.slider.set(value)

    def _setEditFieldFromValue(self, value):
        if value is None:
            s = ""
        elif int(value) == value:
            s = str(int(value))
        else:
            s = f"{value:.1f}"
        self.editField.set(s)

    def get(self):
        if not self.editField.get():
            return None
        else:
            return self.slider.get()

    def set(self, value):
        self._setSliderFromValue(value)
        self._setEditFieldFromValue(value)


def callCallback(callback, sender):
    if callback is not None:
        callback(sender)


if __name__ == "__main__":

    class SliderTest:

        def __init__(self):
            self.w = Window((300, 400), "SliderTest", autosaveName="SliderTestttt")
            # self.w.slider1 = SliderPlus((10, 10, -10, 50), "Slider 1", 0, 50, 100)
            # self.w.slider2 = SliderPlus((10, 60, -10, 50), "Slider 2", 0, 50, 100)
            info = [("abcd", "The alphabet"),
                    ("xyz ", "The alphabet part 2"),
                    ("wdth", "Width"),
                    ("wght", "Weight")]
            self.sliderInfo = {}
            for tag, label in info:
                self.sliderInfo[tag] = (label, 0, 50, 100)
            self.w.sliderGroup = SliderGroup(300, self.sliderInfo, continuous=True, callback=self.sliderGroupCallback)
            self.w.mutateButton = Button((10, -40, 80, 20), "Mutate", callback=self.mutateCallback)
            self.w.open()

        def sliderGroupCallback(self, sender):
            print(sender.get())

        def mutateCallback(self, sender):
            state = {}
            for tag, (label, minValue, defaultValue, maxValue) in self.sliderInfo.items():
                v = minValue + (maxValue - minValue) * random()
                state[tag] = v
            self.w.sliderGroup.set(state)

    t = SliderTest()
