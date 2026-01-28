#!/usr/bin/env python3
"""
Vision Analysis Module

VLM-powered image and video analysis for Physical AI and code diagrams.
Supports multiple analysis modes with Gemini 2.0 Flash (default) and GPT-4o fallback.
"""

import json
import os
import sys
import subprocess
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.llm_config import LLMConfigManager
from lib.llm_provider import ImageInput
from lib.providers.gemini_provider import GeminiProvider
from lib.providers.openai_provider import OpenAIProvider


class AnalysisMode(str, Enum):
    """Vision analysis modes"""
    DESCRIBE = "describe"
    DETECT_OBJECTS = "detect_objects"
    ANALYZE_DIAGRAM = "analyze_diagram"
    SAFETY_CHECK = "safety_check"


@dataclass
class BoundingBox:
    """Bounding box for detected objects"""
    x: float
    y: float
    width: float
    height: float
    confidence: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DetectedObject:
    """Detected object with bounding box"""
    label: str
    confidence: float
    bounding_box: Optional[BoundingBox] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        result = {
            "label": self.label,
            "confidence": self.confidence
        }
        if self.bounding_box:
            result["bounding_box"] = self.bounding_box.to_dict()
        return result


@dataclass
class VisionAnalysisResult:
    """Result from vision analysis"""
    mode: str
    description: str
    detected_objects: Optional[List[DetectedObject]] = None
    safety_issues: Optional[List[str]] = None
    diagram_elements: Optional[List[str]] = None
    confidence: Optional[float] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    cost: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result: Dict[str, Any] = {
            "mode": self.mode,
            "description": self.description
        }
        if self.detected_objects:
            result["detected_objects"] = [obj.to_dict() for obj in self.detected_objects]
        if self.safety_issues:
            result["safety_issues"] = self.safety_issues
        if self.diagram_elements:
            result["diagram_elements"] = self.diagram_elements
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.model:
            result["model"] = self.model
        if self.provider:
            result["provider"] = self.provider
        if self.cost is not None:
            result["cost"] = self.cost
        return result


