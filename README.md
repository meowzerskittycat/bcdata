# bcdata

A mirror of the game data archives the [BCSFE save editor](https://github.com/meowzerskittycat/BCSFE)
downloads to look up names, prices and limits. It's a fallback in case the upstream sources go
down.

- `metadata.json` lists every archive, in the same layout as upstream's, so the editor can use it
  as its game data source unchanged.
- The archives are files on the [`data` release](../../releases/tag/data).
- `.github/workflows/sync.yml` runs `sync.py` every day. It copies any new versions from upstream
  (fieryhenry's BCData on git.battlecatsmodding.org, then gitlab.com), checks each is a valid
  `.tar.xz`, uploads it and updates `metadata.json`. Versions are never removed.

To sync now: **Actions → Sync → Run workflow**. To see what's missing without changing anything:
`python sync.py --dry-run`.

The game data belongs to PONOS. This repository only mirrors files already published upstream for
use with the editor.
