"""Log destination implementations for different output targets."""

import json
import sys
import asyncio
from typing import Dict, Any, List, Optional
from ...application.interfaces.logging import ILogDestination


class ConsoleDestination(ILogDestination):
    """Console log destination implementation."""
    
    def __init__(self, use_stderr: bool = False):
        """
        Initialize console destination.
        
        Args:
            use_stderr: Whether to write to stderr instead of stdout
        """
        self._output = sys.stderr if use_stderr else sys.stdout
        self._use_stderr = use_stderr
    
    async def write_log(self, log_entry: Dict[str, Any]) -> bool:
        """Write a log entry to console."""
        try:
            if isinstance(log_entry, dict):
                # Format as JSON for structured output
                output = json.dumps(log_entry, default=str, ensure_ascii=False)
            else:
                output = str(log_entry)
            
            print(output, file=self._output)
            self._output.flush()
            return True
        except Exception:
            return False
    
    async def write_batch(self, log_entries: List[Dict[str, Any]]) -> int:
        """Write multiple log entries to console."""
        successful_writes = 0
        
        for entry in log_entries:
            if await self.write_log(entry):
                successful_writes += 1
        
        return successful_writes
    
    async def flush(self) -> bool:
        """Flush console output."""
        try:
            self._output.flush()
            return True
        except Exception:
            return False
    
    @property
    def destination_name(self) -> str:
        """Get the name of the log destination."""
        return "console_stderr" if self._use_stderr else "console_stdout"
    
    @property
    def is_available(self) -> bool:
        """Check if the destination is available."""
        return True  # Console is always available


