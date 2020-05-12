from collections import defaultdict
import AppKit
from vanilla import Button, Group, TextBox, VanillaBaseObject, Window
from fontgoggles.mac.tagView import TagView
from fontgoggles.misc.opentypeTags import features
from fontgoggles.misc.properties import weakrefCallbackProperty


class FeatureTagGroup(Group):

    _callback = weakrefCallbackProperty()

    def __init__(self, width, tagGroups, callback=None):
        posSize = (0, 0, width, 50)  # dummy height
        super().__init__(posSize)
        self._callback = callback
        self._state = {}
        self.setTags(tagGroups, {})

    def _breakCycles(self):
        del self._callback
        super()._breakCycles()

    def setTags(self, tagGroups, stylisticSetNames):
        # clear all subviews
        for attr, value in list(self.__dict__.items()):
            if isinstance(value, VanillaBaseObject):
                delattr(self, attr)
        self._titles = list(tagGroups)
        self._tagIdentifiers = defaultdict(list)
        margin = 10
        tagWidth = 60
        y = margin
        tagCounter = 0
        for title, tags in tagGroups.items():
            titleLabel = TextBox((margin, y, -margin, 20), title)
            setattr(self, f"label_{title}", titleLabel)
            y += 24
            for tag in sorted(tags):
                tagView = TagView((margin, y, tagWidth, 20), tag, None,
                                  callback=self._tagStateChanged,
                                  allowsAlternateSelection=(title == "GSUB"))
                names = stylisticSetNames.get(tag)
                if names:
                    if len(names) == 1:
                        description = next(iter(names))
                    else:
                        description = "<multiple names>"
                else:
                    description = features.get(tag, ["<unknown>"])[0]
                friendlyName = TextBox((margin + tagWidth + 6, y + 1, -margin, 20), description)
                friendlyName._nsObject.cell().setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
                friendlyName._nsObject.setAllowsExpansionToolTips_(True)
                tagIdentifier = f"tag_{title}_{tag}"
                self._tagIdentifiers[tag].append(tagIdentifier)
                setattr(self, tagIdentifier, tagView)
                setattr(self, f"friendlyName_{title}_{tag}", friendlyName)
                tagCounter += 1
                y += 26
            y += 6
        posSize = (0, 0, self.getPosSize()[2], y)
        self.setPosSize(posSize)
        self._updateState()

    def _tagStateChanged(self, tagView):
        tag = tagView.tag
        state = tagView.state
        # if a tag occurs in more than one group, reflect the new state
        for tagIdentifier in self._tagIdentifiers[tag]:
            otherTagView = getattr(self, tagIdentifier)
            if otherTagView is not tagView:
                otherTagView.state = state
        if state is None:
            self._state.pop(tag, None)
        else:
            self._state[tag] = state
        callback = self._callback
        if callback is not None:
            callback(self)

    def get(self):
        return dict(self._state)

    def _updateState(self):
        for tag, value in self._state.items():
            for tagIdentifier in self._tagIdentifiers.get(tag, ()):
                tagView = getattr(self, tagIdentifier)
                tagView.state = value

    def set(self, state):
        for tag, tagIdentifiers in self._tagIdentifiers.items():
            for tagIdentifier in tagIdentifiers:
                tagView = getattr(self, tagIdentifier)
                tagView.state = state.get(tag)
        self._state = dict(state)


if __name__ == "__main__":
    from fontgoggles.mac.aligningScrollView import AligningScrollView

    class Test:

        def __init__(self):
            tagGroups = {"GSUB": {"aalt", "salt", "ss02", "ccmb", "ccmp", "liga", "dlig", "rvrn", "cpsp"},
                         "GPOS": {"kern", "mark", "mkmk", "cpsp", "ZZZZ"}}
            self.w = Window((300, 500), "TagTest", minSize=(200, 200), autosaveName="TempTagTesttt")
            self.tags = FeatureTagGroup(300, tagGroups, callback=self.tagsChanged)

            self.w.tagsScrollView = AligningScrollView((0, 0, 0, -50), self.tags, drawBackground=False,
                                                       borderType=AppKit.NSNoBorder)
            self.w.mutateButton = Button((10, -30, 100, 20), "Mutate", callback=self.mutate)
            self.w.repopulateButton = Button((120, -30, 100, 20), "Repopulate", callback=self.repopulate)
            self.w.open()

        def tagsChanged(self, sender):
            print(sender.get())

        def mutate(self, sender):
            state = self.tags.get()
            import random
            for i in range(3):
                k = random.choice(list(state))
                state[k] = random.choice([None, None, None, False, True])
            self.tags.set(state)

        def repopulate(self, sender):
            tagGroups = {"GSUB": {"salt", "ss02", "ccmb", "ccmp", "liga", "cpsp"},
                         "GPOS": {"kern", "mkmk", "cpsp"}}
            self.tags.setTags(tagGroups)

    t = Test()
