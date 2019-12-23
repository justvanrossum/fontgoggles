import AppKit
from vanilla import *
from fontgoggles.mac.tagView import TagView
from fontgoggles.misc.opentypeTags import features
from fontgoggles.misc.decorators import weakrefCallbackProperty


class FeatureTagGroup(Group):

    _callback = weakrefCallbackProperty()

    def __init__(self, width, tagGroups, callback=None):
        posSize = (0, 0, width, 50)  # dummy height
        super().__init__(posSize)
        self._callback = callback
        self._titles = []
        self.setTags(tagGroups)

    def setTags(self, tagGroups):
        # clear all subviews
        for attr, value in list(self.__dict__.items()):
            if isinstance(value, VanillaBaseObject):
                delattr(self, attr)
        margin = 10
        tagWidth = 60
        y = margin
        tagCounter = 0
        self._titles = list(tagGroups)
        for title, tags in tagGroups.items():
            titleLabel = TextBox((margin, y, -margin, 20), title)
            setattr(self, f"label_{title}", titleLabel)
            y += 24
            for tag in sorted(tags):
                tagView = TagView((margin, y, tagWidth, 20), tag, None, callback=self._tagStateChanged)
                friendlyName = TextBox((margin + tagWidth + 6, y + 1, -margin, 20), features.get(tag, ["<unknown>"])[0])
                friendlyName._nsObject.cell().setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
                setattr(self, f"tag_{title}_{tag}", tagView)
                setattr(self, f"friendlyName_{title}_{tag}", friendlyName)
                tagCounter += 1
                y += 26
            y += 6
        posSize = (0, 0, self.getPosSize()[2], y)
        self.setPosSize(posSize)

    def _tagStateChanged(self, tagView):
        tag = tagView.tag
        state = tagView.state
        # if a tag occurs in more than one group, refelct the new state
        for title in self._titles:
            otherTagView = getattr(self, f"tag_{title}_{tag}", None)
            if otherTagView is not None and otherTagView is not tagView:
                otherTagView.state = state
        callback = self._callback
        if callback is not None:
            callback(self)

    def get(self):
        state = {}
        for subview in self._nsObject.subviews():
            if hasattr(subview, "state"):
                state[subview.tag] = subview.state
        return state

    def set(self, state):
        for subview in self._nsObject.subviews():
            if hasattr(subview, "state") and subview.tag in state:
                subview.state = state[subview.tag]
        return state


if __name__ == "__main__":
    from fontgoggles.mac.aligningScrollView import AligningScrollView

    class Test:

        def __init__(self):
            tagGroups = {"GSUB": {"aalt", "salt", "ss02", "ccmb", "ccmp", "liga", "dlig", "rvrn", "cpsp"},
                         "GPOS": {"kern", "mark", "mkmk", "cpsp", "ZZZZ"}}
            self.w = Window((300, 500), "TagTest", minSize=(200, 200), autosaveName="TempTagTesttt")
            self.tags = FeatureTagGroup(300, tagGroups, callback=self.tagsChanged)

            self.w.tagsScrollView = AligningScrollView((0, 0, 0, -50), self.tags, drawBackground=False, borderType=AppKit.NSNoBorder)
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