class CloudWatchDestination(ILogDestination):
    """CloudWatch log destination implementation."""
    
    def __init__(self, log_group: str, log_stream: Optional[str] = None,
                 region: str = 'us-east-1'):
        """
        Initialize CloudWatch destination.
        
        Args:
            log_group: CloudWatch log group name
            log_stream: CloudWatch log stream name
            region: AWS region
        """
        self._log_group = log_group
        self._log_stream = log_stream
        self._region = region
        self._client = None
        self._sequence_token = None
        self._batch_buffer: List[Dict[str, Any]] = []
        self._max_batch_size = 10000  # CloudWatch limit
    
    async def _get_client(self):
        """Get or create CloudWatch Logs client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('logs', region_name=self._region)
            except ImportError:
                raise RuntimeError("boto3 is required for CloudWatch logging")
        return self._client
    
    async def _ensure_log_stream(self) -> bool:
        """Ensure log stream exists."""
        if not self._log_stream:
            import time
            self._log_stream = f"stream-{int(time.time())}"
        
        try:
            client = await self._get_client()
            
            # Try to create log stream (will fail if it already exists)
            try:
                client.create_log_stream(
                    logGroupName=self._log_group,
                    logStreamName=self._log_stream
                )
            except client.exceptions.ResourceAlreadyExistsException:
                pass  # Stream already exists
            
            return True
        except Exception:
            return False
    
    async def write_log(self, log_entry: Dict[str, Any]) -> bool:
        """Write a log entry to CloudWatch."""
        return await self.write_batch([log_entry]) == 1
    
    async def write_batch(self, log_entries: List[Dict[str, Any]]) -> int:
        """Write multiple log entries to CloudWatch."""
        if not log_entries:
            return 0
        
        try:
            if not await self._ensure_log_stream():
                return 0
            
            client = await self._get_client()
            
            # Prepare log events for CloudWatch
            events = []
            for entry in log_entries:
                if isinstance(entry, dict):
                    message = json.dumps(entry, default=str, ensure_ascii=False)
                else:
                    message = str(entry)
                
                events.append({
                    'timestamp': int(entry.get('timestamp', 0) * 1000) if 'timestamp' in entry else int(asyncio.get_event_loop().time() * 1000),
                    'message': message
                })
            
            # Sort events by timestamp (CloudWatch requirement)
            events.sort(key=lambda x: x['timestamp'])
            
            # Send to CloudWatch
            put_args = {
                'logGroupName': self._log_group,
                'logStreamName': self._log_stream,
                'logEvents': events
            }
            
            if self._sequence_token:
                put_args['sequenceToken'] = self._sequence_token
            
            response = client.put_log_events(**put_args)
            self._sequence_token = response.get('nextSequenceToken')
            
            return len(log_entries)
        
        except Exception:
            return 0
    
    async def flush(self) -> bool:
        """Flush any buffered log entries."""
        if self._batch_buffer:
            written = await self.write_batch(self._batch_buffer)
            success = written == len(self._batch_buffer)
            self._batch_buffer.clear()
            return success
        return True
    
    @property
    def destination_name(self) -> str:
        """Get the name of the log destination."""
        return f"cloudwatch_{self._log_group}_{self._log_stream}"
    
    @property
    def is_available(self) -> bool:
        """Check if CloudWatch is available."""
        try:
            import boto3
            return True
        except ImportError:
            return False
    
    def add_to_buffer(self, log_entry: Dict[str, Any]) -> None:
        """Add log entry to buffer for batch processing."""
        self._batch_buffer.append(log_entry)
        
        # Auto-flush if buffer is getting large
        if len(self._batch_buffer) >= self._max_batch_size:
            asyncio.create_task(self.flush())


class FileDestination(ILogDestination):
    """File log destination implementation."""
    
    def __init__(self, file_path: str, max_file_size: int = 10 * 1024 * 1024,
                 backup_count: int = 5):
        """
        Initialize file destination.
        
        Args:
            file_path: Path to log file
            max_file_size: Maximum file size before rotation
            backup_count: Number of backup files to keep
        """
        self._file_path = file_path
        self._max_file_size = max_file_size
        self._backup_count = backup_count
        self._current_size = 0
    
    async def write_log(self, log_entry: Dict[str, Any]) -> bool:
        """Write a log entry to file."""
        try:
            if isinstance(log_entry, dict):
                output = json.dumps(log_entry, default=str, ensure_ascii=False) + '\n'
            else:
                output = str(log_entry) + '\n'
            
            # Check if rotation is needed
            if self._current_size + len(output.encode('utf-8')) > self._max_file_size:
                await self._rotate_file()
            
            with open(self._file_path, 'a', encoding='utf-8') as f:
                f.write(output)
                f.flush()
            
            self._current_size += len(output.encode('utf-8'))
            return True
        except Exception:
            return False
    
    async def write_batch(self, log_entries: List[Dict[str, Any]]) -> int:
        """Write multiple log entries to file."""
        successful_writes = 0
        
        for entry in log_entries:
            if await self.write_log(entry):
                successful_writes += 1
        
        return successful_writes
    
    async def flush(self) -> bool:
        """Flush file output."""
        # File writes are already flushed in write_log
        return True
    
    async def _rotate_file(self) -> None:
        """Rotate log file when it gets too large."""
        import os
        import shutil
        
        try:
            # Move existing backups
            for i in range(self._backup_count - 1, 0, -1):
                old_file = f"{self._file_path}.{i}"
                new_file = f"{self._file_path}.{i + 1}"
                if os.path.exists(old_file):
                    shutil.move(old_file, new_file)
            
            # Move current file to .1
            if os.path.exists(self._file_path):
                shutil.move(self._file_path, f"{self._file_path}.1")
            
            self._current_size = 0
        except Exception:
            pass  # Continue even if rotation fails
    
    @property
    def destination_name(self) -> str:
        """Get the name of the log destination."""
        return f"file_{self._file_path}"
    
    @property
    def is_available(self) -> bool:
        """Check if file destination is available."""
        import os
        try:
            # Check if directory exists and is writable
            directory = os.path.dirname(self._file_path)
            return os.path.exists(directory) and os.access(directory, os.W_OK)
        except Exception:
            return False