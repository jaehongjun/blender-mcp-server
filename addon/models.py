"""Pydantic models for bridge command parameter validation.

Each model corresponds to a command accepted by the Blender add-on bridge.
The CommandHandler calls ``model.model_validate(params)`` on incoming dicts
so that invalid or missing fields are caught early with clear error messages.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Scene / inspection ─────────────────────────────────────────────


class SceneListObjectsParams(BaseModel):
    type: str | None = Field(None, description="Blender object type filter (MESH, CAMERA, LIGHT, …)")


class ObjectGetTransformParams(BaseModel):
    name: str = Field(..., description="Name of the object")


class ObjectGetHierarchyParams(BaseModel):
    name: str | None = Field(None, description="Root object name; omit for full scene tree")


# ── Object mutation ────────────────────────────────────────────────


class ObjectCreateMeshParams(BaseModel):
    type: str = Field("cube", description="Primitive type: cube, sphere, cylinder, plane, cone, torus")
    name: str | None = Field(None, description="Optional object name")
    location: list[float] = Field(
        default_factory=lambda: [0, 0, 0], description="World-space [x, y, z]", min_length=3, max_length=3
    )
    size: float = Field(2.0, gt=0, description="Uniform scale factor")


class ObjectDeleteParams(BaseModel):
    name: str


class ObjectTranslateParams(BaseModel):
    name: str
    location: list[float] | None = Field(None, description="Absolute position [x, y, z]", min_length=3, max_length=3)
    offset: list[float] | None = Field(None, description="Relative offset [x, y, z]", min_length=3, max_length=3)


class ObjectRotateParams(BaseModel):
    name: str
    rotation: list[float] = Field(
        default_factory=lambda: [0, 0, 0], description="Euler angles [x, y, z]", min_length=3, max_length=3
    )
    degrees: bool = Field(True, description="Interpret rotation as degrees (True) or radians (False)")


class ObjectScaleParams(BaseModel):
    name: str
    scale: list[float] = Field(
        default_factory=lambda: [1, 1, 1], description="Scale [x, y, z]", min_length=3, max_length=3
    )


class ObjectDuplicateParams(BaseModel):
    name: str
    new_name: str | None = Field(None, description="Name for the copy")


# ── Materials ──────────────────────────────────────────────────────


class MaterialCreateParams(BaseModel):
    name: str
    color: list[float] | None = Field(None, description="Base color [r, g, b] in 0-1 range", min_length=3, max_length=3)


class MaterialAssignParams(BaseModel):
    object: str = Field(..., description="Target object name")
    material: str = Field(..., description="Material name")


class MaterialSetColorParams(BaseModel):
    material: str
    color: list[float] = Field(..., description="[r, g, b] in 0-1 range", min_length=3, max_length=3)


class MaterialSetTextureParams(BaseModel):
    material: str
    path: str = Field(..., description="Image file path")


# ── Rendering & export ─────────────────────────────────────────────


class RenderStillParams(BaseModel):
    output_path: str = Field("//render.png")
    resolution_x: int | None = Field(None, gt=0)
    resolution_y: int | None = Field(None, gt=0)
    engine: str | None = Field(None, description="Render engine name (e.g. CYCLES, BLENDER_EEVEE)")


class RenderAnimationParams(BaseModel):
    output_path: str = Field("//render_")
    frame_start: int | None = None
    frame_end: int | None = None
    engine: str | None = None


class ExportFileParams(BaseModel):
    filepath: str


# ── Python execution ───────────────────────────────────────────────


class PythonExecuteParams(BaseModel):
    code: str | None = Field(None, description="Inline Python code")
    script_path: str | None = Field(None, description="Path to a .py script file")
    args: dict | None = Field(None, description="Keyword arguments passed to the script namespace")
    timeout_seconds: float | None = Field(None, gt=0)


class JobIdParams(BaseModel):
    job_id: str
