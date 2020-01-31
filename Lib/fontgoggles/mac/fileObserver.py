import os
from CoreFoundation import CFRunLoopGetCurrent
from Foundation import NSURL
from FSEvents import (FSEventStreamCreate, FSEventStreamInvalidate, FSEventStreamScheduleWithRunLoop,
                      FSEventStreamStart, FSEventStreamStop, FSEventStreamUnscheduleFromRunLoop,
                      kCFRunLoopDefaultMode, kFSEventStreamCreateFlagNone, kFSEventStreamEventIdSinceNow)


# Relevant documentation:
# https://developer.apple.com/library/archive/documentation/Darwin/Conceptual/FSEvents_ProgGuide/UsingtheFSEventsFramework/UsingtheFSEventsFramework.html


class FileObserver:

    def __init__(self, latency=0.25):
        self.latency = latency
        self.directories = {}
        self.observedFolders = set()
        self.eventStreamRef = None

    def addObserver(self, path, callback):
        path = os.path.normpath(path)
        assert os.path.exists(path)
        parent, name = os.path.split(path)
        directory = self._getDirectory(parent)
        directory.addChildObserver(name, callback)
        self._update()

    def removeObserver(self, path, callback):
        path = os.path.normpath(path)
        parent, name = os.path.split(path)
        directory = self._getDirectory(parent)
        directory.removeChildObserver(name, callback)
        if not directory.children:
            del self.directories[parent]
        self._update()

    def _getDirectory(self, path):
        assert os.path.isdir(path)
        dirInfo = self.directories.get(path)
        if dirInfo is None:
            dirInfo = Directory(path)
            self.directories[path] = dirInfo
        return dirInfo

    def _update(self):
        newObservedFolders = set(self.directories)
        if self.eventStreamRef is not None:
            if newObservedFolders == self.observedFolders:
                return
            FSEventStreamStop(self.eventStreamRef)
            FSEventStreamUnscheduleFromRunLoop(self.eventStreamRef,
                                               CFRunLoopGetCurrent(),
                                               kCFRunLoopDefaultMode)
            FSEventStreamInvalidate(self.eventStreamRef)

        self.observedFolders = newObservedFolders
        if not newObservedFolders:
            self.eventStreamRef = None
            return

        self.eventStreamRef = FSEventStreamCreate(None,
                                                  self._fsEventCallback,
                                                  None,
                                                  list(newObservedFolders),
                                                  kFSEventStreamEventIdSinceNow,
                                                  self.latency,
                                                  kFSEventStreamCreateFlagNone)
        FSEventStreamScheduleWithRunLoop(self.eventStreamRef,
                                         CFRunLoopGetCurrent(),
                                         kCFRunLoopDefaultMode)
        FSEventStreamStart(self.eventStreamRef)

    def _fsEventCallback(self, streamRef, clientCallBackInfo, numEvents, eventPaths, eventFlags, eventIds):
        for eventPath in eventPaths:
            eventPath = os.path.normpath(eventPath.decode("utf-8"))
            parent = eventPath
            name = None
            while parent not in self.directories and parent != "/":
                parent, name = os.path.split(parent)

            directory = self.directories.get(parent)
            if directory is None:
                # TODO: log a warning
                continue

            movedOrDeleted = directory.directoryChangedEvent(name)
            if movedOrDeleted:
                if not directory.children:
                    del self.directories[parent]
                for inode, child, newPath in movedOrDeleted:
                    newParent = os.path.dirname(newPath)
                    # TODO: check whether newParent is a Trash folder
                    directory = self._getDirectory(newParent)
                    directory.children[inode] = child
                self._update()


class DirectoryEntry:

    def __init__(self, name, modTime, bookmarkData):
        self.name = name
        self.modTime = modTime
        self.bookmarkData = bookmarkData
        self.callbacks = []

    def callCallbacks(self, oldPath, newPath, wasModified):
        for callback in self.callbacks:
            callback(oldPath, newPath, wasModified)


class Directory:

    def __init__(self, path):
        self.path = path
        self.children = {}

    def addChildObserver(self, name, callback):
        childPath = os.path.join(self.path, name)
        assert os.path.exists(childPath)
        url = NSURL.fileURLWithPath_(childPath)
        bookmarkData, error = url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
                0, None, None, None)
        assert error is None, error
        st = os.stat(childPath)
        inode = st.st_ino
        modTime = st.st_mtime
        if inode in self.children:
            assert self.children[inode].name == name
            assert self.children[inode].modTime == modTime
            self.children[inode].bookmarkData = bookmarkData
        else:
            self.children[inode] = DirectoryEntry(name, modTime, bookmarkData)
        self.children[inode].callbacks.append(callback)

    def removeChildObserver(self, name, callback):
        # TODO: keep a childrenByName dict so we won't have to loop
        for inode, child in list(self.children.items()):
            if child.name == name:
                self.children[inode].callbacks.remove(callback)
                if not self.children[inode].callbacks:
                    del self.children[inode]

    def directoryChangedEvent(self, childName):
        if childName:
            # If we're observing a folder and something changes (deep)
            # inside of it, notify.
            # TODO: keep a childrenByName dict so we won't have to loop
            for child in self.children.values():
                if child.name == childName:
                    childPath = os.path.join(self.path, child.name)
                    child.callCallbacks(childPath, childPath, True)
                    break
            return

        inodes = {}  # gather the inodes that _may_ have changed
        for name in os.listdir(self.path):
            childPath = os.path.join(self.path, name)
            st = os.stat(childPath)
            if st.st_ino in self.children:
                inodes[st.st_ino] = (name, st.st_mtime)

        # add inodes for files/folders that were no longer found
        for inode in set(self.children) - set(inodes):
            # This one moved away
            inodes[inode] = (self.children[inode].name, None)

        movedOrDeleted = []
        for inode, (name, modTime) in inodes.items():
            child = self.children[inode]
            oldPath = os.path.join(self.path, child.name)
            if modTime is None:
                # This file or folder moved somewhere else or got deleted. Let's find out
                # by resolving our bookmark data
                url, isStale, error = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(
                        child.bookmarkData, 0, None, None, None)
                if url is None:
                    # file was deleted
                    newPath = None
                    child.name = None
                    wasModified = False
                else:
                    # TODO: Check whether it was moved to the trash, and treat special
                    # os.listdir() will fail on a Trash folder
                    newPath = url.path()
                    child.name = os.path.basename(newPath)  # update name
                    bookmarkData, error = url.bookmarkDataWithOptions_includingResourceValuesForKeys_relativeToURL_error_(
                            0, None, None, None)
                    assert error is None, error
                    child.bookmarkData = bookmarkData
                    wasModified = child.modTime != os.stat(newPath).st_mtime
                wasRenamed = True
                movedOrDeleted.append((inode, child, newPath))
            else:
                wasModified = child.modTime != modTime
                if wasModified:
                    child.modTime = modTime
                wasRenamed = child.name != name
                if wasRenamed:
                    child.name = name
                    newPath = os.path.join(self.path, name)
                else:
                    newPath = oldPath
            if wasRenamed or wasModified:
                child.callCallbacks(oldPath, newPath, wasModified)
        for inode, child, newPath in movedOrDeleted:
            del self.children[inode]
        return movedOrDeleted


_fileObserver = None


def getFileObserver():
    global _fileObserver
    if _fileObserver is None:
        _fileObserver = FileObserver()
    return _fileObserver
