# Krita Stroke Sampler

[![Python: 3.14](https://img.shields.io/badge/python-3.14-007ec6.svg?logo=python&logoColor=white)](https://www.python.org)
[![Krita: 6.0.1](https://img.shields.io/badge/krita-6.0.1-fe4b9c?logo=krita&logoColor=white)](https://krita.org)
[![License: GPLv3](https://img.shields.io/badge/license-GPLv3-67ac09.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub Release](https://img.shields.io/github/v/release/frammenti/krita-stroke-sampler?color=67ac09)](https://github.com/frammenti/krita-stroke-sampler/releases/latest)

A plugin for the Krita painting program that lets you sample color from another layer with every brushstroke.

## Installation

1. Download [`krita-stroke-sampler.zip`](https://github.com/frammenti/krita-stroke-sampler/releases/latest/download/krita-stroke-sampler.zip) from the [latest release](https://github.com/frammenti/krita-stroke-sampler/releases/latest).
2. In Krita:
   1. Choose **Tools → Scripts → Import Python Plugin from File…** and select the zip file.
   2. When prompted, accept to enable the plugin.

   _or_

   Manually:
   1. Find the `pykrita/` directory inside Krita's resources folder. You can open it in Krita through **Settings → Manage Resources → Open Resource Folder**.
   2. Copy the contents of the zip file into the directory:

   ```
   pykrita
   ├── stroke_sampler
   └── stroke_sampler.desktop
   ```

   3. Restart Krita.
   4. Enable **Stroke Sampler** in the Python Plugin Manager under **Settings → Configure Krita**.

3. Restart Krita.
4. Open **Settings → Dockers → Stroke Sampler**.

## Settings

**Enable:** toggle on/off sampling without affecting the source selection.

**Source layer:** select a layer in the current document (masks excluded) from which to sample color, ignoring visibility and opacity.
Choose **None** to clear the source and stop sampling.
The selection is synced if the layer is renamed or nested, and cleared if deleted.

> [!TIP]
> If you name the source layer the same across documents, for example, “Reference,” that layer will be selected automatically when you switch between them.

**Size:** set the diameter of color sampling in image pixels, independent of zoom, much like brush size.
If the size is greater than 1px, the resulting color will be the average of the colors of the pixels within the diameter.

Each window has its own live settings, shared by its docker and input handler.
User changes are saved to Krita's `kritarc` and loaded by new windows.

## Roadmap

The current input prototype swaps foreground and background colors on left-button canvas presses while enabled and the Freehand Brush tool is selected. Source-layer color sampling is not implemented yet.

- [ ] Sample color from the source layer with every stroke
- [ ] Option to sync sample size with brush size
- [ ] Keyboard shortcut for setting a coordinate offset for the source color, like a Clone Stamp tool
- [ ] Keyboard shortcut for color preview

## Development

Runtime files live in `plugin/`.

The plugin registers both a **docker** and an **extension**. For each Krita window, the
extension finds the docker and creates an **input handler**, sharing the settings
object owned by that docker. The docker forwards `canvasChanged` callbacks to
keep the handler's canvas and view current.

The handler finds **canvas receivers** among the window's descendant widgets by their
class name, `KisOpenGLCanvas2`, and installs an **event listener** directly on them.
It reinstalls the listener after canvas focus changes to preserve priority over
Krita's input filters. The listener forwards the receiving widget and local press
position; the handler checks whether sampling is enabled and the Freehand Brush
tool is selected before acting.

The remaining directories and scripts support development:

- `tests/`: automated checks using real Qt controls and Krita API doubles.
- `typings/`: local Krita Python API type stubs used by Pyright.
- `update_types.sh`: import type stubs into `typings/krita.pyi` from an installed Krita application.
- `package_plugin.sh`: create a local plugin `.zip` package to import into Krita.
- `install_plugin.sh`: install the plugin manually and restart Krita.

## Testing

With Python 3.14+ and PyQt6 available, run the tests from the repository root:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

Tests cover:

- plugin registration and one handler per window,
- initial canvas attachment and listener priority after refocusing,
- receiver/position delivery and brush selection tracking,
- settings parsing and persistence,
- startup signal blocking,
- layer lookup,
- document switching,
- live node updates and deletion,
- flat-list selection,
- popup list synchronization.

No running Krita instance is required.
Qt's offscreen backend may print platform capability messages during popup tests.

Krita's custom slider rendering and native window integration still require testing in the application.

## Packaging and releases

To publish a release, commit and push the changes, then create and push a
version tag:

```bash
git tag -a v0.1.0 -m "Initial release"
git push origin --tags
```

The Github actions workflow creates a release and uploads the packaged plugin as `krita-stroke-sampler.zip`.
For annotated tags, the tag message becomes the release body and can contain Markdown.
Omit `-m` to compose a longer message in your editor. Lightweight tags have no
message, so their releases use automatically generated notes instead.
The archive contains `stroke_sampler.desktop` and the `stroke_sampler/` folder, including a copy of the license.
Tags such as `v0.1.0-beta.1` create prereleases.
Remember to keep the version in `pyproject.toml` consistent with the tag.
Re-running the workflow replaces the asset on an existing mutable release.

## License

This plugin is licensed under the GNU General Public License v3.0, see [LICENSE](LICENSE).
