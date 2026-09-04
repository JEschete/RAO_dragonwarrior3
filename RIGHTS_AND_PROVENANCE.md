# Rights and Provenance

Locally authored plugin code is offered under MIT. That license does not cover ROMs, game assets, patches, trademarks, or content inside `decomp_reference`. Document every third-party source and its terms here.

## Decomp Reference

- Repository: `https://github.com/zeromus/DragonWarrior3.git`
- Pinned revision: `b35d5fd2046c33254f4387aa92bd3bce730f6c97`
- Location: `decomp_reference/DragonWarrior3`
- Runtime requirement: optional

The upstream repository and its contents remain governed by their own terms.

## Locally Generated Assets

The plugin may read a user-configured Dragon Warrior III ROM and generate map images in the user's local application-state directory. Generated images are derivative game content, are not covered by this repository's MIT license, and must not be committed or redistributed. The extractor validates supported ROM hashes and does not copy ROM bytes into the repository or generated metadata.

## Local Maps

The ignored `resources` directory may contain local fallback map images. They are used only when supported-ROM extraction is unavailable. Those files are not covered by this plugin's MIT license and must not be redistributed without a verified grant of permission. `resources/.gitkeep` is the only resource file tracked by default.
