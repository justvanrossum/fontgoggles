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

- Direction/orientation
- Visual alignment
- Script
- Language

## Formatting settings

- Features panel
- Variation panel
- Options panel

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

Once loaded, you can navigate through the lines of the text file with
the “stepper” control next to the text field. The “View” menu has shortcuts
for this: ⌘-arrow-key-up and ⌘-arrow-key-down to go to the previous or next
line respectively.

You can keep editing the text file in a text editor while it is loaded in
FontGoggles: it will reload the text file and show the changes.

## Save a project file

You can save a window as a `.gggls` project file. It will store all text,
formatting and window settings.

_Note: The file stores relative paths to the font files, so its location
is related on the location of the font files. They can move together,
but if sources move or the project file moves, the source references in
the project file become invalid._

## Edit font with another application

If a font gets changed on-disk by another application, FontGoggles will
reload it and show the updated version. For example, this happens, when
you:

- Re-generate a .ttf or .otf from a font editor.
- Edit a .ufo with a font editor
- Edit a .ufo with a text editor
- Edit a .designspace file
- Edit a .fea file associated with a .ufo or .designspace file
- Edit a .ttx file

_Note: FontGoggles does its very best to reload as quickly as possible,
but for .ufo and .designspace it may have to re-compile OpenType
features, and the time needed depends on the complexity of the font._

## Compile warnings and errors

If, during the (re)loading of a font, a warning is issued or an error occurs,
(... visual feedback todo ...), click on the font and have a look at the
output panel below the font list. (todo: screenshot)

## Found a bug or have a question?

Please open an issue on [the FontGoggles repository](https://github.com/justvanrossum/fontgoggles/issues).

-------------------

*FontGoggles was written by [Just van Rossum](mailto:justvanrossum@gmail.com)
and funded by [GoogleFonts](https://fonts.google.com/).*
