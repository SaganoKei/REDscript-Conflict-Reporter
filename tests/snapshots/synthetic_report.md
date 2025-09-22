# REDscript Conflict Report

- Scanned root: `X:/game/mods`

- Files scanned: 5

- Annotation counts: replaceMethod=3, wrapMethod=1, replaceGlobal=0


## Conflicts (multiple files @replaceMethod the same method)

### HudManager.RefreshUI  — 1 occurrences  — Mods: ModC  — Low

Target method: `func RefreshUI() -> Void`

- [ModC] c.reds:5


### PlayerPuppet.OnUpdate  — 2 occurrences  — Mods: ModA, ModB  — Medium

Target method: `func OnUpdate(delta: Float) -> Void`

Baseline: Medium

- [ModA] a.reds:10

- [ModB] b.reds:20

@wrapMethod (coexisting):

  - [ModA] a.reds:10

  - [ModB] b.reds:20



## Reference

### HudManager.RefreshUI

Target method: `func RefreshUI() -> Void`

- [ModC] c.reds:5


### PlayerPuppet.OnUpdate

Target method: `func OnUpdate(delta: Float) -> Void`

- [ModA] a.reds:10

- [ModB] b.reds:20

