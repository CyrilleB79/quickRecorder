# Audio recorder

* Author: Cyrille Bougot
* NVDA compatibility: 2024.1 and beyond
* Downloadable in NVDA's Add-on Store

This add-on provides.

TBD

### Features

* Display detailed information on a character, e.g. Unicode name, number, CLDR, symbol name, etc.
* This information can be displayed either at the location of the review cursor or at the location of the system cursor.
* Customize the reported information when pressing `numpad2`.
* Use the same custom information when moving the review cursor by character.

## Commands

* `Numpad2` (all keyboard layouts) or `NVDA+.` (laptop layout): when pressed 4 times, displays information about the character of the current navigator object where the review cursor is situated. This command can also be customized in the settings of the add-on.
* Unassigned: Presents a message with detailed information on the character where the review cursor is situated. If you feel uncomfortable with the four press gesture, you may use this command instead.
* Unassigned: Presents a message with detailed information on the character at the position of the caret (works only in places where there is a caret).
* Unassigned: Opens Character Information add-on settings.

The unassigned commands need first to be assigned in the Input gestures dialog to be used.

## Settings

This add-on has its own category in NVDA's settings dialog where you can configure the following options.

### Action for multiple presses of the report review character command

The three combo boxes of this group allow to customize what is reported by the report review character command (`numpad2`) when using two, three or four presses.
By default, NVDA reports the character description on second press and its numeric value, decimal and hexadecimal, on third press.
You can change what is reported on the character at the position of the review cursor upon multiple presses.
For example, you can report its CLDR English name on second press, its Unicode name on third press and display detailed information on it on fourth press.

### Remember these action during character navigation

When you have reported specific information with the report review character command (`numpad2`) called multiple times, you may want to continue reporting the same information while navigating with the review cursor (`numpad1` and `numpad3`).
Checking this option will allow you to do it, as long as you navigate with the review cursor by character just after a multiple press of `numpad2`.

## Change log

### Version 1.0

* Initial release.
