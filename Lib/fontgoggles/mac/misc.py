import AppKit
import objc


textAlignments = dict(
    left=AppKit.NSTextAlignmentLeft,
    center=AppKit.NSTextAlignmentCenter,
    right=AppKit.NSTextAlignmentRight,
)


textLineBreakModes = dict(
    wordwrap=AppKit.NSLineBreakByWordWrapping,
    charwrap=AppKit.NSLineBreakByCharWrapping,
    clipping=AppKit.NSLineBreakByClipping,
    trunchead=AppKit.NSLineBreakByTruncatingHead,
    trunctail=AppKit.NSLineBreakByTruncatingTail,
    truncmiddle=AppKit.NSLineBreakByTruncatingMiddle,
)


def makeTextCell(align="left", lineBreakMode="wordwrap", font=None):
    cell = AppKit.NSTextFieldCell.alloc().init()
    cell.setAlignment_(textAlignments[align])
    cell.setLineBreakMode_(textLineBreakModes[lineBreakMode])
    if font is not None:
        cell.setFont_(font)
    return cell


def ClassNameIncrementer(clsName, bases, dct):
    orgName = clsName
    counter = 0
    while True:
        try:
            objc.lookUpClass(clsName)
        except objc.nosuchclass_error:
            break
        counter += 1
        clsName = orgName + str(counter)
    return type(clsName, bases, dct)
