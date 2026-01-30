# Unity XR Automation

When working with Unity XR projects in Physical AI applications:

## Unity Editor Automation

### Running Unity from Command Line
```bash
# Run Unity in batch mode (headless)
Unity -batchmode -quit -projectPath /path/to/project \
    -executeMethod BuildScript.BuildPlayer

# Run with log output
Unity -batchmode -projectPath /path/to/project \
    -logFile /path/to/log.txt \
    -executeMethod MyScript.RunTests

# Import package
Unity -batchmode -quit -projectPath /path/to/project \
    -importPackage /path/to/package.unitypackage
```

### EditorScript for Automation
```csharp
using UnityEditor;
using UnityEngine;

public class AutomationScript
{
    [MenuItem("Automation/Build XR Scene")]
    public static void BuildXRScene()
    {
        // Set XR settings
        PlayerSettings.virtualRealitySupported = true;

        // Build player
        BuildPipeline.BuildPlayer(
            new[] { "Assets/Scenes/MainXR.unity" },
            "Build/XRApp.exe",
            BuildTarget.StandaloneWindows64,
            BuildOptions.None
        );
    }

    public static void RunFromCommandLine()
    {
        // Called via -executeMethod
        Debug.Log("Running automation...");
        // Your automation logic here
    }
}
```

## XR Rig Setup

### OpenXR Configuration
```csharp
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features;

// Enable OpenXR features programmatically
var settings = OpenXRSettings.Instance;
if (settings != null)
{
    var feature = settings.GetFeature<HandTrackingFeature>();
    if (feature != null)
    {
        feature.enabled = true;
    }
}
```

### XR Origin Setup
```csharp
using Unity.XR.CoreUtils;
using UnityEngine.XR.Interaction.Toolkit;

public class XRSetup : MonoBehaviour
{
    void SetupXRRig()
    {
        // Create XR Origin
        var xrOrigin = new GameObject("XR Origin");
        xrOrigin.AddComponent<XROrigin>();

        // Add camera
        var camera = new GameObject("Main Camera");
        camera.transform.SetParent(xrOrigin.transform);
        camera.AddComponent<Camera>();
        camera.AddComponent<TrackedPoseDriver>();

        // Add controllers
        SetupController("Left Controller", true);
        SetupController("Right Controller", false);
    }

    void SetupController(string name, bool isLeft)
    {
        var controller = new GameObject(name);
        var xrController = controller.AddComponent<XRController>();
        xrController.controllerNode = isLeft ?
            XRNode.LeftHand : XRNode.RightHand;
    }
}
```

## Common Error Patterns

### XR Plugin Not Initialized
- **Error**: `XR Plugin not initialized`
- **Cause**: XR system not properly started
- **Solution**: Check Project Settings > XR Plug-in Management

### Missing XR Interaction Components
- **Error**: `NullReferenceException` in XR interactions
- **Cause**: Missing XRInteractionManager or interaction components
- **Solution**: Ensure scene has required components
```csharp
// Check for required components
if (FindObjectOfType<XRInteractionManager>() == null)
{
    var manager = new GameObject("XR Interaction Manager");
    manager.AddComponent<XRInteractionManager>();
}
```

### Tracking Loss
- **Error**: `Tracking lost` or position drift
- **Cause**: Poor tracking environment or device issues
- **Solution**: Implement tracking loss handling
```csharp
using UnityEngine.XR;

void CheckTrackingState()
{
    var device = InputDevices.GetDeviceAtXRNode(XRNode.Head);
    if (device.TryGetFeatureValue(CommonUsages.trackingState, out var state))
    {
        if ((state & InputTrackingState.Position) == 0)
        {
            Debug.LogWarning("Position tracking lost!");
        }
    }
}
```

### Build Errors for XR
- **Error**: Various build errors for XR platforms
- **Cause**: Missing XR SDK or incorrect build settings
- **Solution**: Verify XR SDK installation and settings
```bash
# Unity command line to check XR settings
Unity -batchmode -quit -projectPath . \
    -executeMethod CheckXRSettings.Verify
```

## Isaac Sim to Unity XR

### Exporting from Isaac Sim
```python
# Export USD for Unity
stage = Usd.Stage.Open("scene.usd")

# Export as FBX (Unity-compatible)
omni.kit.commands.execute(
    'ExportUSDCommand',
    usd_path='scene.usd',
    export_path='scene.fbx',
    export_format='fbx'
)

# Or use USD directly with Unity USD package
```

### Importing in Unity
```csharp
using Unity.Formats.USD;

public class USDImporter
{
    [MenuItem("Assets/Import USD")]
    static void ImportUSD()
    {
        string usdPath = EditorUtility.OpenFilePanel(
            "Select USD File", "", "usd,usda,usdc,usdz");

        if (!string.IsNullOrEmpty(usdPath))
        {
            var options = new SceneImportOptions();
            options.importPhysics = true;
            options.importMaterials = true;

            Scene.ImportUSD(usdPath, options);
        }
    }
}
```

## Testing XR Applications

### Editor Testing (XR Device Simulator)
```csharp
using UnityEngine.XR.Interaction.Toolkit.Inputs.Simulation;

// Enable XR Device Simulator for editor testing
var simulator = FindObjectOfType<XRDeviceSimulator>();
if (simulator != null)
{
    simulator.enabled = true;
}
```

### Automated Testing
```csharp
using NUnit.Framework;
using UnityEngine.TestTools;

public class XRTests
{
    [UnityTest]
    public IEnumerator XROrigin_InitializesCorrectly()
    {
        var xrOrigin = Object.FindObjectOfType<XROrigin>();
        Assert.IsNotNull(xrOrigin, "XR Origin should exist");

        yield return null;

        Assert.IsTrue(xrOrigin.Camera != null,
            "XR Origin should have a camera");
    }
}
```

## Best Practices

1. **Use XR Interaction Toolkit for interactions**
   - Consistent API across XR platforms
   - Built-in locomotion and UI interaction

2. **Handle device disconnection gracefully**
   ```csharp
   InputDevices.deviceDisconnected += OnDeviceDisconnected;
   ```

3. **Optimize for XR performance**
   - Target 72-90 FPS minimum
   - Use single-pass rendering
   - LOD for complex scenes

4. **Test on actual hardware**
   - Editor simulation is not the same
   - Each headset has quirks

5. **Support multiple XR platforms**
   - Use OpenXR for cross-platform support
   - Abstract platform-specific code
