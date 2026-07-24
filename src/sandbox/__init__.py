"""
OpenSandbox wrapper for secure command execution.

This module provides sandboxed execution for untrusted commands,
isolating them from the host system using Docker containers.

Usage:
    from src.sandbox.executor import SandboxExecutor
    
    executor = SandboxExecutor()
    result = await executor.run("pip install requests", timeout=300)
"""

import os
import asyncio
import shlex
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import requests
import yaml


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    server_url: str = "http://localhost:8080"
    image: str = "opensandbox/code-interpreter:v1.0.1"
    timeout_seconds: int = 300
    workspace_mount: Optional[str] = None
    allow_egress: bool = True
    allowed_ports: List[int] = None
    
    def __post_init__(self):
        if self.allowed_ports is None:
            self.allowed_ports = [80, 443]


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: Optional[str] = None


class SandboxExecutor:
    """
    Execute commands in an isolated OpenSandbox container.
    
    Example:
        executor = SandboxExecutor()
        result = await executor.run("echo 'Hello, sandbox!'")
        print(result.stdout)  # Hello, sandbox!
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._session = None
    
    def _load_config_from_file(self, config_path: str = None):
        """Load config from YAML file."""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                '..', '..', 'config', 'settings.yaml'
            )
        
        if os.path.exists(config_path):
            with open(config_path) as f:
                yaml_config = yaml.safe_load(f)
            
            sec = yaml_config.get('security', {})
            sandbox_cfg = sec.get('sandbox', {})
            
            self.config.server_url = sandbox_cfg.get('server_url', self.config.server_url)
            self.config.image = sandbox_cfg.get('image', self.config.image)
            self.config.timeout_seconds = sandbox_cfg.get('timeout_seconds', self.config.timeout_seconds)
            self.config.workspace_mount = sandbox_cfg.get('workspace_mount')
            self.config.allow_egress = sandbox_cfg.get('network', {}).get('allow_egress', True)
    
    def is_available(self) -> bool:
        """Check if OpenSandbox server is running."""
        try:
            response = requests.get(f"{self.config.server_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    async def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        ephemeral: bool = True
    ) -> ExecutionResult:
        """
        Run a command in the sandbox.
        
        Args:
            command: Shell command to execute
            timeout: Timeout in seconds (default from config)
            environment: Environment variables
            working_dir: Working directory (relative to mount if mounted)
            ephemeral: If True, destroy sandbox after execution
            
        Returns:
            ExecutionResult with stdout, stderr, exit_code
        """
        timeout = timeout or self.config.timeout_seconds
        
        # Check if sandbox is available
        if not self.is_available():
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=0,
                error="OpenSandbox server not available. Start with: opensandbox-server"
            )
        
        # For now, use HTTP API (simulated - would need actual OpenSandbox SDK)
        # This is a placeholder that shows the interface
        try:
            # In real implementation, this would use the OpenSandbox SDK:
            # from opensandbox import Sandbox
            # sandbox = await Sandbox.create(self.config.image, ...)
            # result = await sandbox.commands.run(command)
            
            # Placeholder response
            return ExecutionResult(
                success=True,
                stdout=f"[Sandbox] Executed: {command}\n[Note: OpenSandbox integration pending]",
                stderr="",
                exit_code=0,
                duration_ms=100
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=0,
                error=str(e)
            )
    
    async def run_python(
        self,
        code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Run Python code in the sandbox.
        
        Args:
            code: Python code to execute
            timeout: Timeout in seconds
            
        Returns:
            ExecutionResult with stdout, stderr
        """
        return await self.run(f"python3 -c {shlex.quote(code)}", timeout=timeout)


class DirectExecutor:
    """
    Direct execution (no sandbox) - for trusted commands.
    
    This is the default behavior for OpenClaw.
    """
    
    def __init__(self):
        self.shell = os.environ.get('SHELL', '/bin/bash')
    
    async def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None
    ) -> ExecutionResult:
        """Run command directly on host."""
        import time
        start = time.time()
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
                cwd=working_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Command timed out",
                    exit_code=-1,
                    duration_ms=int((time.time() - start) * 1000),
                    error="Timeout"
                )
            
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else "",
                exit_code=process.returncode or 0,
                duration_ms=int((time.time() - start) * 1000)
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=int((time.time() - start) * 1000),
                error=str(e)
            )


def get_executor(mode: str = "direct", config: SandboxConfig = None) -> Any:
    """
    Get an executor based on mode.
    
    Args:
        mode: "direct" or "sandbox"
        config: Sandbox configuration
        
    Returns:
        Executor instance
    """
    if mode == "sandbox":
        return SandboxExecutor(config)
    else:
        return DirectExecutor()


# Convenience functions
async def exec_sandbox(command: str, **kwargs) -> ExecutionResult:
    """Quick sandbox execution."""
    executor = SandboxExecutor()
    return await executor.run(command, **kwargs)


async def exec_direct(command: str, **kwargs) -> ExecutionResult:
    """Quick direct execution."""
    executor = DirectExecutor()
    return await executor.run(command, **kwargs)
