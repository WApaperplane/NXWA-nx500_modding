# Nuklear source provenance

- Upstream: https://github.com/Immediate-Mode-UI/Nuklear
- Revision: `9f7750296f176e506c2b24ff55bc24495e2db750` (HEAD observed 2026-10-17).
- Files fetched from upstream master on 2026-10-17, unmodified.
- License selected: MIT (Alternative A in LICENSE).
- `nuklear.h` SHA256: `30a33586aeee98f71db083a6c1546295a4279fd8f214cfab36eec703eb98ebfd`
- `nuklear_xlib.h` SHA256: `0c6095fef05ccfb31c0967bc1802f14987c07c7f656c3b8bcb81fe6006b63d26`
- `LICENSE` SHA256: `b7c67c24445f3d5c16b6cd7aea2924d23209a416742a619d61bd38b05cbf64f9`

The event loop, panel layout, queue, engine adapter and deployment scripts are
NX-WA code outside these vendored files. `xvfb_local_paths.c` is only a development
helper and is never included in the camera binary or update package.
