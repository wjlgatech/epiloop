#!/usr/bin/env python3
"""
Unit tests for vision_analyzer.py
"""

import unittest
import os
import sys
import subprocess
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.vision_analyzer import (
    VisionAnalyzer,
    AnalysisMode,
    BoundingBox,
    DetectedObject,
    VisionAnalysisResult
)
from lib.llm_provider import LLMResponse, TokenUsage


class TestBoundingBox(unittest.TestCase):
    """Test BoundingBox dataclass"""

    def test_to_dict(self):
        """Test BoundingBox to_dict conversion"""
        bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0, confidence=0.95)
        result = bbox.to_dict()
        self.assertEqual(result["x"], 10.0)
        self.assertEqual(result["y"], 20.0)
        self.assertEqual(result["width"], 100.0)
        self.assertEqual(result["height"], 50.0)
        self.assertEqual(result["confidence"], 0.95)


class TestDetectedObject(unittest.TestCase):
    """Test DetectedObject dataclass"""

    def test_to_dict_with_bbox(self):
        """Test DetectedObject to_dict with bounding box"""
        bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        obj = DetectedObject(label="car", confidence=0.92, bounding_box=bbox)
        result = obj.to_dict()
        self.assertEqual(result["label"], "car")
        self.assertEqual(result["confidence"], 0.92)
        self.assertIn("bounding_box", result)

    def test_to_dict_without_bbox(self):
        """Test DetectedObject to_dict without bounding box"""
        obj = DetectedObject(label="person", confidence=0.88)
        result = obj.to_dict()
        self.assertEqual(result["label"], "person")
        self.assertEqual(result["confidence"], 0.88)
        self.assertNotIn("bounding_box", result)


class TestVisionAnalysisResult(unittest.TestCase):
    """Test VisionAnalysisResult dataclass"""

    def test_to_dict_describe_mode(self):
        """Test result to_dict for describe mode"""
        result = VisionAnalysisResult(
            mode="describe",
            description="A sunny day at the beach",
            model="gemini-2.0-flash",
            provider="gemini",
            cost=0.0001
        )
        data = result.to_dict()
        self.assertEqual(data["mode"], "describe")
        self.assertEqual(data["description"], "A sunny day at the beach")
        self.assertEqual(data["model"], "gemini-2.0-flash")
        self.assertEqual(data["provider"], "gemini")
        self.assertEqual(data["cost"], 0.0001)

    def test_to_dict_detect_objects_mode(self):
        """Test result to_dict for detect_objects mode"""
        obj1 = DetectedObject(label="car", confidence=0.95)
        obj2 = DetectedObject(label="person", confidence=0.88)
        result = VisionAnalysisResult(
            mode="detect_objects",
            description="Detected 2 objects",
            detected_objects=[obj1, obj2],
            model="gpt-4o",
            provider="openai",
            cost=0.0005
        )
        data = result.to_dict()
        self.assertEqual(data["mode"], "detect_objects")
        self.assertEqual(len(data["detected_objects"]), 2)

    def test_to_dict_safety_check_mode(self):
        """Test result to_dict for safety_check mode"""
        result = VisionAnalysisResult(
            mode="safety_check",
            description="Safety issues found",
            safety_issues=["No hard hat", "Missing safety vest"],
            model="gemini-2.0-flash",
            provider="gemini",
            cost=0.0001
        )
        data = result.to_dict()
        self.assertEqual(data["mode"], "safety_check")
        self.assertEqual(len(data["safety_issues"]), 2)


