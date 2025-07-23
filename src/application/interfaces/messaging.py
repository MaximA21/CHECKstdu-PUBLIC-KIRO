"""Messaging interfaces for queue and workflow management."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class WorkflowStatus(Enum):
    """Workflow execution status."""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    ABORTED = "ABORTED"


class IMessageQueue(ABC):
    """Interface for message queue operations."""

    @abstractmethod
    async def send_message(
        self,
        queue_name: str,
        message: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: int = 0,
    ) -> str:
        """
        Send a message to a queue.

        Args:
            queue_name: Name of the queue
            message: Message payload
            priority: Message priority level
            delay_seconds: Delay before message becomes available

        Returns:
            str: Message ID
        """
        pass

    @abstractmethod
    async def receive_messages(
        self, queue_name: str, max_messages: int = 10, wait_time_seconds: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Receive messages from a queue.

        Args:
            queue_name: Name of the queue
            max_messages: Maximum number of messages to receive
            wait_time_seconds: Long polling wait time

        Returns:
            List[Dict[str, Any]]: List of received messages
        """
        pass

    @abstractmethod
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """
        Delete a message from the queue.

        Args:
            queue_name: Name of the queue
            receipt_handle: Receipt handle of the message to delete

        Returns:
            bool: True if deletion was successful
        """
        pass

    @abstractmethod
    async def get_queue_attributes(self, queue_name: str) -> Dict[str, Any]:
        """
        Get queue attributes and statistics.

        Args:
            queue_name: Name of the queue

        Returns:
            Dict[str, Any]: Queue attributes
        """
        pass

    @abstractmethod
    async def purge_queue(self, queue_name: str) -> bool:
        """
        Purge all messages from a queue.

        Args:
            queue_name: Name of the queue to purge

        Returns:
            bool: True if purge was successful
        """
        pass


class IWorkflowOrchestrator(ABC):
    """Interface for workflow orchestration (Step Functions, etc.)."""

    @abstractmethod
    async def start_workflow(
        self, workflow_name: str, input_data: Dict[str, Any], execution_name: Optional[str] = None
    ) -> str:
        """
        Start a workflow execution.

        Args:
            workflow_name: Name of the workflow to execute
            input_data: Input data for the workflow
            execution_name: Optional custom execution name

        Returns:
            str: Execution ID/ARN
        """
        pass

    @abstractmethod
    async def get_workflow_status(self, execution_id: str) -> WorkflowStatus:
        """
        Get the status of a workflow execution.

        Args:
            execution_id: Execution ID to check

        Returns:
            WorkflowStatus: Current status of the execution
        """
        pass

    @abstractmethod
    async def get_workflow_output(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the output of a completed workflow execution.

        Args:
            execution_id: Execution ID to get output for

        Returns:
            Optional[Dict[str, Any]]: Workflow output or None if not completed
        """
        pass

    @abstractmethod
    async def stop_workflow(self, execution_id: str, reason: str = "User requested") -> bool:
        """
        Stop a running workflow execution.

        Args:
            execution_id: Execution ID to stop
            reason: Reason for stopping the workflow

        Returns:
            bool: True if stop was successful
        """
        pass

    @abstractmethod
    async def list_workflow_executions(
        self, workflow_name: str, status_filter: Optional[WorkflowStatus] = None, max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List workflow executions for a given workflow.

        Args:
            workflow_name: Name of the workflow
            status_filter: Optional status to filter by
            max_results: Maximum number of results to return

        Returns:
            List[Dict[str, Any]]: List of execution summaries
        """
        pass


class IEventBus(ABC):
    """Interface for event bus operations (EventBridge, etc.)."""

    @abstractmethod
    async def publish_event(
        self, event_type: str, source: str, detail: Dict[str, Any], detail_type: Optional[str] = None
    ) -> str:
        """
        Publish an event to the event bus.

        Args:
            event_type: Type of the event
            source: Source of the event
            detail: Event detail payload
            detail_type: Optional detail type

        Returns:
            str: Event ID
        """
        pass

    @abstractmethod
    async def subscribe_to_events(self, event_pattern: Dict[str, Any], callback: Callable[[Dict[str, Any]], None]) -> str:
        """
        Subscribe to events matching a pattern.

        Args:
            event_pattern: Pattern to match events against
            callback: Function to call when matching events are received

        Returns:
            str: Subscription ID
        """
        pass

    @abstractmethod
    async def unsubscribe_from_events(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.

        Args:
            subscription_id: ID of the subscription to remove

        Returns:
            bool: True if unsubscribe was successful
        """
        pass
