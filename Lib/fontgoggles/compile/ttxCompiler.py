from fontTools.ttLib import TTFont


def compileTTXToPath(ttxPath, ttPath):
    font = TTFont()
    font.importXML(ttxPath)
    font.save(ttPath, reorderTables=False)