class TestVisionAnalyzer(unittest.TestCase):
    """Test VisionAnalyzer class"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock config manager
        self.mock_config = MagicMock()
        self.mock_gemini_config = MagicMock()
        self.mock_gemini_config.enabled = True
        self.mock_gemini_config.default_model = "gemini-2.0-flash"
        self.mock_openai_config = MagicMock()
        self.mock_openai_config.enabled = True
        self.mock_openai_config.default_model = "gpt-4o"

        self.mock_config.get_provider.side_effect = lambda name: {
            "gemini": self.mock_gemini_config,
            "openai": self.mock_openai_config
        }.get(name)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_initialization_with_both_providers(self, mock_openai_cls, mock_gemini_cls):
        """Test VisionAnalyzer initialization with both providers available"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        self.assertIsNotNone(analyzer.primary_provider)
        self.assertIsNotNone(analyzer.fallback_provider)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_initialization_with_only_openai(self, mock_openai_cls, mock_gemini_cls):
        """Test VisionAnalyzer initialization with only OpenAI"""
        # Disable Gemini
        self.mock_gemini_config.enabled = False
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        self.assertIsNone(analyzer.primary_provider)
        self.assertIsNotNone(analyzer.fallback_provider)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_initialization_no_providers(self, mock_openai_cls, mock_gemini_cls):
        """Test VisionAnalyzer initialization with no providers"""
        self.mock_gemini_config.enabled = False
        self.mock_openai_config.enabled = False
        with self.assertRaises(ValueError):
            VisionAnalyzer(config_manager=self.mock_config)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_get_mode_prompt_describe(self, mock_openai_cls, mock_gemini_cls):
        """Test mode prompt for describe"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        prompt = analyzer._get_mode_prompt(AnalysisMode.DESCRIBE)
        self.assertIn("Describe this image", prompt)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_get_mode_prompt_detect_objects(self, mock_openai_cls, mock_gemini_cls):
        """Test mode prompt for detect_objects"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        prompt = analyzer._get_mode_prompt(AnalysisMode.DETECT_OBJECTS)
        self.assertIn("Detect and list all objects", prompt)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_get_mode_prompt_analyze_diagram(self, mock_openai_cls, mock_gemini_cls):
        """Test mode prompt for analyze_diagram"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        prompt = analyzer._get_mode_prompt(AnalysisMode.ANALYZE_DIAGRAM)
        self.assertIn("Analyze this diagram", prompt)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_get_mode_prompt_safety_check(self, mock_openai_cls, mock_gemini_cls):
        """Test mode prompt for safety_check"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        prompt = analyzer._get_mode_prompt(AnalysisMode.SAFETY_CHECK)
        self.assertIn("safety analysis", prompt)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_with_file_path(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze with file path"""
        # Create mock provider
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content="A beautiful sunset over the ocean",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.0001,
            provider="gemini"
        )
        mock_provider.complete_with_vision.return_value = mock_response
        mock_gemini_cls.return_value = mock_provider

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_provider

        result = analyzer.analyze(image_path="/path/to/image.jpg")

        self.assertEqual(result.mode, "describe")
        self.assertIn("sunset", result.description)
        self.assertEqual(result.model, "gemini-2.0-flash")
        self.assertEqual(result.provider, "gemini")

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_with_url(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze with URL"""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content="A busy street with cars and people",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.0001,
            provider="gemini"
        )
        mock_provider.complete_with_vision.return_value = mock_response
        mock_gemini_cls.return_value = mock_provider

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_provider

        result = analyzer.analyze(image_url="https://example.com/image.jpg")

        self.assertEqual(result.mode, "describe")
        self.assertIn("street", result.description)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_with_base64(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze with base64"""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content="A red apple on a table",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.0001,
            provider="gemini"
        )
        mock_provider.complete_with_vision.return_value = mock_response
        mock_gemini_cls.return_value = mock_provider

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_provider

        result = analyzer.analyze(image_base64="base64encodedstring")

        self.assertEqual(result.mode, "describe")
        self.assertIn("apple", result.description)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_detect_objects_mode(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze with detect_objects mode"""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content='Objects detected:\n[{"label": "car", "confidence": 0.95}, {"label": "person", "confidence": 0.88}]',
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.0001,
            provider="gemini"
        )
        mock_provider.complete_with_vision.return_value = mock_response
        mock_gemini_cls.return_value = mock_provider

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_provider

        result = analyzer.analyze(
            image_path="/path/to/image.jpg",
            mode=AnalysisMode.DETECT_OBJECTS
        )

        self.assertEqual(result.mode, "detect_objects")
        self.assertIsNotNone(result.detected_objects)
        if result.detected_objects:
            self.assertEqual(len(result.detected_objects), 2)
            self.assertEqual(result.detected_objects[0].label, "car")
            self.assertEqual(result.detected_objects[0].confidence, 0.95)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_safety_check_mode(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze with safety_check mode"""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content="Safety issues found:\n- No hard hat\n- Missing safety vest\n- Unsafe footwear",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.0001,
            provider="gemini"
        )
        mock_provider.complete_with_vision.return_value = mock_response
        mock_gemini_cls.return_value = mock_provider

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_provider

        result = analyzer.analyze(
            image_path="/path/to/image.jpg",
            mode=AnalysisMode.SAFETY_CHECK
        )

        self.assertEqual(result.mode, "safety_check")
        self.assertIsNotNone(result.safety_issues)
        if result.safety_issues:
            self.assertEqual(len(result.safety_issues), 3)
            self.assertIn("No hard hat", result.safety_issues)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_diagram_mode(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze with analyze_diagram mode"""
        mock_provider = MagicMock()
        mock_response = LLMResponse(
            content="Diagram elements:\n- Input node\n- Processing node\n- Output node\n- Data flow arrows",
            model="gemini-2.0-flash",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.0001,
            provider="gemini"
        )
        mock_provider.complete_with_vision.return_value = mock_response
        mock_gemini_cls.return_value = mock_provider

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_provider

        result = analyzer.analyze(
            image_path="/path/to/diagram.png",
            mode=AnalysisMode.ANALYZE_DIAGRAM
        )

        self.assertEqual(result.mode, "analyze_diagram")
        self.assertIsNotNone(result.diagram_elements)
        if result.diagram_elements:
            self.assertEqual(len(result.diagram_elements), 4)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_with_fallback(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze with fallback to OpenAI"""
        mock_gemini = MagicMock()
        mock_gemini.complete_with_vision.side_effect = Exception("Gemini error")
        mock_openai = MagicMock()
        mock_response = LLMResponse(
            content="Fallback description",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.0005,
            provider="openai"
        )
        mock_openai.complete_with_vision.return_value = mock_response

        mock_gemini_cls.return_value = mock_gemini
        mock_openai_cls.return_value = mock_openai

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_gemini
        analyzer.fallback_provider = mock_openai

        result = analyzer.analyze(image_path="/path/to/image.jpg")

        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.model, "gpt-4o")

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_analyze_both_providers_fail(self, mock_openai_cls, mock_gemini_cls):
        """Test analyze when both providers fail"""
        mock_gemini = MagicMock()
        mock_gemini.complete_with_vision.side_effect = Exception("Gemini error")
        mock_openai = MagicMock()
        mock_openai.complete_with_vision.side_effect = Exception("OpenAI error")

        mock_gemini_cls.return_value = mock_gemini
        mock_openai_cls.return_value = mock_openai

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        analyzer.primary_provider = mock_gemini
        analyzer.fallback_provider = mock_openai

        with self.assertRaises(Exception) as context:
            analyzer.analyze(image_path="/path/to/image.jpg")

        self.assertIn("Both providers failed", str(context.exception))

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_objects_valid_json(self, mock_openai_cls, mock_gemini_cls):
        """Test _extract_objects with valid JSON"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        content = 'Here are the objects:\n[{"label": "dog", "confidence": 0.9}, {"label": "cat", "confidence": 0.85}]'
        objects = analyzer._extract_objects(content)
        self.assertEqual(len(objects), 2)
        self.assertEqual(objects[0].label, "dog")
        self.assertEqual(objects[1].confidence, 0.85)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_objects_invalid_json(self, mock_openai_cls, mock_gemini_cls):
        """Test _extract_objects with invalid JSON"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        content = "No JSON here, just text"
        objects = analyzer._extract_objects(content)
        self.assertEqual(len(objects), 0)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_safety_issues_bullet_list(self, mock_openai_cls, mock_gemini_cls):
        """Test _extract_safety_issues with bullet list"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        content = "Issues:\n- No hard hat\n- Missing gloves\n- Unsafe position"
        issues = analyzer._extract_safety_issues(content)
        self.assertEqual(len(issues), 3)
        self.assertIn("No hard hat", issues)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_safety_issues_numbered_list(self, mock_openai_cls, mock_gemini_cls):
        """Test _extract_safety_issues with numbered list"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        content = "Issues:\n1. No hard hat\n2. Missing gloves"
        issues = analyzer._extract_safety_issues(content)
        self.assertEqual(len(issues), 2)

    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_diagram_elements(self, mock_openai_cls, mock_gemini_cls):
        """Test _extract_diagram_elements"""
        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        content = "Elements:\n- Input\n- Processing\n- Output"
        elements = analyzer._extract_diagram_elements(content)
        self.assertEqual(len(elements), 3)
        self.assertIn("Input", elements)

    @patch("lib.vision_analyzer.subprocess.run")
    @patch("lib.vision_analyzer.os.path.exists")
    @patch("lib.vision_analyzer.os.makedirs")
    @patch("lib.vision_analyzer.os.listdir")
    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_video_frames(self, mock_openai_cls, mock_gemini_cls, mock_listdir, mock_makedirs, mock_exists, mock_run):
        """Test extract_video_frames"""
        mock_exists.return_value = True
        mock_listdir.return_value = ["frame_0001.jpg", "frame_0002.jpg"]
        mock_run.return_value = MagicMock(returncode=0)

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        frames = analyzer.extract_video_frames("/path/to/video.mp4", fps=1.0)

        self.assertEqual(len(frames), 2)
        mock_run.assert_called_once()

    @patch("lib.vision_analyzer.subprocess.run")
    @patch("lib.vision_analyzer.os.path.exists")
    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_video_frames_not_found(self, mock_openai_cls, mock_gemini_cls, mock_exists, mock_run):
        """Test extract_video_frames with non-existent video"""
        mock_exists.return_value = False

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        with self.assertRaises(FileNotFoundError):
            analyzer.extract_video_frames("/path/to/nonexistent.mp4")

    @patch("lib.vision_analyzer.subprocess.run")
    @patch("lib.vision_analyzer.os.makedirs")
    @patch("lib.vision_analyzer.os.path.exists")
    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_video_frames_ffmpeg_error(self, mock_openai_cls, mock_gemini_cls, mock_exists, mock_makedirs, mock_run):
        """Test extract_video_frames with ffmpeg error"""
        mock_exists.return_value = True
        mock_makedirs.return_value = None
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg", stderr="Error")

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        with self.assertRaises(Exception) as context:
            analyzer.extract_video_frames("/path/to/video.mp4")
        self.assertIn("Failed to extract frames", str(context.exception))

    @patch("lib.vision_analyzer.subprocess.run")
    @patch("lib.vision_analyzer.os.makedirs")
    @patch("lib.vision_analyzer.os.path.exists")
    @patch("lib.vision_analyzer.GeminiProvider")
    @patch("lib.vision_analyzer.OpenAIProvider")
    def test_extract_video_frames_ffmpeg_not_found(self, mock_openai_cls, mock_gemini_cls, mock_exists, mock_makedirs, mock_run):
        """Test extract_video_frames with ffmpeg not installed"""
        mock_exists.return_value = True
        mock_makedirs.return_value = None
        mock_run.side_effect = FileNotFoundError()

        analyzer = VisionAnalyzer(config_manager=self.mock_config)
        with self.assertRaises(Exception) as context:
            analyzer.extract_video_frames("/path/to/video.mp4")
        self.assertIn("ffmpeg not found", str(context.exception))


if __name__ == "__main__":
    unittest.main()
