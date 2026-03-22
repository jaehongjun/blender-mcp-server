"""Open Blender GUI with the dam-break scene built and baked.

This launcher avoids the Blender 4.0.2 viewport crash by keeping the liquid
domain modifier hidden in the viewport during setup and baking.

Run:
    blender --factory-startup --python scripts/demos/open_dam_break_gui.py
"""

from __future__ import annotations

from pathlib import Path

import bpy


SCENE_SCRIPT = Path(__file__).with_name("dam_break_scene.py")


def main() -> None:
    args = {
        "resolution": 32,
        "frame_end": 120,
        "output_dir": "//",
    }
    namespace = {
        "__name__": "__main__",
        "args": args,
    }

    code = SCENE_SCRIPT.read_text(encoding="utf-8")
    exec(compile(code, str(SCENE_SCRIPT), "exec"), namespace)

    domain = bpy.data.objects["FluidDomain"]
    bpy.context.view_layer.objects.active = domain
    domain.select_set(True)
    bpy.context.view_layer.update()

    if bpy.ops.fluid.bake_all.poll():
        bpy.ops.fluid.bake_all()

    bpy.context.scene.frame_set(bpy.context.scene.frame_end)
    print("Dam-break scene ready in Blender GUI")


if __name__ == "__main__":
    main()
