"""
Unit tests for Lightweight Agent Runtime
"""

import unittest
import sys
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.agent_runtime import (
    AgentRuntime,
    ToolCall,
    ToolResult,
    ExecutionStep,
    ExecutionResult,
    ToolExecutionError,
    MaxIterationsError
)
from lib.llm_provider import Message, MessageRole, LLMResponse, TokenUsage


class TestToolCall(unittest.TestCase):
    """Test ToolCall dataclass"""

    def test_tool_call_creation(self):
        """Test creating a ToolCall"""
        call = ToolCall(
            name='read_file',
            arguments={'file_path': 'test.txt'},
            id='call_123'
        )

        self.assertEqual(call.name, 'read_file')
        self.assertEqual(call.arguments, {'file_path': 'test.txt'})
        self.assertEqual(call.id, 'call_123')

    def test_tool_call_without_id(self):
        """Test ToolCall without id field"""
        call = ToolCall(
            name='write_file',
            arguments={'file_path': 'test.txt', 'content': 'hello'}
        )

        self.assertEqual(call.name, 'write_file')
        self.assertIsNone(call.id)


class TestToolResult(unittest.TestCase):
    """Test ToolResult dataclass"""

    def test_successful_result(self):
        """Test successful tool result"""
        result = ToolResult(
            name='read_file',
            result='file contents',
            success=True,
            call_id='call_123'
        )

        self.assertEqual(result.name, 'read_file')
        self.assertEqual(result.result, 'file contents')
        self.assertTrue(result.success)
        self.assertIsNone(result.error)

    def test_failed_result(self):
        """Test failed tool result"""
        result = ToolResult(
            name='read_file',
            result=None,
            success=False,
            error='File not found',
            call_id='call_123'
        )

        self.assertEqual(result.name, 'read_file')
        self.assertIsNone(result.result)
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'File not found')


class TestAgentRuntimeInit(unittest.TestCase):
    """Test AgentRuntime initialization"""

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('lib.agent_runtime.OpenAIProvider')
    def test_init_with_openai(self, mock_openai_provider, mock_config_manager):
        """Test initialization with OpenAI provider"""
        mock_config = Mock()
        mock_config.name = 'openai'
        mock_config_manager.return_value.get_provider.return_value = mock_config

        runtime = AgentRuntime(provider_name='openai')

        self.assertEqual(runtime.provider_name, 'openai')
        self.assertEqual(runtime.max_iterations, 20)
        self.assertTrue(runtime.sandbox)

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('lib.agent_runtime.GeminiProvider')
    def test_init_with_gemini(self, mock_gemini_provider, mock_config_manager):
        """Test initialization with Gemini provider"""
        mock_config = Mock()
        mock_config.name = 'gemini'
        mock_config_manager.return_value.get_provider.return_value = mock_config

        runtime = AgentRuntime(provider_name='gemini')

        self.assertEqual(runtime.provider_name, 'gemini')

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('lib.agent_runtime.OpenAIProvider')
    def test_init_with_custom_settings(self, mock_openai_provider, mock_config_manager):
        """Test initialization with custom settings"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        runtime = AgentRuntime(
            provider_name='openai',
            max_iterations=10,
            working_dir='/tmp',
            sandbox=False
        )

        self.assertEqual(runtime.max_iterations, 10)
        self.assertEqual(runtime.working_dir, '/tmp')
        self.assertFalse(runtime.sandbox)

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_init_unsupported_provider(self, mock_config_manager):
        """Test initialization with unsupported provider"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with self.assertRaises(ValueError) as ctx:
            runtime = AgentRuntime(provider_name='unsupported')

        self.assertIn('Unsupported provider', str(ctx.exception))

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_init_provider_not_configured(self, mock_config_manager):
        """Test initialization when provider not configured"""
        mock_config_manager.return_value.get_provider.return_value = None

        with self.assertRaises(ValueError) as ctx:
            runtime = AgentRuntime(provider_name='openai')

        self.assertIn('not configured', str(ctx.exception))


class TestToolsFormat(unittest.TestCase):
    """Test tool format methods"""

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('lib.agent_runtime.OpenAIProvider')
    def test_get_tools_openai_format(self, mock_openai_provider, mock_config_manager):
        """Test getting tools in OpenAI format"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        runtime = AgentRuntime(provider_name='openai')
        tools = runtime._get_tools_format()

        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        self.assertEqual(tools[0]['type'], 'function')
        self.assertIn('function', tools[0])

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('lib.agent_runtime.GeminiProvider')
    def test_get_tools_gemini_format(self, mock_gemini_provider, mock_config_manager):
        """Test getting tools in Gemini format"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        runtime = AgentRuntime(provider_name='gemini')
        tools = runtime._get_tools_format()

        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        self.assertIn('name', tools[0])
        self.assertIn('parameters', tools[0])


