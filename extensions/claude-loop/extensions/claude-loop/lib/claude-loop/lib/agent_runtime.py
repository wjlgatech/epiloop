"""
Lightweight Agent Runtime

Provides minimal agent runtime for non-Claude providers with tool execution capabilities.
Supports OpenAI and Gemini function calling formats with safe tool execution.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.llm_provider import Message, MessageRole, LLMResponse
from lib.llm_config import LLMConfigManager
from lib.providers.openai_provider import OpenAIProvider
from lib.providers.gemini_provider import GeminiProvider
from lib.providers.deepseek_provider import DeepSeekProvider
from lib.providers.litellm_provider import LiteLLMProvider


class ToolExecutionError(Exception):
    """Raised when tool execution fails"""
    pass


class MaxIterationsError(Exception):
    """Raised when maximum iterations exceeded"""
    pass


@dataclass
class ToolCall:
    """Represents a tool call request from the LLM"""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None  # For OpenAI tool call tracking


@dataclass
class ToolResult:
    """Represents the result of tool execution"""
    name: str
    result: Any
    success: bool
    error: Optional[str] = None
    call_id: Optional[str] = None  # For OpenAI tool call tracking


@dataclass
class ExecutionStep:
    """Represents one step in the agent execution trace"""
    iteration: int
    message: str
    tool_calls: List[ToolCall]
    tool_results: List[ToolResult]
    response_content: str
    tokens_in: int
    tokens_out: int
    cost: float


@dataclass
class ExecutionResult:
    """Final result from agent task execution"""
    success: bool
    final_output: str
    iterations: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost: float
    trace: List[ExecutionStep]
    error: Optional[str] = None


class AgentRuntime:
    """
    Lightweight agent runtime for non-Claude providers

    Provides safe tool execution with sandboxing and iteration limits.
    Supports OpenAI and Gemini function calling formats.
    """

    # Tool definitions in OpenAI function calling format
    TOOLS_OPENAI = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to read"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        }
                    },
                    "required": ["file_path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_bash",
                "description": "Execute a bash command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Bash command to execute"
                        }
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "git_command",
                "description": "Execute a git command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "string",
                            "description": "Git command arguments (e.g., 'status', 'add .', 'commit -m \"message\"')"
                        }
                    },
                    "required": ["args"]
                }
            }
        }
    ]

    # Tool definitions in Gemini function calling format
    TOOLS_GEMINI = [
        {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "file_path": {
                        "type": "STRING",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "file_path": {
                        "type": "STRING",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "STRING",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["file_path", "content"]
            }
        },
        {
            "name": "run_bash",
            "description": "Execute a bash command",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "command": {
                        "type": "STRING",
                        "description": "Bash command to execute"
                    }
                },
                "required": ["command"]
            }
        },
        {
            "name": "git_command",
            "description": "Execute a git command",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "args": {
                        "type": "STRING",
                        "description": "Git command arguments (e.g., 'status', 'add .', 'commit -m \"message\"')"
                    }
                },
                "required": ["args"]
            }
        }
    ]

    def __init__(
        self,
        provider_name: str,
        max_iterations: int = 20,
        working_dir: Optional[str] = None,
        sandbox: bool = True
    ):
        """
        Initialize agent runtime

        Args:
            provider_name: Name of LLM provider to use (openai, gemini, deepseek)
            max_iterations: Maximum number of iterations (default: 20)
            working_dir: Working directory for file operations (default: current dir)
            sandbox: Enable sandboxing for tool execution (default: True)
        """
        self.provider_name = provider_name.lower()
        self.max_iterations = max_iterations
        self.working_dir = working_dir or os.getcwd()
        self.sandbox = sandbox

        # Initialize LLM config and provider
        self.config_manager = LLMConfigManager()
        self.provider = self._init_provider()

        # Execution state
        self.trace: List[ExecutionStep] = []
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_cost = 0.0

    def _init_provider(self):
        """Initialize the LLM provider"""
        config = self.config_manager.get_provider(self.provider_name)
        if not config:
            raise ValueError(f"Provider '{self.provider_name}' not configured or disabled")

        # Initialize provider using module-level imports
        if self.provider_name == 'openai':
            return OpenAIProvider(config)
        elif self.provider_name == 'gemini':
            return GeminiProvider(config)
        elif self.provider_name == 'deepseek':
            return DeepSeekProvider(config)
        elif self.provider_name == 'litellm':
            return LiteLLMProvider(config)
        else:
            raise ValueError(f"Unsupported provider: {self.provider_name}")

    def _get_tools_format(self) -> List[Dict[str, Any]]:
        """Get tools in provider-specific format"""
        if self.provider_name == 'gemini':
            return self.TOOLS_GEMINI
        else:  # OpenAI format (also compatible with DeepSeek)
            return self.TOOLS_OPENAI

    def _parse_tool_calls(self, response: LLMResponse) -> List[ToolCall]:
        """
        Parse tool calls from LLM response

        Different providers return tool calls in different formats.
        This method normalizes them to ToolCall objects.
        """
        tool_calls = []

        # Check if response content contains function calls
        # This is a simplified parsing - in reality, providers may use different formats
        content = response.content.strip()

        # Try to parse JSON function calls from content
        # Format: [{"name": "tool_name", "arguments": {...}}]
        if content.startswith('[') and content.endswith(']'):
            try:
                calls_data = json.loads(content)
                for call_data in calls_data:
                    if isinstance(call_data, dict) and 'name' in call_data:
                        tool_calls.append(ToolCall(
                            name=call_data['name'],
                            arguments=call_data.get('arguments', {}),
                            id=call_data.get('id')
                        ))
            except json.JSONDecodeError:
                pass

        # Alternative: Look for tool calls in a structured format
        # Some providers may include tool_calls in extra metadata
        # For now, we'll use the simple JSON array format

        return tool_calls

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call safely

        Args:
            tool_call: Tool call to execute

        Returns:
            ToolResult with execution outcome
        """
        try:
            if tool_call.name == 'read_file':
                result = self._tool_read_file(tool_call.arguments['file_path'])
            elif tool_call.name == 'write_file':
                result = self._tool_write_file(
                    tool_call.arguments['file_path'],
                    tool_call.arguments['content']
                )
            elif tool_call.name == 'run_bash':
                result = self._tool_run_bash(tool_call.arguments['command'])
            elif tool_call.name == 'git_command':
                result = self._tool_git_command(tool_call.arguments['args'])
            else:
                raise ToolExecutionError(f"Unknown tool: {tool_call.name}")

            return ToolResult(
                name=tool_call.name,
                result=result,
                success=True,
                call_id=tool_call.id
            )
        except Exception as e:
            return ToolResult(
                name=tool_call.name,
                result=None,
                success=False,
                error=str(e),
                call_id=tool_call.id
            )

    def _tool_read_file(self, file_path: str) -> str:
        """Read file tool implementation with path traversal protection"""
        # Sandbox: ensure path is within working directory
        if self.sandbox:
            abs_path = os.path.abspath(os.path.join(self.working_dir, file_path))

            # SECURITY: Resolve symlinks to prevent path traversal via symbolic links
            try:
                real_path = os.path.realpath(abs_path)
            except (OSError, ValueError) as e:
                raise ToolExecutionError(f"Invalid file path: {str(e)}")

            real_workdir = os.path.realpath(self.working_dir)
            if not real_path.startswith(real_workdir):
                raise ToolExecutionError(
                    f"Access denied: {file_path} is outside working directory. "
                    f"Resolved path: {real_path}"
                )
            abs_path = real_path
        else:
            abs_path = file_path

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise ToolExecutionError(f"File not found: {file_path}")
        except PermissionError:
            raise ToolExecutionError(f"Permission denied: {file_path}")
        except Exception as e:
            raise ToolExecutionError(f"Failed to read file: {str(e)}")

    def _tool_write_file(self, file_path: str, content: str) -> str:
        """Write file tool implementation with path traversal protection"""
        # Sandbox: ensure path is within working directory
        if self.sandbox:
            abs_path = os.path.abspath(os.path.join(self.working_dir, file_path))

            # SECURITY: Resolve symlinks to prevent path traversal via symbolic links
            # Note: For write, we resolve the parent directory since file may not exist yet
            parent_dir = os.path.dirname(abs_path)
            if os.path.exists(parent_dir):
                try:
                    real_parent = os.path.realpath(parent_dir)
                except (OSError, ValueError) as e:
                    raise ToolExecutionError(f"Invalid parent directory: {str(e)}")

                real_workdir = os.path.realpath(self.working_dir)
                if not real_parent.startswith(real_workdir):
                    raise ToolExecutionError(
                        f"Access denied: {file_path} is outside working directory. "
                        f"Resolved parent: {real_parent}"
                    )
                abs_path = os.path.join(real_parent, os.path.basename(abs_path))
            else:
                # Parent doesn't exist, check if it would be within workdir when created
                real_workdir = os.path.realpath(self.working_dir)
                if not abs_path.startswith(real_workdir):
                    raise ToolExecutionError(
                        f"Access denied: {file_path} is outside working directory"
                    )
        else:
            abs_path = file_path

        try:
            # Create parent directory if it doesn't exist
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {file_path}"
        except PermissionError:
            raise ToolExecutionError(f"Permission denied: {file_path}")
        except Exception as e:
            raise ToolExecutionError(f"Failed to write file: {str(e)}")

    def _tool_run_bash(self, command: str) -> str:
        """Run bash command tool implementation with safe execution"""
        import shlex

        # Parse command safely without shell interpretation
        try:
            args = shlex.split(command)
        except ValueError as e:
            raise ToolExecutionError(f"Invalid command syntax: {e}")

        if not args:
            raise ToolExecutionError("Empty command provided")

        # Sandbox: whitelist allowed commands
        if self.sandbox:
            allowed_commands = {
                'ls', 'cat', 'head', 'tail', 'grep', 'find', 'pwd', 'echo', 'wc',
                'git', 'python3', 'python', 'node', 'npm', 'yarn', 'make', 'curl',
                'jq', 'sed', 'awk', 'sort', 'uniq', 'diff', 'tree', 'file', 'stat',
                'test', 'tr', 'cut', 'basename', 'dirname', 'realpath', 'which'
            }

            command_name = args[0]
            if command_name not in allowed_commands:
                raise ToolExecutionError(
                    f"Command '{command_name}' not allowed. "
                    f"Allowed commands: {', '.join(sorted(allowed_commands))}"
                )

            # Additional safety: block dangerous flags/patterns
            dangerous_patterns = ['rm', 'dd', 'mkfs', '/dev/sd', 'chmod 777', 'sudo', 'su']
            command_str = ' '.join(args)
            for pattern in dangerous_patterns:
                if pattern in command_str:
                    raise ToolExecutionError(f"Dangerous pattern blocked: {pattern}")

        try:
            result = subprocess.run(
                args,
                shell=False,  # SECURITY: Disable shell interpretation to prevent command injection
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"

            return output
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Command timed out after 30 seconds")
        except FileNotFoundError:
            raise ToolExecutionError(f"Command not found: {args[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Failed to execute command: {str(e)}")

    def _tool_git_command(self, args: str) -> str:
        """Git command tool implementation"""
        return self._tool_run_bash(f"git {args}")

    def run(self, task: str, model: Optional[str] = None) -> ExecutionResult:
        """
        Run agent task with iterative tool execution

        Args:
            task: Task description for the agent
            model: Optional model override

        Returns:
            ExecutionResult with trace and final output
        """
        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content="You are a helpful AI assistant with access to tools. "
                        "When you need to use a tool, respond with a JSON array of tool calls: "
                        '[{"name": "tool_name", "arguments": {...}}]. '
                        "When you're done, respond with your final answer in plain text."
            ),
            Message(
                role=MessageRole.USER,
                content=task
            )
        ]

        iteration = 0

        try:
            while iteration < self.max_iterations:
                iteration += 1

                # Call LLM with function calling support
                kwargs = {}
                if self.provider_name == 'openai':
                    kwargs['tools'] = self.TOOLS_OPENAI
                elif self.provider_name == 'gemini':
                    # Gemini uses tools parameter in different format
                    kwargs['tools'] = [{"function_declarations": self.TOOLS_GEMINI}]

                response = self.provider.complete(
                    messages=messages,
                    model=model,
                    temperature=0.7,
                    **kwargs
                )

                # Update token tracking
                self.total_tokens_in += response.usage.input_tokens
                self.total_tokens_out += response.usage.output_tokens
                self.total_cost += response.cost

                # Parse tool calls from response
                tool_calls = self._parse_tool_calls(response)

                # If no tool calls, we're done
                if not tool_calls:
                    step = ExecutionStep(
                        iteration=iteration,
                        message="Final response",
                        tool_calls=[],
                        tool_results=[],
                        response_content=response.content,
                        tokens_in=response.usage.input_tokens,
                        tokens_out=response.usage.output_tokens,
                        cost=response.cost
                    )
                    self.trace.append(step)

                    return ExecutionResult(
                        success=True,
                        final_output=response.content,
                        iterations=iteration,
                        total_tokens_in=self.total_tokens_in,
                        total_tokens_out=self.total_tokens_out,
                        total_cost=self.total_cost,
                        trace=self.trace
                    )

                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    result = self._execute_tool(tool_call)
                    tool_results.append(result)

                # Record step
                step = ExecutionStep(
                    iteration=iteration,
                    message=response.content,
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    response_content=response.content,
                    tokens_in=response.usage.input_tokens,
                    tokens_out=response.usage.output_tokens,
                    cost=response.cost
                )
                self.trace.append(step)

                # Add assistant message and tool results to history
                messages.append(Message(
                    role=MessageRole.ASSISTANT,
                    content=response.content
                ))

                # Add tool results as user messages
                for result in tool_results:
                    if result.success:
                        content = f"Tool '{result.name}' result: {result.result}"
                    else:
                        content = f"Tool '{result.name}' failed: {result.error}"

                    messages.append(Message(
                        role=MessageRole.USER,
                        content=content
                    ))

            # Max iterations exceeded
            raise MaxIterationsError(f"Maximum iterations ({self.max_iterations}) exceeded")

        except MaxIterationsError as e:
            return ExecutionResult(
                success=False,
                final_output="",
                iterations=iteration,
                total_tokens_in=self.total_tokens_in,
                total_tokens_out=self.total_tokens_out,
                total_cost=self.total_cost,
                trace=self.trace,
                error=str(e)
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                final_output="",
                iterations=iteration,
                total_tokens_in=self.total_tokens_in,
                total_tokens_out=self.total_tokens_out,
                total_cost=self.total_cost,
                trace=self.trace,
                error=f"Runtime error: {str(e)}"
            )


