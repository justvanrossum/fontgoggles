# Changelog for FontGoggles

## [1.2.0] - 2021-05-27

- Added support for [COLRv1 fonts](https://github.com/googlefonts/colr-gradients-spec/) ([Issue 162](https://github.com/justvanrossum/fontgoggles/issues/162), [PR 171](https://github.com/justvanrossum/fontgoggles/pull/171))

## [1.1.21] - 2021-05-23

- Fixed UFOZ support ([Issue 147](https://github.com/justvanrossum/fontgoggles/issues/147),
  [PR 167](https://github.com/justvanrossum/fontgoggles/pull/167),
  [PR 168](https://github.com/justvanrossum/fontgoggles/pull/168))
- Fixed small bug with error handling when building outlines from .designspace files

## [1.1.20] - 2021-05-15

- Fixed non-crashing crash on TTF with single off-curve point
  ([Issue 156](https://github.com/justvanrossum/fontgoggles/issues/156),
  [PR 166](https://github.com/justvanrossum/fontgoggles/pull/166))
- Fixed too-narrow Unicode column in character pane and Unicode Picker
  ([Issue 165](https://github.com/justvanrossum/fontgoggles/issues/165))

## [1.1.18] - 2021-05-15

- Fixed an AttributeError during mark feature compilation
  ([PR 164](https://github.com/justvanrossum/fontgoggles/pull/164))
- Updated HarfBuzz to 2.8.1
- Updated internal dependencies

## [1.1.17] - 2020-09-07

- Updated HarfBuzz to 2.7.2
- Updated internal dependencies

## [1.1.16] - 2020-06-23

- Show tooltip when feature description gets truncated.
  ([Issue 94](https://github.com/justvanrossum/fontgoggles/issues/94))
- Use HarfBuzz cluster level 1 (MONOTONE_CHARACTERS) to get a better
  mapping between glyphs and characters. Thanks Khaled Hosny!
  ([PR 91](https://github.com/justvanrossum/fontgoggles/pull/91))
- Some small layout improvements. Thanks Georg Seifert!
  ([PR 101](https://github.com/justvanrossum/fontgoggles/pull/101))

## [1.1.15] - 2020-05-10

- Feature tag UI: option-click reverses the cycle direction, making it
  possible to enable/disable features with one click.
- Use setuptools_scm for version numbers.
- Updated internal packages

## [1.1.14] - 2020-04-30

- Updated uharfbuzz to 0.10.0, which updates HarfBuzz to 2.6.5
- Fixed contextual menu for feature tags to also respond to right-click.

## [1.1.13] - 2020-04-06

- Fixed contextual menu to also respond to right-click.
- Fixed feature tag list: not all available features were always shown.
  ([Issue 85](https://github.com/justvanrossum/fontgoggles/issues/85),
  [PR 86](https://github.com/justvanrossum/fontgoggles/issues/86))

## [1.1.12] - 2020-04-03

- Fixed app version info.

## [1.1.11] - 2020-04-02

- Fixed UFO reload issue: if kerning _and_ glyphs changed, only the glyph changes
  would show.

## [1.1.10] - 2020-03-22

- Fixed language override: for some languages the language popup menu did not
  work. ([Issue 68](https://github.com/justvanrossum/fontgoggles/issues/68),
  [PR 69](https://github.com/justvanrossum/fontgoggles/issues/69))

## [1.1.9] - 2020-03-20

- Updated fonttools to 4.5.0, which was updated to Unicode 13.0.0.

## [1.1.8] - 2020-03-20

- Updated to Unicode 13.0.0 (both the internal database and the Unicode Picker).

## [1.1.7] - 2020-03-17

- Fixed an update glitch where the language would not be properly reset after the
  user changed the script.

## [1.1.6] - 2020-03-16

- Updated uharfbuzz to latest version, which fixes a bug retrieving feature tags.
  [Issue 63](https://github.com/justvanrossum/fontgoggles/issues/63)

## [1.1.5] - 2020-03-15

- Rewrote Bi-directional text support ([issue 35](https://github.com/justvanrossum/fontgoggles/issues/35), [PR 60](https://github.com/justvanrossum/fontgoggles/issues/60)). This also implements script segmentation.
- As an indirect consequence of the previous item, the "BiDi" checkbox above
  the character list has been removed.
- Fixed regression: dragging fonts between FontGoggles windows works again.

## [1.1.4] - 2020-03-07

- Added "Reload font" and "Clear error" contextual menus to font item.
- If an error occurs while preparing a VF from a .designspace file, check
  whether it was caused within GSUB or GPOS, and try again without that table.
  This allows us to at least see a partially working font.

## [1.1.3] - 2020-03-06

- [designspace] fixed layer composite regression introduced in 1.1.2 with the
  fix for [issue 53](https://github.com/justvanrossum/fontgoggles/issues/53).
- Fixed automatic reloading snag. [Issue 48](https://github.com/justvanrossum/fontgoggles/issues/48)

## [1.1.2] - 2020-03-05

- [designspace] Fixed issue with composite glyphs not rendering correctly if a
  base glyph uses a support layer. [Issue 53](https://github.com/justvanrossum/fontgoggles/issues/53)

## [1.1.1] - 2020-03-03

- Fixed minor UI glitch: update available language tags after reload.
- Update the used Unicode database to 12.1.0
- Work around related Unicode bidi problem. [Issue #49](https://github.com/justvanrossum/fontgoggles/issues/49)

## [1.1] - 2020-03-02

- Added View -> Show/hide Font File name menu. [Issue #39](https://github.com/justvanrossum/fontgoggles/issues/39)
- Sort fonts that are dropped onto a window the same way as when they are dropped
  onto the application. [Issue #46](https://github.com/justvanrossum/fontgoggles/issues/46)
- Small layout improvements. [PR #45](https://github.com/justvanrossum/fontgoggles/pull/45)
- GSUB feature tags now have a contextual menu (control-click or right-click)
  that allows the "alternate number" to be specified. This is useful for features
  that expose multiple alternates. [Issue #42](https://github.com/justvanrossum/fontgoggles/issues/42)
- Fixed Script override for script codes that are different between OpenType and
  ISO-15924. For example, when a font has `mym2` as a Script, it would render
  incorrectly if the user actually selected `mym2` as a Script override. Thanks
  to Ben Mitchell for reporting this.

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
