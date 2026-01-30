# USD (Universal Scene Description) Handling

When working with USD files in Physical AI applications, follow these guidelines:

## Prim Path Conventions

- All prim paths start with `/` (absolute) or are relative to current context
- Use hierarchical naming: `/World/Robot/Arm/Joint1`
- Avoid spaces and special characters in prim names
- Use PascalCase or snake_case for prim names consistently

## Common USD Prim Types

### Xform (Transforms)
```python
from pxr import Usd, UsdGeom

stage = Usd.Stage.Open("scene.usd")
xform = UsdGeom.Xform.Define(stage, "/World/Robot")
xform.AddTranslateOp().Set((0, 0, 1))
xform.AddRotateXYZOp().Set((0, 0, 90))
```

### Mesh Geometry
```python
mesh = UsdGeom.Mesh.Define(stage, "/World/Object/Mesh")
mesh.CreatePointsAttr([...])
mesh.CreateFaceVertexCountsAttr([...])
mesh.CreateFaceVertexIndicesAttr([...])
```

### Physics Bodies (Isaac Sim)
```python
from pxr import UsdPhysics

rigid_body = UsdPhysics.RigidBodyAPI.Apply(prim)
collision = UsdPhysics.CollisionAPI.Apply(prim)
mass = UsdPhysics.MassAPI.Apply(prim)
mass.CreateMassAttr(1.0)
```

## Common Error Patterns

### Invalid Prim Path
- **Error**: `Invalid prim path`
- **Cause**: Path contains invalid characters or malformed hierarchy
- **Solution**: Validate path with `Sdf.Path.IsValidPathString(path)`

### Missing Prim
- **Error**: `Prim not found at path`
- **Cause**: Prim doesn't exist in the stage
- **Solution**: Check `stage.GetPrimAtPath(path).IsValid()`

### Type Mismatch
- **Error**: `Cannot apply schema to prim`
- **Cause**: Attempting to apply incompatible API schema
- **Solution**: Check prim type before applying schemas

## Best Practices

1. **Always validate prim paths before operations**
   ```python
   from pxr import Sdf
   if not Sdf.Path.IsValidPathString(path):
       raise ValueError(f"Invalid prim path: {path}")
   ```

2. **Use context managers for stage operations**
   ```python
   with Usd.Stage.Open("scene.usd") as stage:
       # operations here
       stage.Save()
   ```

3. **Set up composition arcs properly**
   - Reference for reusable assets
   - Payload for heavy data (deferred loading)
   - Inherit for shared properties
   - Specialize for variations

4. **Handle layer stack correctly**
   ```python
   # Get strongest opinion
   attr = prim.GetAttribute("myAttr")
   value = attr.Get()  # Gets composed value

   # Set in session layer (non-destructive)
   stage.SetEditTarget(stage.GetSessionLayer())
   ```

## Isaac Sim Specific

### PhysX Extensions
```python
from omni.physx import get_physx_interface

physx = get_physx_interface()
physx.start_simulation()
```

### Articulation Root
```python
from pxr import PhysxSchema

articulation = PhysxSchema.PhysxArticulationAPI.Apply(prim)
articulation.CreateEnabledSelfCollisionsAttr(False)
```

### Sensor Setup
```python
# Camera sensor
camera = UsdGeom.Camera.Define(stage, "/World/Robot/Camera")
camera.CreateFocalLengthAttr(35)
camera.CreateHorizontalApertureAttr(36)

# Lidar (Isaac Sim extension)
# Use omni.isaac.sensor extension APIs
```
