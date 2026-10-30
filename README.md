# Krita Stroke Sampler

[![Python: 3.14](https://img.shields.io/badge/python-3.14-007ec6.svg?logo=python&logoColor=white)](https://www.python.org)
[![Krita: 6.0.1](https://img.shields.io/badge/krita-6.0.1-fe4b9c?logo=krita&logoColor=white)](https://krita.org)
[![License: GPLv3](https://img.shields.io/badge/license-GPLv3-67ac09.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub Release](https://img.shields.io/github/v/release/frammenti/krita-stroke-sampler?color=67ac09)](https://github.com/frammenti/krita-stroke-sampler/releases/latest)

A plugin for the Krita painting program that lets you sample color from any layer with every brushstroke.

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

**Size:** set the diameter of color sampling in image pixels, independent of zoom. Sizes above 1 average the colors inside a circle centered at stroke start. Fully transparent pixels are ignored and the sampled color is always opaque. Averaging uses the source color space and profile without additional linear-light conversion. Even diameters center the circle between pixels; odd diameters center it on the selected pixel.

When NumPy is available in Krita’s Python environment, circular masking and averaging use vectorized array operations. Otherwise, the plugin uses a Python fallback with the same result (but far worse performance).

Settings are independent per window and saved in `kritarc` as defaults for new windows.

## Roadmap

- [x] Sample one pixel from the source layer with every stroke
- [x] Average colors within the sampling diameter
- [ ] Option to sync sample size with brush size
- [ ] Keyboard shortcut for setting a coordinate offset for the source color, like a Clone Stamp tool
- [ ] Keyboard shortcut for color preview

## Development

Runtime files live in `plugin/`.

The plugin registers both a **docker** and an **extension**.
For each Krita window, the extension creates an **input handler** and shares with it the settings selected in the docker.
The docker forwards `canvasChanged` callbacks to keep the handler's view current.

The handler listens for left-button presses on `KisOpenGLCanvas2` and reinstalls its filter after focus changes to run before Krita's input filter.

If the Freehand Brush tool is selected and sampling is enabled, the handler maps the stroke start point into image coordinates, samples the color from the source layer's projection, and sets it as foreground color before the stroke starts.

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

Tests cover window and canvas lifecycle, settings and layer selection, input coordinate mapping, color decoding and averaging, and the NumPy/fallback circular mask.

No running Krita instance is required.
Tests use real Qt controls and Krita API doubles: rendering, ICC conversion, and native input behavior still need in-app testing.
Install NumPy to include the vectorization checks, otherwise those checks are skipped.
Qt's offscreen backend may print platform messages during tests.

## Packaging and releases

To publish a release, commit and push the changes, then create and push a
version tag:

```bash
git tag v0.1.0
git push origin --tags
```

The GitHub Actions workflow creates a release and uploads the packaged plugin as `krita-stroke-sampler.zip`.
The archive contains `stroke_sampler.desktop` and the `stroke_sampler/` folder, including a copy of the license.
For annotated tags, the tag message becomes the release body and can contain Markdown.
Tags such as `v0.1.0-beta.1` create prereleases.
Remember to keep the version in `pyproject.toml` consistent with the tag.
Re-running the workflow replaces the asset on an existing mutable release.

## License

This plugin is licensed under the GNU General Public License v3.0, see [LICENSE](LICENSE).
