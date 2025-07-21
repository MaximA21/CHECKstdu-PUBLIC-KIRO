"""Mock messaging implementations for testing purposes."""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import uuid
import asyncio
from copy import deepcopy
from collections import defaultdict, deque

from ...application.interfaces.messaging import (
    IMessageQueue, 
    IWorkflowOrchestrator, 
    IEventBus,
    MessagePriority, 
    WorkflowStatus
)


class MockMessageQueue(IMessageQueue):
    """Mock implementation of message queue for testing."""
    
    def __init__(self):
        """Initialize with in-memory queues."""
        self._queues: Dict[str, deque] = defaultdict(deque)
        self._message_metadata: Dict[str, Dict[str, Any]] = {}
        self._queue_attributes: Dict[str, Dict[str, Any]] = defaultdict(dict)
    
    async def send_message(self, queue_name: str, message: Dict[str, Any], 
                          priority: MessagePriority = MessagePriority.NORMAL,
                          delay_seconds: int = 0) -> str:
        """Send a message to a queue."""
        message_id = str(uuid.uuid4())
        
        # Create message envelope
        envelope = {
            "message_id": message_id,
            "body": deepcopy(message),
            "priority": priority,
            "sent_at": datetime.utcnow(),
            "available_at": datetime.utcnow() + timedelta(seconds=delay_seconds),
            "receipt_handle": f"receipt_{message_id}",
            "receive_count": 0
        }
        
        # Store message metadata
        self._message_metadata[message_id] = envelope
        
        # Add to queue based on priority
        if priority == MessagePriority.URGENT:
            self._queues[queue_name].appendleft(envelope)
        else:
            self._queues[queue_name].append(envelope)
        
        # Update queue attributes
        self._update_queue_attributes(queue_name)
        
        return message_id
    
    async def receive_messages(self, queue_name: str, max_messages: int = 10,
                              wait_time_seconds: int = 20) -> List[Dict[str, Any]]:
        """Receive messages from a queue."""
        if queue_name not in self._queues:
            return []
        
        messages = []
        now = datetime.utcnow()
        
        # Get available messages (not delayed)
        available_messages = []
        while self._queues[queue_name] and len(available_messages) < max_messages:
            envelope = self._queues[queue_name].popleft()
            
            if envelope["available_at"] <= now:
                envelope["receive_count"] += 1
                envelope["received_at"] = now
                available_messages.append(envelope)
            else:
                # Put back delayed message
                self._queues[queue_name].appendleft(envelope)
                break
        
        # Format messages for return
        for envelope in available_messages:
            messages.append({
                "message_id": envelope["message_id"],
                "receipt_handle": envelope["receipt_handle"],
                "body": envelope["body"],
                "attributes": {
                    "sent_timestamp": envelope["sent_at"].isoformat(),
                    "receive_count": envelope["receive_count"],
                    "priority": envelope["priority"].value
                }
            })
        
        # Update queue attributes
        self._update_queue_attributes(queue_name)
        
        return messages
    
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """Delete a message from the queue."""
        # Find and remove message by receipt handle
        message_id = receipt_handle.replace("receipt_", "")
        
        if message_id in self._message_metadata:
            del self._message_metadata[message_id]
            self._update_queue_attributes(queue_name)
            return True
        
        return False
    
    async def get_queue_attributes(self, queue_name: str) -> Dict[str, Any]:
        """Get queue attributes and statistics."""
        return deepcopy(self._queue_attributes.get(queue_name, {}))
    
    async def purge_queue(self, queue_name: str) -> bool:
        """Purge all messages from a queue."""
        if queue_name in self._queues:
            # Remove message metadata for this queue
            queue_messages = list(self._queues[queue_name])
            for envelope in queue_messages:
                message_id = envelope["message_id"]
                if message_id in self._message_metadata:
                    del self._message_metadata[message_id]
            
            # Clear the queue
            self._queues[queue_name].clear()
            self._update_queue_attributes(queue_name)
            return True
        
        return False
    
    def _update_queue_attributes(self, queue_name: str) -> None:
        """Update queue attributes for statistics."""
        queue = self._queues[queue_name]
        now = datetime.utcnow()
        
        # Count available vs delayed messages
        available_count = sum(1 for msg in queue if msg["available_at"] <= now)
        delayed_count = len(queue) - available_count
        
        self._queue_attributes[queue_name] = {
            "approximate_number_of_messages": len(queue),
            "approximate_number_of_messages_delayed": delayed_count,
            "approximate_number_of_messages_not_visible": delayed_count,
            "created_timestamp": now.isoformat(),
            "last_modified_timestamp": now.isoformat()
        }
    
    def clear_all_queues(self) -> None:
        """Clear all queues (for testing)."""
        self._queues.clear()
        self._message_metadata.clear()
        self._queue_attributes.clear()
    
    def get_queue_names(self) -> List[str]:
        """Get all queue names (for testing)."""
        return list(self._queues.keys())


