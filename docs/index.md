![FontGoggles icon](images/icon.png)

# FontGoggles

_Rich Font Previewing and Comparing_

## Overview

FontGoggles is a font viewer for various font formats. It is a desktop
application for macOS. It is free and open [source](https://github.com/justvanrossum/fontgoggles).

You can download [the latest release here](https://github.com/justvanrossum/fontgoggles/releases/latest).

Supported formats:

- .ttf/.otf (including variable fonts)
- .ttc/.otc
- .woff/.woff2
- .ufo/.ufoz
- .designspace
- .ttx

Core features:

- View multiple fonts simultaneously
- Supports complex scripts: it does proper text shaping with HarfBuzz
- Enable/disable OpenType features
- Explore design spaces
- Preview .ufo and .designspace files _as if_ they are compiled fonts
- Automatically reload fonts if they are changed on disk
- Supports vertical text layout

![FontGoggles screenshot](images/screenshot_1.png)

## How to use

Drop some fonts (or folders with fonts) onto the application, or launch the application, and drop some fonts onto the window.

An empty window looks like this:
![FontGoggles screenshot](images/screenshot_2.png)
After opening some fonts it will look like this:
![FontGoggles screenshot](images/screenshot_3.png)

- Zoom in/out by using pinch gestures on your trackpad, or use ⌘-plus and ⌘-minus, or option-scroll.
- Type text in the text field to change the displayed text
- Drag and drop can be used to rearrange the fonts
- Click on a font to see the glyph positioning information
- Select glyphs by clicking on them, highlighting glyph positioning info and character info

![FontGoggles screenshot](images/screenshot_4.png)

## Text settings

## Formatting settings

## Customize the window

Most panels in the window are resizable, and some are collapsable.
There are also “View” menu items to show and hide a few panels:

- Show/hide Character list — ⌘-1
- Show/hide Glyph list — ⌘-2
- Show/hide Compile output — ⌘-3
- Show/hide Formatting options — ⌘-4

## Load and navigate a text file

Instead of typing the text into the text field, you may load an external
text file, using the “Load Text File...” menu under “View”, or with the
“gear” popup menu next to the text field.

## Save a project file

You can save a window as a `.gggls` project file. It will store all text,
formatting and window settings.

_Note: The file stores relative paths to the font files, so its location
is related on the location of the font files. They can move together,
but if sources move or the project file moves, the source references in
the project file become invalid._

## Edit font with another application

- Edit .ufo with RoboFont
- Edit .ttx with text editor

## Compile warnings and errors

## Found a bug or have a question?

Please open an issue on [the FontGoggles repository](https://github.com/justvanrossum/fontgoggles/issues).

-------------------

*FontGoggles was written by [Just van Rossum](mailto:justvanrossum@gmail.com)
and funded by [GoogleFonts](https://fonts.google.com/).*
