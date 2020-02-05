from fontTools.ttLib import TTFont


def compileFontToPath(ttxPath, ttPath):
    font = TTFont()
    font.importXML(ttxPath)
    font.save(ttPath, reorderTables=False)