class VisionAnalyzer:
    """
    Vision analyzer using VLM providers for image and video analysis.

    Uses Gemini 2.0 Flash as default (best vision + low cost), with
    GPT-4o fallback if Gemini unavailable.
    """

    def __init__(self, config_manager: Optional[LLMConfigManager] = None):
        """Initialize vision analyzer"""
        self.config_manager = config_manager or LLMConfigManager()
        self.primary_provider = None
        self.fallback_provider = None

        # Initialize providers (Gemini primary, OpenAI fallback)
        gemini_config = self.config_manager.get_provider("gemini")
        openai_config = self.config_manager.get_provider("openai")

        if gemini_config and gemini_config.enabled:
            self.primary_provider = GeminiProvider(gemini_config)

        if openai_config and openai_config.enabled:
            self.fallback_provider = OpenAIProvider(openai_config)

        if not self.primary_provider and not self.fallback_provider:
            raise ValueError("No vision providers available. Configure Gemini or OpenAI.")

    def _get_mode_prompt(self, mode: AnalysisMode) -> str:
        """Get analysis prompt for mode"""
        prompts = {
            AnalysisMode.DESCRIBE: (
                "Describe this image in detail. Include:\n"
                "- Main subjects and objects\n"
                "- Setting and environment\n"
                "- Actions and activities\n"
                "- Notable details\n"
                "Provide a comprehensive description."
            ),
            AnalysisMode.DETECT_OBJECTS: (
                "Detect and list all objects in this image. For each object:\n"
                "- Label (what it is)\n"
                "- Confidence (how certain you are, 0.0-1.0)\n"
                "- Location (approximate position in image)\n"
                "Return results as JSON array:\n"
                '[{"label": "...", "confidence": 0.95, "location": "..."}]'
            ),
            AnalysisMode.ANALYZE_DIAGRAM: (
                "Analyze this diagram or technical image. Identify:\n"
                "- Type of diagram (flowchart, architecture, UML, etc.)\n"
                "- Main components and elements\n"
                "- Relationships and connections\n"
                "- Data flow or control flow\n"
                "- Labels and annotations\n"
                "Provide a structured analysis."
            ),
            AnalysisMode.SAFETY_CHECK: (
                "Perform a safety analysis of this image. Check for:\n"
                "- PPE compliance (hard hats, safety vests, gloves, etc.)\n"
                "- Safety hazards (obstacles, spills, unsafe conditions)\n"
                "- Proper equipment usage\n"
                "- Safety zone violations\n"
                "- Emergency equipment accessibility\n"
                "List any safety issues found, or confirm if safe."
            )
        }
        return prompts.get(mode, prompts[AnalysisMode.DESCRIBE])

    def analyze(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
        mode: AnalysisMode = AnalysisMode.DESCRIBE,
        use_fallback: bool = False
    ) -> VisionAnalysisResult:
        """
        Analyze an image using VLM.

        Args:
            image_path: Path to image file
            image_base64: Base64-encoded image
            image_url: URL to image
            mode: Analysis mode
            use_fallback: Force use of fallback provider

        Returns:
            VisionAnalysisResult with analysis
        """
        # Create ImageInput
        image_input = ImageInput(
            base64=image_base64,
            url=image_url,
            file_path=image_path
        )

        # Select provider
        provider = self.fallback_provider if use_fallback else self.primary_provider
        if not provider:
            # Switch to alternative if requested provider unavailable
            provider = self.primary_provider or self.fallback_provider

        if not provider:
            raise ValueError("No vision provider available")

        # Get prompt for mode
        prompt = self._get_mode_prompt(mode)

        # Call provider
        try:
            response = provider.complete_with_vision(
                messages=[],
                images=[image_input],
                model=None,  # Use provider's default model
                prompt=prompt
            )

            # Parse response based on mode
            return self._parse_response(mode, response)

        except Exception as e:
            # Try fallback if primary failed
            if provider == self.primary_provider and self.fallback_provider:
                try:
                    response = self.fallback_provider.complete_with_vision(
                        messages=[],
                        images=[image_input],
                        model=None,
                        prompt=prompt
                    )
                    return self._parse_response(mode, response)
                except Exception as fallback_error:
                    raise Exception(f"Both providers failed. Primary: {str(e)}, Fallback: {str(fallback_error)}")
            raise

    def _parse_response(self, mode: AnalysisMode, response) -> VisionAnalysisResult:
        """Parse provider response into VisionAnalysisResult"""
        content = response.content

        # Mode-specific parsing
        if mode == AnalysisMode.DETECT_OBJECTS:
            # Try to extract JSON array from response
            detected_objects = self._extract_objects(content)
            return VisionAnalysisResult(
                mode=mode.value,
                description=content,
                detected_objects=detected_objects,
                model=response.model,
                provider=response.provider,
                cost=response.cost
            )

        elif mode == AnalysisMode.SAFETY_CHECK:
            # Extract safety issues
            safety_issues = self._extract_safety_issues(content)
            return VisionAnalysisResult(
                mode=mode.value,
                description=content,
                safety_issues=safety_issues,
                model=response.model,
                provider=response.provider,
                cost=response.cost
            )

        elif mode == AnalysisMode.ANALYZE_DIAGRAM:
            # Extract diagram elements
            diagram_elements = self._extract_diagram_elements(content)
            return VisionAnalysisResult(
                mode=mode.value,
                description=content,
                diagram_elements=diagram_elements,
                model=response.model,
                provider=response.provider,
                cost=response.cost
            )

        else:  # DESCRIBE
            return VisionAnalysisResult(
                mode=mode.value,
                description=content,
                model=response.model,
                provider=response.provider,
                cost=response.cost
            )

    def _extract_objects(self, content: str) -> List[DetectedObject]:
        """Extract detected objects from content"""
        objects = []
        try:
            # Try to find JSON array in content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)
                for item in data:
                    objects.append(DetectedObject(
                        label=item.get("label", "unknown"),
                        confidence=item.get("confidence", 0.5)
                    ))
        except Exception:
            # If parsing fails, return empty list
            pass
        return objects

    def _extract_safety_issues(self, content: str) -> List[str]:
        """Extract safety issues from content"""
        issues = []
        # Look for bullet points or numbered lists
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Check for list indicators
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                issue = line.lstrip('-•* ').strip()
                if issue:
                    issues.append(issue)
            elif line and line[0].isdigit() and '.' in line[:3]:
                issue = line.split('.', 1)[1].strip()
                if issue:
                    issues.append(issue)
        return issues

    def _extract_diagram_elements(self, content: str) -> List[str]:
        """Extract diagram elements from content"""
        elements = []
        # Look for bullet points or numbered lists
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Check for list indicators
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                element = line.lstrip('-•* ').strip()
                if element:
                    elements.append(element)
            elif line and line[0].isdigit() and '.' in line[:3]:
                element = line.split('.', 1)[1].strip()
                if element:
                    elements.append(element)
        return elements

    def extract_video_frames(
        self,
        video_path: str,
        fps: float = 1.0,
        output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Extract frames from video at specified fps.

        Args:
            video_path: Path to video file
            fps: Frames per second to extract (default: 1.0)
            output_dir: Directory to save frames (default: temp dir)

        Returns:
            List of frame file paths
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Create output directory
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(video_path), "frames")
        os.makedirs(output_dir, exist_ok=True)

        # Use ffmpeg to extract frames
        output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", f"fps={fps}",
            "-q:v", "2",  # High quality
            output_pattern
        ]

        try:
            # Run ffmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Get list of created frames
            frames = sorted([
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.startswith("frame_") and f.endswith(".jpg")
            ])

            return frames

        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to extract frames: {e.stderr}")
        except FileNotFoundError:
            raise Exception("ffmpeg not found. Please install ffmpeg to extract video frames.")

    def analyze_video(
        self,
        video_path: str,
        mode: AnalysisMode = AnalysisMode.DESCRIBE,
        fps: float = 1.0
    ) -> List[VisionAnalysisResult]:
        """
        Analyze video by extracting frames and analyzing each.

        Args:
            video_path: Path to video file
            mode: Analysis mode
            fps: Frames per second to extract (default: 1.0)

        Returns:
            List of VisionAnalysisResult for each frame
        """
        # Extract frames
        frames = self.extract_video_frames(video_path, fps=fps)

        # Analyze each frame
        results = []
        for frame_path in frames:
            result = self.analyze(
                image_path=frame_path,
                mode=mode
            )
            results.append(result)

        return results