class TestToolExecution(unittest.TestCase):
    """Test individual tool execution"""

    def setUp(self):
        """Create temp directory for tests"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directory"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_read_file_success(self, mock_config_manager):
        """Test successful file read"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir
            )

            # Create test file
            test_file = os.path.join(self.test_dir, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('Hello, world!')

            # Execute read
            result = runtime._tool_read_file('test.txt')
            self.assertEqual(result, 'Hello, world!')

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_read_file_not_found(self, mock_config_manager):
        """Test reading non-existent file"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir
            )

            with self.assertRaises(ToolExecutionError):
                runtime._tool_read_file('nonexistent.txt')

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_read_file_sandbox_violation(self, mock_config_manager):
        """Test sandbox prevents reading outside working dir"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir,
                sandbox=True
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                runtime._tool_read_file('/etc/passwd')

            self.assertIn('Access denied', str(ctx.exception))

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_write_file_success(self, mock_config_manager):
        """Test successful file write"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir
            )

            result = runtime._tool_write_file('output.txt', 'test content')
            self.assertIn('Successfully wrote', result)

            # Verify file was written
            with open(os.path.join(self.test_dir, 'output.txt'), 'r') as f:
                self.assertEqual(f.read(), 'test content')

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_write_file_creates_directory(self, mock_config_manager):
        """Test write file creates parent directory"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir
            )

            runtime._tool_write_file('subdir/output.txt', 'test')

            # Verify file was written
            with open(os.path.join(self.test_dir, 'subdir', 'output.txt'), 'r') as f:
                self.assertEqual(f.read(), 'test')

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_write_file_sandbox_violation(self, mock_config_manager):
        """Test sandbox prevents writing outside working dir"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir,
                sandbox=True
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                runtime._tool_write_file('/tmp/evil.txt', 'malicious')

            self.assertIn('Access denied', str(ctx.exception))

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('subprocess.run')
    def test_run_bash_success(self, mock_run, mock_config_manager):
        """Test successful bash command execution"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        mock_run.return_value = Mock(
            stdout='command output',
            stderr='',
            returncode=0
        )

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(provider_name='openai')

            result = runtime._tool_run_bash('echo hello')
            self.assertEqual(result, 'command output')

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_run_bash_dangerous_command_blocked(self, mock_config_manager):
        """Test dangerous command is blocked by sandbox"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                sandbox=True
            )

            with self.assertRaises(ToolExecutionError) as ctx:
                runtime._tool_run_bash('rm -rf /')

            self.assertIn('Dangerous command blocked', str(ctx.exception))

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('subprocess.run')
    def test_run_bash_timeout(self, mock_run, mock_config_manager):
        """Test bash command timeout"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 30)

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(provider_name='openai')

            with self.assertRaises(ToolExecutionError) as ctx:
                runtime._tool_run_bash('sleep 100')

            self.assertIn('timed out', str(ctx.exception))

    @patch('lib.agent_runtime.LLMConfigManager')
    @patch('subprocess.run')
    def test_git_command(self, mock_run, mock_config_manager):
        """Test git command execution"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        mock_run.return_value = Mock(
            stdout='On branch main',
            stderr='',
            returncode=0
        )

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(provider_name='openai')

            result = runtime._tool_git_command('status')
            self.assertIn('On branch main', result)

            # Verify git command was prepended
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            self.assertTrue(call_args[0][0].startswith('git '))


class TestParseToolCalls(unittest.TestCase):
    """Test parsing tool calls from LLM responses"""

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_parse_json_tool_calls(self, mock_config_manager):
        """Test parsing JSON array of tool calls"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(provider_name='openai')

            response = LLMResponse(
                content='[{"name": "read_file", "arguments": {"file_path": "test.txt"}, "id": "call_1"}]',
                model='gpt-4o',
                usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
                cost=0.01,
                provider='openai'
            )

            tool_calls = runtime._parse_tool_calls(response)

            self.assertEqual(len(tool_calls), 1)
            self.assertEqual(tool_calls[0].name, 'read_file')
            self.assertEqual(tool_calls[0].arguments['file_path'], 'test.txt')
            self.assertEqual(tool_calls[0].id, 'call_1')

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_parse_no_tool_calls(self, mock_config_manager):
        """Test parsing response with no tool calls"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(provider_name='openai')

            response = LLMResponse(
                content='This is a plain text response',
                model='gpt-4o',
                usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
                cost=0.01,
                provider='openai'
            )

            tool_calls = runtime._parse_tool_calls(response)
            self.assertEqual(len(tool_calls), 0)


class TestExecuteToolCall(unittest.TestCase):
    """Test executing tool calls"""

    def setUp(self):
        """Create temp directory for tests"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directory"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_execute_read_file_success(self, mock_config_manager):
        """Test executing read_file tool call"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir
            )

            # Create test file
            with open(os.path.join(self.test_dir, 'test.txt'), 'w') as f:
                f.write('content')

            tool_call = ToolCall(
                name='read_file',
                arguments={'file_path': 'test.txt'}
            )

            result = runtime._execute_tool(tool_call)

            self.assertTrue(result.success)
            self.assertEqual(result.result, 'content')
            self.assertIsNone(result.error)

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_execute_tool_failure(self, mock_config_manager):
        """Test executing tool call that fails"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(
                provider_name='openai',
                working_dir=self.test_dir
            )

            tool_call = ToolCall(
                name='read_file',
                arguments={'file_path': 'nonexistent.txt'}
            )

            result = runtime._execute_tool(tool_call)

            self.assertFalse(result.success)
            self.assertIsNone(result.result)
            self.assertIsNotNone(result.error)

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_execute_unknown_tool(self, mock_config_manager):
        """Test executing unknown tool"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        with patch('lib.agent_runtime.OpenAIProvider'):
            runtime = AgentRuntime(provider_name='openai')

            tool_call = ToolCall(
                name='unknown_tool',
                arguments={}
            )

            result = runtime._execute_tool(tool_call)

            self.assertFalse(result.success)
            self.assertIn('Unknown tool', result.error)


class TestAgentRun(unittest.TestCase):
    """Test full agent execution"""

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_run_simple_task_no_tools(self, mock_config_manager):
        """Test running simple task that doesn't need tools"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        mock_provider = Mock()
        mock_provider.complete.return_value = LLMResponse(
            content='The answer is 4',
            model='gpt-4o',
            usage=TokenUsage(input_tokens=100, output_tokens=20, total_tokens=120),
            cost=0.01,
            provider='openai'
        )

        with patch('lib.agent_runtime.OpenAIProvider', return_value=mock_provider):
            runtime = AgentRuntime(provider_name='openai')
            result = runtime.run('What is 2+2?')

            self.assertTrue(result.success)
            self.assertEqual(result.final_output, 'The answer is 4')
            self.assertEqual(result.iterations, 1)
            self.assertIsNone(result.error)

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_run_with_tool_calls(self, mock_config_manager):
        """Test running task with tool calls"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        # First call: request tool call
        response1 = LLMResponse(
            content='[{"name": "run_bash", "arguments": {"command": "echo test"}}]',
            model='gpt-4o',
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.01,
            provider='openai'
        )

        # Second call: final response
        response2 = LLMResponse(
            content='The command output is: test',
            model='gpt-4o',
            usage=TokenUsage(input_tokens=120, output_tokens=30, total_tokens=150),
            cost=0.01,
            provider='openai'
        )

        mock_provider = Mock()
        mock_provider.complete.side_effect = [response1, response2]

        with patch('lib.agent_runtime.OpenAIProvider', return_value=mock_provider):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(
                    stdout='test',
                    stderr='',
                    returncode=0
                )

                runtime = AgentRuntime(provider_name='openai')
                result = runtime.run('Run echo test command')

                self.assertTrue(result.success)
                self.assertEqual(result.iterations, 2)
                self.assertEqual(len(result.trace), 2)

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_run_max_iterations_exceeded(self, mock_config_manager):
        """Test that max iterations limit is enforced"""
        mock_config = Mock()
        mock_config_manager.return_value.get_provider.return_value = mock_config

        # Always return tool calls (infinite loop)
        mock_response = LLMResponse(
            content='[{"name": "run_bash", "arguments": {"command": "echo test"}}]',
            model='gpt-4o',
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            cost=0.01,
            provider='openai'
        )

        mock_provider = Mock()
        mock_provider.complete.return_value = mock_response

        with patch('lib.agent_runtime.OpenAIProvider', return_value=mock_provider):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(stdout='test', stderr='', returncode=0)

                runtime = AgentRuntime(provider_name='openai', max_iterations=3)
                result = runtime.run('Infinite loop task')

                self.assertFalse(result.success)
                self.assertEqual(result.iterations, 3)
                self.assertIn('Maximum iterations', result.error)


class TestCLI(unittest.TestCase):
    """Test CLI interface"""

    @patch('lib.agent_runtime.LLMConfigManager')
    def test_providers_command(self, mock_config_manager):
        """Test providers command"""
        mock_config_manager.return_value.list_providers.return_value = [
            {'name': 'openai', 'enabled': True, 'model': 'gpt-4o'},
            {'name': 'gemini', 'enabled': False, 'model': 'gemini-2.0-flash'}
        ]

        from lib.agent_runtime import main
        with patch('sys.argv', ['agent_runtime.py', 'providers']):
            exit_code = main()

        self.assertEqual(exit_code, 0)


if __name__ == '__main__':
    unittest.main()
