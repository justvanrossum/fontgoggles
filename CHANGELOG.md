# Changelog for FontGoggles

## [1.0] - 2020-02-29

- One! Oh! Let's go!
- Sort axis sliders more logically: sort registered axes first, then
  by name.
- The Unicode Picker can now show more than 500 search results.

## [0.9.8] - 2020-02-28

- Added “Reset all axes” button to Variations panel.
- Deal better with different default axis values when multiple fonts are
  being viewed.
- Improved shift-click behavior in the font list

## [0.9.7] - 2020-02-28

- Be smarter about multi-font glyph selection if fonts behave the same and
  use the same glyph names, as is usual within a family.
- Show stylistic set names when possible. If multiple fonts are loaded and
  they don't have matching names for a stylistic set, a generic "\<multiple
  names\>" is shown.

## [0.9.6] - 2020-02-27

- Fixed issue with glyph selection/hover, when adjacent glyphs overlap
- Fixed pinch zoom issue which messed up window resize + scroll behavior
- Fixed issue with clicking in font list but beyond of items
- Made Copy menu (⌘-C) work in UnicodePicker
- Added support for vertical text layout for .designspace files

## [0.9.5] - 2020-02-25

- Added support for COLR/CPAL color fonts
- Added support for UFO color layer fonts, as experimentally supported
  by fontmake. See this [new feature](https://github.com/googlefonts/ufo2ft/pull/359)
  in ufo2ft.

## [0.9.4] - 2020-02-24

- Implement File -> Revert
- Discovered a bug in the BiDi algorithm we use, which triggered an assert.
  Disabled the assert so we can at least see the result of the bug.
  Workaround: disable BiDi processing. See [#35](https://github.com/justvanrossum/fontgoggles/issues/35).
- Hide the compile output panel by default, but show visual feedback
  in the font list when a compile warning or error was issued, and show
  the compile output pane automatically when a font item is selected
  that has a warning or error.
- Fixed issue with dragging multiple fonts: the selection was reset to
  a single item, making it impossible to drag multiple fonts.
- Fixed issue where you couldn't select glyphs by clicking outside the
  glyphs.
- Make app icon work better at small sizes.

## [0.9.3] - 2020-02-21

- Save all text settings and many UI settings to the project file.
- When performing undo/redo in the font list, also take the selection
  into account.

## [0.9.2] - 2020-02-19

- Fixed drag and drop bug on macOS 10.10

## [0.9.1] - 2020-02-19

- Reordering of fonts in the font list is now possible through drag and
  drop. One can also drag fonts to other FontGoggles windows, and to
  other applications.
- Implement copying selected data from the character list and the glyph
  list to the clipboard. Selecting a whole column is also implemented.
  The result is tab-separated text, so it can be pasted straight into a
  spreadsheet.
- Renamed “Size” slider to “Relative Size”, to make it clearer this is
  about the size relative to the font list item. Normal zooming is done
  with pinch gestures, command minus and plus, and option scroll.
- Misc copyright updates.

## [0.9.0] - 2020-02-17

First public release.