def main():
    """CLI interface for agent runtime"""
    import argparse

    parser = argparse.ArgumentParser(description='Lightweight Agent Runtime')
    parser.add_argument('command', choices=['run', 'test', 'providers'],
                       help='Command to execute')
    parser.add_argument('--provider', '-p', default='openai',
                       help='Provider to use (openai, gemini, deepseek)')
    parser.add_argument('--task', '-t', help='Task description for the agent')
    parser.add_argument('--model', '-m', help='Model to use (optional)')
    parser.add_argument('--max-iterations', type=int, default=20,
                       help='Maximum iterations (default: 20)')
    parser.add_argument('--working-dir', '-d', help='Working directory')
    parser.add_argument('--no-sandbox', action='store_true',
                       help='Disable sandboxing (use with caution)')
    parser.add_argument('--json', action='store_true',
                       help='Output result as JSON')

    args = parser.parse_args()

    if args.command == 'providers':
        # List available providers
        config_manager = LLMConfigManager()
        providers = config_manager.list_providers()

        print("Available providers:")
        for provider in providers:
            # Handle both dict and ProviderConfig objects
            if isinstance(provider, dict):
                enabled = provider.get('enabled', False)
                name = provider.get('name', 'unknown')
                model = provider.get('model', provider.get('default_model', 'unknown'))
            else:
                enabled = provider.enabled
                name = provider.name
                model = provider.default_model

            status = "✓" if enabled else "✗"
            print(f"  {status} {name}: {model}")
        return 0

    elif args.command == 'test':
        # Test runtime with simple task
        task = args.task or "What is 2 + 2?"

        runtime = AgentRuntime(
            provider_name=args.provider,
            max_iterations=args.max_iterations,
            working_dir=args.working_dir,
            sandbox=not args.no_sandbox
        )

        print(f"Testing {args.provider} provider...")
        print(f"Task: {task}\n")

        result = runtime.run(task, model=args.model)

        if args.json:
            print(json.dumps({
                'success': result.success,
                'final_output': result.final_output,
                'iterations': result.iterations,
                'total_cost': result.total_cost,
                'error': result.error
            }, indent=2))
        else:
            print(f"Success: {result.success}")
            print(f"Iterations: {result.iterations}")
            print(f"Total cost: ${result.total_cost:.4f}")
            if result.error:
                print(f"Error: {result.error}")
            else:
                print(f"\nFinal output:\n{result.final_output}")

        return 0 if result.success else 1

    elif args.command == 'run':
        if not args.task:
            print("Error: --task is required for 'run' command", file=sys.stderr)
            return 1

        runtime = AgentRuntime(
            provider_name=args.provider,
            max_iterations=args.max_iterations,
            working_dir=args.working_dir,
            sandbox=not args.no_sandbox
        )

        result = runtime.run(args.task, model=args.model)

        if args.json:
            # Output detailed JSON result
            trace_data = []
            for step in result.trace:
                trace_data.append({
                    'iteration': step.iteration,
                    'message': step.message,
                    'tool_calls': [asdict(tc) for tc in step.tool_calls],
                    'tool_results': [asdict(tr) for tr in step.tool_results],
                    'tokens_in': step.tokens_in,
                    'tokens_out': step.tokens_out,
                    'cost': step.cost
                })

            print(json.dumps({
                'success': result.success,
                'final_output': result.final_output,
                'iterations': result.iterations,
                'total_tokens_in': result.total_tokens_in,
                'total_tokens_out': result.total_tokens_out,
                'total_cost': result.total_cost,
                'trace': trace_data,
                'error': result.error
            }, indent=2))
        else:
            print(f"Task: {args.task}")
            print(f"Provider: {args.provider}")
            print(f"\n{'='*60}")

            for step in result.trace:
                print(f"\nIteration {step.iteration}:")
                print(f"Response: {step.response_content[:200]}...")

                if step.tool_calls:
                    print(f"Tool calls:")
                    for tc in step.tool_calls:
                        print(f"  - {tc.name}({json.dumps(tc.arguments)})")

                if step.tool_results:
                    print(f"Tool results:")
                    for tr in step.tool_results:
                        status = "✓" if tr.success else "✗"
                        print(f"  {status} {tr.name}: {str(tr.result or tr.error)[:100]}")

                print(f"Tokens: {step.tokens_in} in, {step.tokens_out} out | Cost: ${step.cost:.4f}")

            print(f"\n{'='*60}")
            print(f"\nSuccess: {result.success}")
            print(f"Total iterations: {result.iterations}")
            print(f"Total tokens: {result.total_tokens_in} in, {result.total_tokens_out} out")
            print(f"Total cost: ${result.total_cost:.4f}")

            if result.error:
                print(f"\nError: {result.error}")
            else:
                print(f"\nFinal output:\n{result.final_output}")

        return 0 if result.success else 1


if __name__ == '__main__':
    sys.exit(main())
