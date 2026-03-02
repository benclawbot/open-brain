"""
Docker-based sandbox for secure command execution.

This module provides sandboxed execution by running commands in isolated
Docker containers, without needing the full OpenSandbox server.

Usage:
    from src.sandbox.docker_sandbox import DockerSandbox
    
    sandbox = DockerSandbox()
    result = await sandbox.run("echo hello")
"""

import asyncio
import json
import uuid
from datetime import timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import subprocess


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: Optional[str] = None


class DockerSandbox:
    """
    Execute commands in an isolated Docker container.
    
    This is a simpler alternative to OpenSandbox that doesn't require
    a separate server - it directly uses Docker CLI.
    
    Features:
    - Ephemeral containers (destroyed after execution)
    - No network access (--network=none)
    - Resource limits (CPU, memory)
    - Time limits
    
    Example:
        sandbox = DockerSandbox()
        result = await sandbox.run("pip install requests")
        print(result.stdout)
    """
    
    def __init__(
        self,
        image: str = "python:3.11-slim",
        timeout: int = 300,
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
    ):
        self.image = image
        self.timeout = timeout
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self._container_id: Optional[str] = None
    
    def _ensure_image(self) -> bool:
        """Pull image if needed."""
        try:
            result = subprocess.run(
                ["docker", "pull", self.image],
                capture_output=True,
                timeout=60
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Run a command in an ephemeral Docker container.
        
        Args:
            command: Shell command to execute
            timeout: Timeout in seconds (default from config)
            environment: Environment variables
            working_dir: Working directory
            
        Returns:
            ExecutionResult with stdout, stderr, exit_code
        """
        import time
        start = time.time()
        
        timeout = timeout or self.timeout
        
        # Ensure image exists
        if not self._ensure_image():
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=0,
                error=f"Failed to pull image: {self.image}"
            )
        
        # Build docker run command
        container_name = f"sandbox-{uuid.uuid4().hex[:8]}"
        
        cmd = [
            "docker", "run",
            "--rm",                           # Remove after exit
            "--name", container_name,
            "--network", "none",              # No network
            "--memory", self.memory_limit,
            "--cpus", str(self.cpu_limit),
            "--pids-limit", "100",           # Limit processes
            "--read-only",                    # Read-only filesystem (except /tmp)
            "--tmpfs", "/tmp:rw,size=64m",   # Writable /tmp
        ]
        
        # Add environment variables
        if environment:
            for key, value in environment.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        # Add working directory
        if working_dir:
            cmd.extend(["-w", working_dir])
        
        # Add image and command
        cmd.extend([self.image, "sh", "-c", command])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            duration_ms = int((time.time() - start) * 1000)
            
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_ms=duration_ms
            )
            
        except subprocess.TimeoutExpired:
            # Kill the container if still running
            subprocess.run(["docker", "kill", container_name], 
                         capture_output=True)
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Command timed out",
                exit_code=-1,
                duration_ms=int((time.time() - start) * 1000),
                error="Timeout"
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
    
    async def run_python(
        self,
        code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """Run Python code in the sandbox."""
        return await self.run(f"python3 -c '{code.replace(\"'\", \"'\\\\\")\")}'", timeout=timeout)
    
    def is_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False


class DockerSandboxPool:
    """
    Pool of pre-warmed Docker sandbox containers.
    
    For better performance, keeps containers running and reuses them.
    """
    
    def __init__(
        self,
        image: str = "python:3.11-slim",
        pool_size: int = 3,
        timeout: int = 300,
    ):
        self.image = image
        self.pool_size = pool_size
        self.timeout = timeout
        self._containers: List[str] = []
    
    async def initialize(self):
        """Pre-warm the pool by starting containers."""
        for i in range(self.pool_size):
            container_name = f"sandbox-pool-{i}-{uuid.uuid4().hex[:4]}"
            try:
                subprocess.run([
                    "docker", "run", "-d",
                    "--name", container_name,
                    "--network", "none",
                    "--memory", "512m",
                    "--cpus", "1.0",
                    "--read-only",
                    "--tmpfs", "/tmp:rw,size=64m",
                    self.image,
                    "sleep", "infinity"
                ], capture_output=True, timeout=30)
                self._containers.append(container_name)
            except Exception:
                pass
    
    async def execute(self, command: str) -> ExecutionResult:
        """Execute command in a pooled container."""
        if not self._containers:
            # Fall back to single-shot
            sandbox = DockerSandbox(self.image, self.timeout)
            return await sandbox.run(command)
        
        # Use first available container
        container = self._containers[0]
        
        try:
            result = subprocess.run([
                "docker", "exec", container,
                "sh", "-c", command
            ], capture_output=True, text=True, timeout=self.timeout)
            
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_ms=0
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=0,
                error=str(e)
            )
    
    async def cleanup(self):
        """Stop and remove all pooled containers."""
        for container in self._containers:
            subprocess.run(["docker", "kill", container], capture_output=True)
            subprocess.run(["docker", "rm", container], capture_output=True)
        self._containers = []


# Convenience function
async def exec_docker(command: str, **kwargs) -> ExecutionResult:
    """Quick Docker sandbox execution."""
    sandbox = DockerSandbox()
    return await sandbox.run(command, **kwargs)
