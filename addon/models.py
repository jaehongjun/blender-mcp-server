"""Pydantic models for bridge command parameter validation.

Each model corresponds to a command accepted by the Blender add-on bridge.
The CommandHandler calls ``model.model_validate(params)`` on incoming dicts
so that invalid or missing fields are caught early with clear error messages.
"""

from __future__ import annotations

import types
from typing import Any, get_args, get_origin, get_type_hints

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:
    _UNSET = object()

    class _FieldInfo:
        def __init__(
            self,
            default: Any = _UNSET,
            *,
            default_factory: Any = None,
            description: str | None = None,
            min_length: int | None = None,
            max_length: int | None = None,
            gt: int | float | None = None,
        ):
            self.default = default
            self.default_factory = default_factory
            self.description = description
            self.min_length = min_length
            self.max_length = max_length
            self.gt = gt

    def Field(default: Any = _UNSET, **kwargs: Any) -> _FieldInfo:
        if default is ...:
            default = _UNSET
        return _FieldInfo(default, **kwargs)

    def _is_union(annotation: Any) -> bool:
        origin = get_origin(annotation)
        return origin in (types.UnionType, getattr(__import__("typing"), "Union"))

    def _coerce_value(value: Any, annotation: Any, field_name: str) -> Any:
        if annotation is Any:
            return value

        if _is_union(annotation):
            args = get_args(annotation)
            if value is None and type(None) in args:
                return None
            last_error: Exception | None = None
            for arg in args:
                if arg is type(None):
                    continue
                try:
                    return _coerce_value(value, arg, field_name)
                except (TypeError, ValueError) as exc:
                    last_error = exc
            raise ValueError(str(last_error) if last_error else f"Invalid value for '{field_name}'")

        origin = get_origin(annotation)
        if origin is list:
            if not isinstance(value, list):
                raise TypeError(f"'{field_name}' must be a list")
            args = get_args(annotation)
            item_type = args[0] if args else Any
            return [_coerce_value(item, item_type, field_name) for item in value]

        if origin is dict:
            if not isinstance(value, dict):
                raise TypeError(f"'{field_name}' must be a dict")
            return value

        if annotation is bool:
            if not isinstance(value, bool):
                raise TypeError(f"'{field_name}' must be a bool")
            return value

        if annotation is int:
            if isinstance(value, bool):
                raise TypeError(f"'{field_name}' must be an int")
            if not isinstance(value, int):
                raise TypeError(f"'{field_name}' must be an int")
            return value

        if annotation is float:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"'{field_name}' must be a number")
            return float(value)

        if annotation is str:
            if not isinstance(value, str):
                raise TypeError(f"'{field_name}' must be a string")
            return value

        return value

    class BaseModel:
        def __init__(self, **values: Any):
            for key, value in values.items():
                setattr(self, key, value)

        @classmethod
        def model_validate(cls, payload: dict[str, Any] | None):
            data = payload or {}
            values: dict[str, Any] = {}

            for field_name, annotation in get_type_hints(cls).items():
                field_def = getattr(cls, field_name, _UNSET)
                if isinstance(field_def, _FieldInfo):
                    default = field_def.default
                    default_factory = field_def.default_factory
                    min_length = field_def.min_length
                    max_length = field_def.max_length
                    gt = field_def.gt
                else:
                    default = field_def
                    default_factory = None
                    min_length = None
                    max_length = None
                    gt = None

                if field_name in data:
                    value = data[field_name]
                elif default_factory is not None:
                    value = default_factory()
                elif default is not _UNSET:
                    value = default
                else:
                    raise ValueError(f"Missing required field: {field_name}")

                coerced = _coerce_value(value, annotation, field_name)
                if min_length is not None and coerced is not None and len(coerced) < min_length:
                    raise ValueError(f"'{field_name}' must contain at least {min_length} items")
                if max_length is not None and coerced is not None and len(coerced) > max_length:
                    raise ValueError(f"'{field_name}' must contain at most {max_length} items")
                if gt is not None and coerced is not None and coerced <= gt:
                    raise ValueError(f"'{field_name}' must be greater than {gt}")

                values[field_name] = coerced

            return cls(**values)

        def model_dump(self, *, exclude_none: bool = False) -> dict[str, Any]:
            if not exclude_none:
                return dict(self.__dict__)
            return {key: value for key, value in self.__dict__.items() if value is not None}

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