def main():
    """CLI interface for vision analyzer"""
    import argparse

    parser = argparse.ArgumentParser(description="Vision Analysis CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze an image")
    analyze_parser.add_argument("image", help="Path to image file or URL")
    analyze_parser.add_argument("--mode", choices=["describe", "detect_objects", "analyze_diagram", "safety_check"],
                                default="describe", help="Analysis mode")
    analyze_parser.add_argument("--use-fallback", action="store_true", help="Use fallback provider (GPT-4o)")
    analyze_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Video command
    video_parser = subparsers.add_parser("video", help="Analyze a video")
    video_parser.add_argument("video", help="Path to video file")
    video_parser.add_argument("--mode", choices=["describe", "detect_objects", "analyze_diagram", "safety_check"],
                              default="describe", help="Analysis mode")
    video_parser.add_argument("--fps", type=float, default=1.0, help="Frames per second to extract")
    video_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test vision analyzer")

    # Modes command
    modes_parser = subparsers.add_parser("modes", help="List available analysis modes")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize analyzer
    try:
        analyzer = VisionAnalyzer()
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1

    if args.command == "analyze":
        # Analyze image
        try:
            mode = AnalysisMode(args.mode)

            # Determine if URL or file path
            if args.image.startswith("http://") or args.image.startswith("https://"):
                result = analyzer.analyze(image_url=args.image, mode=mode, use_fallback=args.use_fallback)
            else:
                result = analyzer.analyze(image_path=args.image, mode=mode, use_fallback=args.use_fallback)

            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
            else:
                print(f"Mode: {result.mode}")
                print(f"Provider: {result.provider}")
                print(f"Model: {result.model}")
                print(f"Cost: ${result.cost:.4f}" if result.cost else "Cost: N/A")
                print(f"\nDescription:\n{result.description}")

                if result.detected_objects:
                    print(f"\nDetected Objects ({len(result.detected_objects)}):")
                    for obj in result.detected_objects:
                        print(f"  - {obj.label} (confidence: {obj.confidence:.2f})")

                if result.safety_issues:
                    print(f"\nSafety Issues ({len(result.safety_issues)}):")
                    for issue in result.safety_issues:
                        print(f"  - {issue}")

                if result.diagram_elements:
                    print(f"\nDiagram Elements ({len(result.diagram_elements)}):")
                    for element in result.diagram_elements:
                        print(f"  - {element}")

        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1

    elif args.command == "video":
        # Analyze video
        try:
            mode = AnalysisMode(args.mode)
            results = analyzer.analyze_video(args.video, mode=mode, fps=args.fps)

            if args.json:
                output = [result.to_dict() for result in results]
                print(json.dumps(output, indent=2))
            else:
                print(f"Analyzed {len(results)} frames from video")
                print(f"Mode: {mode.value}")
                print(f"\nResults:")
                for i, result in enumerate(results, 1):
                    print(f"\nFrame {i}:")
                    print(f"  {result.description[:100]}...")

        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1

    elif args.command == "test":
        # Test connectivity
        print("Testing vision analyzer...")
        print(f"Primary provider: {analyzer.primary_provider.__class__.__name__ if analyzer.primary_provider else 'None'}")
        print(f"Fallback provider: {analyzer.fallback_provider.__class__.__name__ if analyzer.fallback_provider else 'None'}")
        print("\nVision analyzer is ready!")

    elif args.command == "modes":
        # List modes
        print("Available analysis modes:")
        print("  describe        - General image description")
        print("  detect_objects  - Object detection with labels and confidence")
        print("  analyze_diagram - Technical diagram analysis")
        print("  safety_check    - Safety compliance checking")

    return 0


if __name__ == "__main__":
    sys.exit(main())
