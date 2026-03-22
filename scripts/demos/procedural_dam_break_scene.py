"""Stable procedural dam-break scene for Blender 4.0.x.

This scene avoids Mantaflow entirely and builds a visible flood animation from a
lightweight grid-based flood simulation. The result is intended for preview and
storyboarding in Blender builds where liquid domains are unstable in the
viewport.

Args:
    frame_end (int): End frame. Default 120.
    output_dir (str): Render output directory. Default "//".
    water_frames (int): Number of animated water frames to generate. Default 120.
"""

from __future__ import annotations

import bpy
import math


def ensure_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def link_to_collection(obj: bpy.types.Object, coll: bpy.types.Collection) -> None:
    for existing in tuple(obj.users_collection):
        existing.objects.unlink(obj)
    coll.objects.link(obj)


def create_block(name: str, size: tuple[float, float, float], location: tuple[float, float, float], coll: bpy.types.Collection) -> bpy.types.Object:
    sx, sy, sz = size
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    verts = [
        (-hx, -hy, -hz),
        (hx, -hy, -hz),
        (hx, hy, -hz),
        (-hx, hy, -hz),
        (-hx, -hy, hz),
        (hx, -hy, hz),
        (hx, hy, hz),
        (-hx, hy, hz),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    coll.objects.link(obj)
    return obj


def create_plane(name: str, size_x: float, size_y: float, z: float, coll: bpy.types.Collection) -> bpy.types.Object:
    hx, hy = size_x / 2.0, size_y / 2.0
    verts = [(-hx, -hy, z), (hx, -hy, z), (hx, hy, z), (-hx, hy, z)]
    faces = [(0, 1, 2, 3)]
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def create_material(
    name: str,
    base_color: tuple[float, float, float, float],
    *,
    roughness: float = 0.4,
    metallic: float = 0.0,
    transmission: float = 0.0,
    alpha: float = 1.0,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND" if alpha < 1.0 or transmission > 0.0 else "OPAQUE"
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Transmission Weight"].default_value = transmission
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = base_color
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def cell_center(ix: int, iy: int, origin_x: float, origin_y: float, cell_size: float) -> tuple[float, float]:
    return origin_x + (ix + 0.5) * cell_size, origin_y + (iy + 0.5) * cell_size


def build_environment(scene: bpy.types.Scene) -> tuple[list[dict], bpy.types.Collection, bpy.types.Collection]:
    env_coll = ensure_collection("Environment")
    bld_coll = ensure_collection("Buildings")
    debris_coll = ensure_collection("Debris")

    ground = create_plane("Ground", 26.0, 20.0, -0.04, env_coll)
    sidewalks = [
        create_block("Sidewalk_North", (26.0, 2.0, 0.18), (0.0, 4.1, 0.05), env_coll),
        create_block("Sidewalk_South", (26.0, 2.0, 0.18), (0.0, -4.1, 0.05), env_coll),
        create_block("Sidewalk_East", (2.2, 20.0, 0.18), (4.6, 0.0, 0.05), env_coll),
        create_block("Sidewalk_West", (2.2, 20.0, 0.18), (-4.6, 0.0, 0.05), env_coll),
    ]
    road_main = create_block("MainStreet", (26.0, 4.2, 0.06), (0.0, 0.0, 0.0), env_coll)
    road_cross = create_block("CrossStreet", (4.0, 20.0, 0.06), (0.0, 0.0, 0.001), env_coll)
    barrier = create_block("DamWall", (0.5, 4.8, 1.8), (9.3, 0.0, 0.9), env_coll)
    barrier.keyframe_insert(data_path="location", frame=1)
    barrier.location = (10.4, 0.0, -1.2)
    barrier.rotation_euler = (0.0, math.radians(16), math.radians(-8))
    barrier.keyframe_insert(data_path="location", frame=10)
    barrier.keyframe_insert(data_path="rotation_euler", frame=10)

    building_specs = [
        {"name": "Building_A", "size": (3.6, 3.1, 4.4), "loc": (6.3, 5.7, 2.2)},
        {"name": "Building_B", "size": (3.0, 3.8, 5.4), "loc": (1.5, 5.5, 2.7)},
        {"name": "Building_C", "size": (4.2, 2.8, 3.8), "loc": (-5.6, 5.1, 1.9)},
        {"name": "Building_D", "size": (3.2, 3.4, 4.2), "loc": (6.8, -5.6, 2.1)},
        {"name": "Building_E", "size": (3.6, 4.4, 5.0), "loc": (-2.4, -5.7, 2.5)},
        {"name": "Building_F", "size": (3.4, 3.0, 4.0), "loc": (-7.0, -5.0, 2.0)},
    ]

    buildings = []
    for spec in building_specs:
        obj = create_block(spec["name"], spec["size"], spec["loc"], bld_coll)
        spec["object"] = obj
        spec["footprint"] = (
            spec["loc"][0] - spec["size"][0] / 2.0 - 0.15,
            spec["loc"][0] + spec["size"][0] / 2.0 + 0.15,
            spec["loc"][1] - spec["size"][1] / 2.0 - 0.15,
            spec["loc"][1] + spec["size"][1] / 2.0 + 0.15,
        )
        buildings.append(spec)

    debris_specs = [
        {"name": "Debris_Crate", "size": (0.8, 0.8, 0.6), "loc": (3.0, -1.0, 0.32)},
        {"name": "Debris_Barrel", "size": (0.7, 0.7, 0.9), "loc": (1.0, 1.1, 0.45)},
        {"name": "Debris_Pallet", "size": (1.2, 0.8, 0.16), "loc": (5.6, 1.6, 0.08)},
        {"name": "Debris_Bin", "size": (0.7, 0.7, 1.0), "loc": (-0.8, -1.2, 0.5)},
    ]
    for spec in debris_specs:
        spec["object"] = create_block(spec["name"], spec["size"], spec["loc"], debris_coll)

    road_mat = create_material("RoadMaterial", (0.11, 0.12, 0.13, 1.0), roughness=0.92)
    sidewalk_mat = create_material("SidewalkMaterial", (0.28, 0.29, 0.30, 1.0), roughness=0.88)
    building_mat = create_material("BuildingMaterial", (0.73, 0.73, 0.72, 1.0), roughness=0.7)
    wall_mat = create_material("BarrierMaterial", (0.46, 0.47, 0.50, 1.0), roughness=0.84)
    debris_mat = create_material("DebrisMaterial", (0.42, 0.29, 0.18, 1.0), roughness=0.75)

    assign_material(ground, road_mat)
    assign_material(road_main, road_mat)
    assign_material(road_cross, road_mat)
    assign_material(barrier, wall_mat)
    for obj in sidewalks:
        assign_material(obj, sidewalk_mat)
    for spec in buildings:
        assign_material(spec["object"], building_mat)
    for spec in debris_specs:
        assign_material(spec["object"], debris_mat)

    return buildings, debris_coll, env_coll


def terrain_height(x: float, y: float) -> float:
    height = 0.05 * x
    if abs(y) < 2.1:
        height -= 0.28
    if abs(x) < 1.7:
        height -= 0.18
    if abs(y) > 7.0:
        height += 0.06
    return height


def inside_footprint(x: float, y: float, footprint: tuple[float, float, float, float]) -> bool:
    min_x, max_x, min_y, max_y = footprint
    return min_x <= x <= max_x and min_y <= y <= max_y


def simulate_flood(buildings: list[dict], frames: int, grid_x: int, grid_y: int, cell_size: float) -> tuple[list[list[list[float]]], list[list[list[tuple[float, float]]]]]:
    origin_x = -12.0
    origin_y = -9.0
    obstacles = [[False for _ in range(grid_y)] for _ in range(grid_x)]
    terrain = [[0.0 for _ in range(grid_y)] for _ in range(grid_x)]

    for ix in range(grid_x):
        for iy in range(grid_y):
            x, y = cell_center(ix, iy, origin_x, origin_y, cell_size)
            terrain[ix][iy] = terrain_height(x, y)
            obstacles[ix][iy] = any(inside_footprint(x, y, b["footprint"]) for b in buildings)

    depth = [[0.0 for _ in range(grid_y)] for _ in range(grid_x)]
    depth_frames: list[list[list[float]]] = []
    velocity_frames: list[list[list[tuple[float, float]]]] = []
    source_cells = [
        (ix, iy)
        for ix in range(grid_x)
        for iy in range(grid_y)
        if cell_center(ix, iy, origin_x, origin_y, cell_size)[0] > 8.2 and abs(cell_center(ix, iy, origin_x, origin_y, cell_size)[1]) < 2.4
    ]

    for frame in range(1, frames + 1):
        frame_velocity = [[(0.0, 0.0) for _ in range(grid_y)] for _ in range(grid_x)]
        for _substep in range(2):
            incoming = [[0.0 for _ in range(grid_y)] for _ in range(grid_x)]
            outgoing = [[0.0 for _ in range(grid_y)] for _ in range(grid_x)]
            for ix in range(grid_x):
                for iy in range(grid_y):
                    if obstacles[ix][iy]:
                        continue
                    here_depth = depth[ix][iy]
                    if here_depth <= 0.0001:
                        continue
                    surface = terrain[ix][iy] + here_depth
                    candidates = []
                    total_flow = 0.0
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx = ix + dx
                        ny = iy + dy
                        if nx < 0 or ny < 0 or nx >= grid_x or ny >= grid_y or obstacles[nx][ny]:
                            continue
                        neighbor_surface = terrain[nx][ny] + depth[nx][ny]
                        delta = surface - neighbor_surface
                        if delta <= 0.002:
                            continue
                        amount = delta * 0.30
                        candidates.append((nx, ny, dx, dy, amount))
                        total_flow += amount
                    if total_flow <= 0.0:
                        continue
                    scale = 1.0
                    if total_flow > here_depth:
                        scale = here_depth / total_flow
                    moved_x = 0.0
                    moved_y = 0.0
                    for nx, ny, dx, dy, amount in candidates:
                        flow = amount * scale
                        outgoing[ix][iy] += flow
                        incoming[nx][ny] += flow
                        moved_x += dx * flow
                        moved_y += dy * flow
                    frame_velocity[ix][iy] = (moved_x, moved_y)
            for ix in range(grid_x):
                for iy in range(grid_y):
                    if obstacles[ix][iy]:
                        depth[ix][iy] = 0.0
                        continue
                    depth[ix][iy] = max(0.0, (depth[ix][iy] + incoming[ix][iy] - outgoing[ix][iy]) * 0.998)

            if frame <= 12:
                injection = 0.92
            elif frame <= 30:
                injection = 0.54
            elif frame <= 70:
                injection = 0.28
            else:
                injection = 0.12

            per_cell = injection / max(1, len(source_cells))
            for ix, iy in source_cells:
                depth[ix][iy] += per_cell

        depth_frames.append([row[:] for row in depth])
        velocity_frames.append([[frame_velocity[ix][iy] for iy in range(grid_y)] for ix in range(grid_x)])

    return depth_frames, velocity_frames


def create_water_mesh(name: str, depth_grid: list[list[float]], buildings: list[dict], cell_size: float, mat: bpy.types.Material, coll: bpy.types.Collection) -> bpy.types.Object:
    grid_x = len(depth_grid)
    grid_y = len(depth_grid[0])
    origin_x = -12.0
    origin_y = -9.0

    def wet(ix: int, iy: int) -> bool:
        if ix < 0 or iy < 0 or ix >= grid_x or iy >= grid_y:
            return False
        depth = depth_grid[ix][iy]
        if depth <= 0.03:
            return False
        x, y = cell_center(ix, iy, origin_x, origin_y, cell_size)
        return not any(inside_footprint(x, y, b["footprint"]) for b in buildings)

    corner_indices: dict[tuple[int, int], int] = {}
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    def corner_height(cx: int, cy: int) -> float:
        samples = []
        for ox, oy in ((-1, -1), (-1, 0), (0, -1), (0, 0)):
            ix = cx + ox
            iy = cy + oy
            if 0 <= ix < grid_x and 0 <= iy < grid_y and wet(ix, iy):
                x, y = cell_center(ix, iy, origin_x, origin_y, cell_size)
                samples.append(terrain_height(x, y) + depth_grid[ix][iy] * 2.6 + 0.03)
        return sum(samples) / len(samples) if samples else 0.0

    def get_corner(cx: int, cy: int) -> int:
        key = (cx, cy)
        index = corner_indices.get(key)
        if index is not None:
            return index
        x = origin_x + cx * cell_size
        y = origin_y + cy * cell_size
        z = corner_height(cx, cy)
        corner_indices[key] = len(verts)
        verts.append((x, y, z))
        return corner_indices[key]

    for ix in range(grid_x):
        for iy in range(grid_y):
            if not wet(ix, iy):
                continue
            v0 = get_corner(ix, iy)
            v1 = get_corner(ix + 1, iy)
            v2 = get_corner(ix + 1, iy + 1)
            v3 = get_corner(ix, iy + 1)
            faces.append((v0, v1, v2, v3))

    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    assign_material(obj, mat)
    obj.hide_render = True
    obj.hide_viewport = True
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def key_single_frame_visibility(obj: bpy.types.Object, frame: int, frame_end: int) -> None:
    for frame_num, hidden in ((1, True), (max(1, frame - 1), True), (frame, False), (min(frame_end, frame + 1), True)):
        obj.hide_viewport = hidden
        obj.hide_render = hidden
        obj.keyframe_insert(data_path="hide_viewport", frame=frame_num)
        obj.keyframe_insert(data_path="hide_render", frame=frame_num)


def animate_debris(debris_specs: list[dict], depth_frames: list[list[list[float]]], velocity_frames: list[list[list[tuple[float, float]]]], frame_end: int, cell_size: float) -> None:
    origin_x = -12.0
    origin_y = -9.0
    grid_x = len(depth_frames[0])
    grid_y = len(depth_frames[0][0])

    def sample(ix: int, iy: int, frame_idx: int) -> tuple[float, float, float]:
        if ix < 0 or iy < 0 or ix >= grid_x or iy >= grid_y:
            return 0.0, 0.0, 0.0
        vx, vy = velocity_frames[frame_idx][ix][iy]
        return depth_frames[frame_idx][ix][iy], vx, vy

    for spec in debris_specs:
        obj = spec["object"]
        x, y, z = spec["loc"]
        for frame in range(1, frame_end + 1, 4):
            frame_idx = frame - 1
            ix = int((x - origin_x) / cell_size)
            iy = int((y - origin_y) / cell_size)
            depth, vx, vy = sample(ix, iy, frame_idx)
            if depth > 0.035:
                x += vx * 0.9
                y += vy * 0.9
                z = 0.10 + min(0.55, depth * 1.6)
                obj.rotation_euler.z += (vx - vy) * 0.12
                obj.rotation_euler.x += 0.04
            obj.location = (x, y, z)
            obj.keyframe_insert(data_path="location", frame=frame)
            obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def create_camera(scene: bpy.types.Scene) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new("DamBreakCam")
    cam_data.lens = 28
    cam_obj = bpy.data.objects.new("DamBreakCam", cam_data)
    ensure_collection("Camera").objects.link(cam_obj)
    scene.camera = cam_obj

    keys = [
        (1, (18.0, -15.0, 10.5), (math.radians(60), 0.0, math.radians(48))),
        (45, (13.0, -12.5, 8.0), (math.radians(63), 0.0, math.radians(38))),
        (90, (9.0, -10.5, 6.2), (math.radians(66), 0.0, math.radians(27))),
        (120, (5.0, -9.0, 4.6), (math.radians(69), 0.0, math.radians(18))),
    ]
    for frame, location, rotation in keys:
        cam_obj.location = location
        cam_obj.rotation_euler = rotation
        cam_obj.keyframe_insert(data_path="location", frame=frame)
        cam_obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    return cam_obj


frame_end = int(args.get("frame_end", 120))
output_dir = args.get("output_dir", "//")
water_frames = int(args.get("water_frames", frame_end))
water_frames = max(1, min(frame_end, water_frames))

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = frame_end
scene.frame_current = 1
scene.render.fps = 24
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.render.filepath = output_dir + "procedural_dam_break"

world = scene.world
if world:
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.58, 0.63, 0.69, 1.0)
        bg.inputs[1].default_value = 0.95

buildings, debris_coll, env_coll = build_environment(scene)
debris_specs = [
    {"name": obj.name, "object": obj, "loc": tuple(obj.location)}
    for obj in debris_coll.objects
]

water_coll = ensure_collection("FloodWater")
water_mat = create_material(
    "FloodWaterMaterial",
    (0.05, 0.44, 0.96, 1.0),
    roughness=0.06,
    transmission=0.0,
    alpha=1.0,
    emission_strength=0.18,
)

cell_size = 0.6
grid_x = 40
grid_y = 30
depth_frames, velocity_frames = simulate_flood(buildings, water_frames, grid_x, grid_y, cell_size)

water_objects = []
for frame_idx, depth_grid in enumerate(depth_frames, start=1):
    obj = create_water_mesh(f"FloodSurface_{frame_idx:04d}", depth_grid, buildings, cell_size, water_mat, water_coll)
    key_single_frame_visibility(obj, frame_idx, frame_end)
    water_objects.append(obj.name)

animate_debris(debris_specs, depth_frames, velocity_frames, frame_end, cell_size)
cam_obj = create_camera(scene)

for obj in env_coll.objects:
    obj.pass_index = 1
for obj in debris_coll.objects:
    obj.pass_index = 2

scene.frame_set(min(frame_end, 90))

sample_frames = {}
for frame in (1, min(30, water_frames), min(60, water_frames), water_frames):
    wet = sum(1 for row in depth_frames[frame - 1] for depth in row if depth > 0.03)
    sample_frames[frame] = {"wet_cells": wet}

__result__ = {
    "scene": scene.name,
    "frame_range": [scene.frame_start, scene.frame_end],
    "water_objects": len(water_objects),
    "water_collection": water_coll.name,
    "buildings": [spec["name"] for spec in buildings],
    "debris": [spec["name"] for spec in debris_specs],
    "camera": cam_obj.name,
    "render_engine": scene.render.engine,
    "sample_frames": sample_frames,
    "notes": [
        "This scene uses a stable procedural flood mesh sequence instead of Mantaflow.",
        "Scrub or play frames 1-120 to see the wave advance through the streets.",
    ],
}
