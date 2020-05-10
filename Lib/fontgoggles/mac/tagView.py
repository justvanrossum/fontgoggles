import AppKit
from vanilla import EditText, Group, Popover, TextBox
from fontgoggles.misc.properties import delegateProperty, hookedProperty, weakrefCallbackProperty
from fontgoggles.mac.drawing import drawText


class FGTagView(AppKit.NSView):

    def _scheduleRedraw(self):
        self.setNeedsDisplay_(True)

    tag = hookedProperty(_scheduleRedraw)
    tracked = hookedProperty(_scheduleRedraw, default=False)
    allowsAlternateSelection = False

    @hookedProperty
    def state(self):
        if self.state and self.state > 1:
            tooltip = f"Selected alternate: {int(self.state)}"
        else:
            tooltip = ""
        self.setToolTip_(tooltip)
        self.setNeedsDisplay_(True)

    def menuForEvent_(self, event):
        if not self.allowsAlternateSelection:
            return None
        menu = AppKit.NSMenu.alloc().initWithTitle_("Contextual Menu")
        baseItems = [
            ("Off", False),
            ("Default", None),
            ("On (Alternate 1)", True),
        ]
        altItems = [(f"Alternate {i}", i) for i in range(2, 11)]
        items = baseItems + altItems
        for index, (item, itemState) in enumerate(items):
            menuItem = menu.insertItemWithTitle_action_keyEquivalent_atIndex_(
                    item, "contextualAction:", "", index)
            menuItem.setRepresentedObject_(itemState)
            if self.state == itemState:
                menuItem.setState_(AppKit.NSControlStateValueOn)
        if self.state and self.state > 10:
            msg = f"Alternate {self.state}, Edit..."
        else:
            msg = "Enter alternate number..."
        menuItem = menu.insertItemWithTitle_action_keyEquivalent_atIndex_(
                msg, "enterAlternateNumber:", "", len(items))
        return menu

    def mouseDown_(self, event):
        if self.allowsAlternateSelection and event.modifierFlags() & AppKit.NSEventModifierFlagControl:
            menu = self.menuForEvent_(event)
            AppKit.NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self)
        else:
            self.tracked = True

    def contextualAction_(self, sender):
        self.state = sender.representedObject()
        self.vanillaWrapper()._callCallback()

    def enterAlternateNumber_(self, sender):
        self.popover = Popover((140, 80))
        self.popover.open(parentView=self, preferredEdge='right')
        self.popover.label = TextBox((20, 10, -20, 20), "Enter an Alt nr.:")
        if self.state:
            value = str(int(self.state))
        else:
            value = ""
        self.popover.altNumber = EditText((20, 35, -20, 25), value, continuous=False,
                                          callback=self.textEnteredCallback_)
        self.window().makeFirstResponder_(self.popover.altNumber._nsObject)

    def textEnteredCallback_(self, sender):
        try:
            altNumber = int(sender.get())
        except ValueError:
            pass
        else:
            self.state = altNumber
            self.vanillaWrapper()._callCallback()
        self.popover.close()

    def mouseDragged_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.tracked = AppKit.NSPointInRect(point, self.bounds())

    def mouseUp_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.tracked = False
        if AppKit.NSPointInRect(point, self.bounds()):
            self.toggleState_(event.modifierFlags() & AppKit.NSEventModifierFlagOption)
            self.vanillaWrapper()._callCallback()

    def toggleState_(self, optionKey):
        optionKey = bool(optionKey)
        table = {
            # (oldState, optionKey): newState
            (None, False): True,
            (None, True): False,
            (True, False): False,
            (True, True): None,
            (False, False): None,
            (False, True): True,
        }
        self.state = table[self.state, optionKey]

    def drawRect_(self, rect):
        (x, y), (w, h) = self.bounds()
        if self.state is None:
            mainColor = AppKit.NSColor.systemGrayColor()
        elif self.state:
            mainColor = AppKit.NSColor.systemGreenColor()
            mainColor = mainColor.blendedColorWithFraction_ofColor_(0.25, AppKit.NSColor.systemGrayColor())
        else:
            mainColor = AppKit.NSColor.systemRedColor()

        if self.tracked:
            mainColor = mainColor.blendedColorWithFraction_ofColor_(0.5, AppKit.NSColor.textColor())

        mainColor.set()
        radius = min(h / 2.75, 10)
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), radius, radius)
        path.fill()

        textColor = AppKit.NSColor.textBackgroundColor()
        if self.state and self.state != 1:
            offset = 9
            text = self.tag + "*"
        else:
            offset = 12
            text = self.tag
        drawText(text, (x + offset, y + 1), textColor, AppKit.NSFont.userFixedPitchFontOfSize_(14))


class TagView(Group):

    nsViewClass = FGTagView
    tag = delegateProperty("_nsObject")
    state = delegateProperty("_nsObject")
    allowsAlternateSelection = delegateProperty("_nsObject")
    _callback = weakrefCallbackProperty()

    def __init__(self, posSize, tag, state, callback=None, allowsAlternateSelection=False):
        super().__init__(posSize)
        self.tag = tag
        self.state = state
        self.allowsAlternateSelection = allowsAlternateSelection
        self._callback = callback

    def _callCallback(self):
        callback = self._callback
        if callback is not None:
            callback(self)


if __name__ == "__main__":
    from vanilla import Window

    class Test:

        def __init__(self):
            self.w = Window((300, 500), minSize=(200, 100))
            y = 10
            self.w.g = Group((0, 0, 0, 0))
            for i, tag in enumerate(["liga", "calt", "dlig", "smcp", "kern", "locl"]):
                setattr(self.w.g, f"tag{i}", TagView((10, y, 60, 20), tag, None, self.callback))
                y += 26
            self.w.open()

        def callback(self, sender):
            print("---", sender.tag, sender.state)

    t = Test()
