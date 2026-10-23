# Krita Stroke Sampler Plugin

Sample color from a source layer at each stroke

Enable the plugin in Krita's Python Plugin Manager, restart Krita, then open
**Settings → Dockers → Stroke Sampler**.

The docker provides an enable checkbox, a source-layer selector (including
layers inside groups), and a sampling radius, defaulting to **1 px**.
Disabling sampling retains the selected source. Radius is measured in image
pixels, independent of zoom; Krita's brush size uses pixels for its diameter.
The radius can be set from 0.01 to 10,000 px.

Settings apply globally and are saved automatically in Krita's configuration
after user changes. Changing sampler settings does not modify the document.
Enable and radius can also be changed with no document open.

Within a document, the selected source is kept as a node reference, so renaming
or reordering it preserves the selection. The source's name is persisted for
the next session and used to find a matching layer when switching documents.
With duplicate names, automatic selection uses Krita's first matching node.
If no matching source exists, the selection is cleared; the next settings save
overwrites the persisted name. Deleting the selected source also clears and
saves the selection.

Currently this plugin implements the settings docker and persistence only;
stroke interception and color sampling are not implemented yet.

To publish a release, commit the plugin and the release workflow, push the
commit, then create and push a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The GitHub Actions workflow creates a release with generated notes and attaches
`krita-stroke-sampler-v0.1.0.zip`. Tags such as `v0.1.0-beta.1` create
prereleases. The tag determines the release version; keep `pyproject.toml`'s
version consistent when preparing a release.

The installable files live in `plugin/`. The workflow ZIPs its contents, so
`stroke_sampler.desktop` and the `stroke_sampler/` directory sit at the archive
root. A copy of `LICENSE` lives in `plugin/stroke_sampler/`. It excludes the repository README,
tests, typings, development scripts, project configuration, and Python caches.
A future manual placed inside `plugin/stroke_sampler/` will be included automatically.
Users should download this ZIP from the release assets and import it through
**Tools → Scripts → Import Python Plugin…**.

Re-running the workflow replaces the ZIP on an existing release while retaining
its release notes. No additional GitHub token secret needs to be configured.