class MockWorkflowOrchestrator(IWorkflowOrchestrator):
    """Mock implementation of workflow orchestrator for testing."""
    
    def __init__(self):
        """Initialize with in-memory workflow storage."""
        self._executions: Dict[str, Dict[str, Any]] = {}
        self._workflow_definitions: Dict[str, Dict[str, Any]] = {}
    
    async def start_workflow(self, workflow_name: str, input_data: Dict[str, Any],
                            execution_name: Optional[str] = None) -> str:
        """Start a workflow execution."""
        execution_id = f"exec_{uuid.uuid4()}"
        
        if execution_name:
            execution_id = f"{execution_name}_{uuid.uuid4().hex[:8]}"
        
        execution = {
            "execution_id": execution_id,
            "workflow_name": workflow_name,
            "status": WorkflowStatus.RUNNING,
            "input": deepcopy(input_data),
            "output": None,
            "started_at": datetime.utcnow(),
            "ended_at": None,
            "error": None,
            "steps_completed": 0,
            "total_steps": 3  # Mock workflow with 3 steps
        }
        
        self._executions[execution_id] = execution
        
        # Simulate workflow execution in background
        asyncio.create_task(self._simulate_workflow_execution(execution_id))
        
        return execution_id
    
    async def get_workflow_status(self, execution_id: str) -> WorkflowStatus:
        """Get the status of a workflow execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            raise ValueError(f"Workflow execution {execution_id} not found")
        
        return execution["status"]
    
    async def get_workflow_output(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get the output of a completed workflow execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            return None
        
        if execution["status"] == WorkflowStatus.SUCCEEDED:
            return deepcopy(execution["output"])
        
        return None
    
    async def stop_workflow(self, execution_id: str, reason: str = "User requested") -> bool:
        """Stop a running workflow execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            return False
        
        if execution["status"] == WorkflowStatus.RUNNING:
            execution["status"] = WorkflowStatus.ABORTED
            execution["ended_at"] = datetime.utcnow()
            execution["error"] = reason
            return True
        
        return False
    
    async def list_workflow_executions(self, workflow_name: str, 
                                      status_filter: Optional[WorkflowStatus] = None,
                                      max_results: int = 100) -> List[Dict[str, Any]]:
        """List workflow executions for a given workflow."""
        executions = []
        
        for execution in self._executions.values():
            if execution["workflow_name"] != workflow_name:
                continue
            
            if status_filter and execution["status"] != status_filter:
                continue
            
            summary = {
                "execution_id": execution["execution_id"],
                "workflow_name": execution["workflow_name"],
                "status": execution["status"].value,
                "started_at": execution["started_at"].isoformat(),
                "ended_at": execution["ended_at"].isoformat() if execution["ended_at"] else None
            }
            executions.append(summary)
            
            if len(executions) >= max_results:
                break
        
        # Sort by start time (newest first)
        executions.sort(key=lambda x: x["started_at"], reverse=True)
        
        return executions
    
    async def _simulate_workflow_execution(self, execution_id: str) -> None:
        """Simulate workflow execution with random delays and outcomes."""
        execution = self._executions[execution_id]
        
        try:
            # Simulate workflow steps
            for step in range(execution["total_steps"]):
                await asyncio.sleep(0.1)  # Simulate work
                execution["steps_completed"] = step + 1
                
                # Small chance of failure
                if step == 1 and hash(execution_id) % 10 == 0:  # 10% failure rate
                    execution["status"] = WorkflowStatus.FAILED
                    execution["ended_at"] = datetime.utcnow()
                    execution["error"] = "Simulated workflow failure"
                    return
            
            # Workflow completed successfully
            execution["status"] = WorkflowStatus.SUCCEEDED
            execution["ended_at"] = datetime.utcnow()
            execution["output"] = {
                "result": "success",
                "processed_input": execution["input"],
                "execution_time_seconds": (
                    execution["ended_at"] - execution["started_at"]
                ).total_seconds()
            }
            
        except Exception as e:
            execution["status"] = WorkflowStatus.FAILED
            execution["ended_at"] = datetime.utcnow()
            execution["error"] = str(e)
    
    def clear_all_executions(self) -> None:
        """Clear all workflow executions (for testing)."""
        self._executions.clear()
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics (for testing)."""
        status_counts = defaultdict(int)
        for execution in self._executions.values():
            status_counts[execution["status"].value] += 1
        
        return {
            "total_executions": len(self._executions),
            "status_breakdown": dict(status_counts)
        }


class MockEventBus(IEventBus):
    """Mock implementation of event bus for testing."""
    
    def __init__(self):
        """Initialize with in-memory event storage."""
        self._published_events: List[Dict[str, Any]] = []
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._event_handlers: Dict[str, Callable] = {}
    
    async def publish_event(self, event_type: str, source: str, detail: Dict[str, Any],
                           detail_type: Optional[str] = None) -> str:
        """Publish an event to the event bus."""
        event_id = str(uuid.uuid4())
        
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "source": source,
            "detail": deepcopy(detail),
            "detail_type": detail_type,
            "timestamp": datetime.utcnow(),
            "version": "1.0"
        }
        
        self._published_events.append(event)
        
        # Trigger matching subscriptions
        await self._trigger_subscriptions(event)
        
        return event_id
    
    async def subscribe_to_events(self, event_pattern: Dict[str, Any], 
                                 callback: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to events matching a pattern."""
        subscription_id = str(uuid.uuid4())
        
        self._subscriptions[subscription_id] = {
            "pattern": deepcopy(event_pattern),
            "created_at": datetime.utcnow()
        }
        
        self._event_handlers[subscription_id] = callback
        
        return subscription_id
    
    async def unsubscribe_from_events(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            del self._event_handlers[subscription_id]
            return True
        
        return False
    
    async def _trigger_subscriptions(self, event: Dict[str, Any]) -> None:
        """Trigger callbacks for matching subscriptions."""
        for subscription_id, subscription in self._subscriptions.items():
            if self._event_matches_pattern(event, subscription["pattern"]):
                callback = self._event_handlers.get(subscription_id)
                if callback:
                    try:
                        # Call callback in background to avoid blocking
                        asyncio.create_task(self._safe_callback(callback, event))
                    except Exception:
                        # Ignore callback errors in mock
                        pass
    
    async def _safe_callback(self, callback: Callable, event: Dict[str, Any]) -> None:
        """Safely execute callback with error handling."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception:
            # Ignore callback errors in mock implementation
            pass
    
    def _event_matches_pattern(self, event: Dict[str, Any], pattern: Dict[str, Any]) -> bool:
        """Check if an event matches a subscription pattern."""
        for key, expected_value in pattern.items():
            if key not in event:
                return False
            
            event_value = event[key]
            
            # Simple pattern matching
            if isinstance(expected_value, str):
                if expected_value != event_value:
                    return False
            elif isinstance(expected_value, list):
                if event_value not in expected_value:
                    return False
            elif isinstance(expected_value, dict):
                # Nested pattern matching
                if not isinstance(event_value, dict):
                    return False
                if not self._event_matches_pattern(event_value, expected_value):
                    return False
        
        return True
    
    def get_published_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get published events (for testing)."""
        if event_type:
            return [e for e in self._published_events if e["event_type"] == event_type]
        return deepcopy(self._published_events)
    
    def clear_all_events(self) -> None:
        """Clear all published events (for testing)."""
        self._published_events.clear()
    
    def clear_all_subscriptions(self) -> None:
        """Clear all subscriptions (for testing)."""
        self._subscriptions.clear()
        self._event_handlers.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics (for testing)."""
        return {
            "total_events_published": len(self._published_events),
            "active_subscriptions": len(self._subscriptions),
            "unique_event_types": len(set(e["event_type"] for e in self._published_events)),
            "unique_sources": len(set(e["source"] for e in self._published_events))
        }