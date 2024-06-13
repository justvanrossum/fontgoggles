import AppKit
from vanilla import Button, EditText, Group, Slider, TextBox, VanillaBaseObject
from fontgoggles.misc.properties import weakrefCallbackProperty


showHiddenAxesButtonLabels = ["Show hidden axes", "Hide hidden axes"]


class SliderGroup(Group):

    _callback = weakrefCallbackProperty()

    def __init__(self, width, sliderInfo, continuous=True, callback=None, showHiddenAxes=True):
        super().__init__((0, 0, width, 0))
        self._callback = callback
        self._continuous = continuous
        self._tags = []
        self.showHiddenAxes = showHiddenAxes
        self.setSliderInfo(sliderInfo)

    def _breakCycles(self):
        self._callback = None
        super()._breakCycles()

    def setSliderInfo(self, sliderInfo):
        self._savedSliderInfo = sliderInfo
        savedState = self.get()
        # clear all subviews
        for attr, value in list(self.__dict__.items()):
            if isinstance(value, VanillaBaseObject):
                delattr(self, attr)
        margin = 10
        y = margin
        self._tags = []
        self._defaultValues = {}
        haveHiddenAxes = False
        for tag, axisSliderInfo in sliderInfo.items():
            if axisSliderInfo.hidden:
                haveHiddenAxes = True
                if not self.showHiddenAxes:
                    continue
            self._tags.append(tag)
            self._defaultValues[tag] = axisSliderInfo.defaultValue
            attrName = f"slider_{tag}"
            slider = SliderPlus(
                (margin, y, -margin, 40),
                axisSliderInfo.label,
                axisSliderInfo.minValue,
                axisSliderInfo.defaultValue,
                axisSliderInfo.maxValue,
                continuous=self._continuous,
                callback=self._sliderChanged,
            )
            setattr(self, attrName, slider)
            y += 50

        self.resetAllButton = Button((10, y, 120, 25), "Reset all axes", self._resetAllButtonCallback)
        self.resetAllButton.enable(False)
        if haveHiddenAxes:
            self.showHiddenAxesButton = Button(
                (140, y, 140, 25),
                showHiddenAxesButtonLabels[self.showHiddenAxes],
                self._showHiddenAxesButtonCallback,
            )
        y += 35

        posSize = (0, 0, self.getPosSize()[2], y)
        self.setPosSize(posSize)
        self._updateState(savedState)

    def _sliderChanged(self, sender):
        self.resetAllButton.enable(True)
        callCallback(self._callback, self)

    def _resetAllButtonCallback(self, sender):
        self.resetAllButton.enable(False)
        for tag in self._tags:
            attrName = f"slider_{tag}"
            slider = getattr(self, attrName)
            slider.set(self._defaultValues[tag])
        callCallback(self._callback, self)

    def _showHiddenAxesButtonCallback(self, sender):
        self.showHiddenAxes = not self.showHiddenAxes
        sender.setTitle(showHiddenAxesButtonLabels[self.showHiddenAxes])
        self.setSliderInfo(self._savedSliderInfo)
        callCallback(self._callback, self)

    def get(self):
        state = {}
        for tag in self._tags:
            attrName = f"slider_{tag}"
            slider = getattr(self, attrName)
            value = slider.get()
            if value is not None:
                state[tag] = value
        return state

    def _updateState(self, state):
        for tag, value in state.items():
            attrName = f"slider_{tag}"
            slider = getattr(self, attrName, None)
            if slider is not None:
                slider.set(value)

    def set(self, state):
        if state:
            self.resetAllButton.enable(True)
        for tag in self._tags:
            attrName = f"slider_{tag}"
            slider = getattr(self, attrName)
            value = state.get(tag)
            if value is None:
                value = self._defaultValues[tag]
            slider.set(value)


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
            # self._setSliderFromValue(None)
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
        if isinstance(value, set):
            value = sum(value) / len(value)
        elif value is None:
            minValue = self.slider._nsObject.minValue()
            maxValue = self.slider._nsObject.maxValue()
            value = (minValue + maxValue) / 2
        self.slider.set(value)

    def _setEditFieldFromValue(self, value):
        if isinstance(value, set):
            if len(value) == 1:
                value = next(iter(value))
            else:
                value = None
        if value is None:
            s = ""
        else:
            if int(value) == value:
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
    from random import random
    from vanilla import Window

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
