"""AWS Step Functions workflow orchestrator adapter implementation."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from ...application.interfaces.messaging import IWorkflowOrchestrator, WorkflowStatus

logger = logging.getLogger(__name__)


class AWSStepFunctionsOrchestrator(IWorkflowOrchestrator):
    """AWS Step Functions implementation of workflow orchestrator interface."""

    def __init__(self, region_name: str = "eu-central-1", state_machine_arn_prefix: Optional[str] = None):
        """
        Initialize AWS Step Functions orchestrator.

        Args:
            region_name: AWS region name
            state_machine_arn_prefix: Optional prefix for state machine ARNs
        """
        self.region_name = region_name
        self.state_machine_arn_prefix = state_machine_arn_prefix or ""
        self._stepfunctions = boto3.client("stepfunctions", region_name=region_name)
        self._state_machine_arns = {}  # Cache for state machine ARNs

        logger.info(f"Initialized AWS Step Functions orchestrator for region: {region_name}")

    def _get_state_machine_arn(self, workflow_name: str) -> str:
        """Get or resolve state machine ARN for a given workflow name."""
        if workflow_name in self._state_machine_arns:
            return self._state_machine_arns[workflow_name]

        try:
            # List state machines and find by name
            response = self._stepfunctions.list_state_machines()

            for state_machine in response.get("stateMachines", []):
                if state_machine["name"] == workflow_name:
                    arn = state_machine["stateMachineArn"]
                    self._state_machine_arns[workflow_name] = arn
                    logger.debug(f"Resolved state machine ARN for {workflow_name}: {arn}")
                    return arn

            # If not found, construct ARN if prefix is provided
            if self.state_machine_arn_prefix:
                arn = f"{self.state_machine_arn_prefix}:{workflow_name}"
                self._state_machine_arns[workflow_name] = arn
                logger.debug(f"Constructed state machine ARN for {workflow_name}: {arn}")
                return arn

            raise ValueError(f"State machine {workflow_name} not found")

        except ClientError as e:
            logger.error(f"Failed to get state machine ARN for {workflow_name}: {e}")
            raise RuntimeError(f"Failed to get state machine ARN: {e}")

    def _map_execution_status(self, aws_status: str) -> WorkflowStatus:
        """Map AWS Step Functions status to our WorkflowStatus enum."""
        status_mapping = {
            "RUNNING": WorkflowStatus.RUNNING,
            "SUCCEEDED": WorkflowStatus.SUCCEEDED,
            "FAILED": WorkflowStatus.FAILED,
            "TIMED_OUT": WorkflowStatus.TIMED_OUT,
            "ABORTED": WorkflowStatus.ABORTED,
        }

        return status_mapping.get(aws_status, WorkflowStatus.FAILED)

    async def start_workflow(
        self, workflow_name: str, input_data: Dict[str, Any], execution_name: Optional[str] = None
    ) -> str:
        """Start a workflow execution."""
        try:
            state_machine_arn = self._get_state_machine_arn(workflow_name)

            # Generate execution name if not provided
            if execution_name is None:
                execution_name = f"{workflow_name}-{uuid.uuid4().hex[:8]}-{int(datetime.utcnow().timestamp())}"

            # Prepare input data
            input_json = json.dumps(input_data, default=str, separators=(",", ":"))

            # Start execution
            response = self._stepfunctions.start_execution(
                stateMachineArn=state_machine_arn, name=execution_name, input=input_json
            )

            execution_arn = response["executionArn"]

            logger.info(f"Started workflow {workflow_name} with execution: {execution_name}")
            logger.debug(f"Execution ARN: {execution_arn}")

            return execution_arn

        except ClientError as e:
            logger.error(f"Failed to start workflow {workflow_name}: {e}")
            raise RuntimeError(f"Failed to start workflow: {e}")
        except json.JSONEncodeError as e:
            logger.error(f"Failed to serialize input data: {e}")
            raise ValueError(f"Input data is not JSON serializable: {e}")

    async def get_workflow_status(self, execution_id: str) -> WorkflowStatus:
        """Get the status of a workflow execution."""
        try:
            response = self._stepfunctions.describe_execution(executionArn=execution_id)

            aws_status = response["status"]
            status = self._map_execution_status(aws_status)

            logger.debug(f"Workflow {execution_id} status: {status.value}")
            return status

        except ClientError as e:
            logger.error(f"Failed to get workflow status for {execution_id}: {e}")
            return WorkflowStatus.FAILED

    async def get_workflow_output(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get the output of a completed workflow execution."""
        try:
            response = self._stepfunctions.describe_execution(executionArn=execution_id)

            # Check if execution is completed
            if response["status"] not in ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]:
                logger.debug(f"Workflow {execution_id} is not completed yet")
                return None

            # Get output if available
            output_json = response.get("output")
            if output_json:
                try:
                    output = json.loads(output_json)
                    logger.debug(f"Retrieved output for workflow {execution_id}")
                    return output
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse workflow output: {e}")
                    return {"raw_output": output_json}

            # If no output but execution failed, get error details
            if response["status"] in ["FAILED", "TIMED_OUT", "ABORTED"]:
                error_details = {
                    "status": response["status"],
                    "stop_date": response.get("stopDate", "").isoformat() if response.get("stopDate") else None,
                }

                # Get execution history for more details
                try:
                    history_response = self._stepfunctions.get_execution_history(
                        executionArn=execution_id, maxResults=10, reverseOrder=True
                    )

                    # Look for failure events
                    for event in history_response.get("events", []):
                        if event["type"] in ["ExecutionFailed", "ExecutionTimedOut", "ExecutionAborted"]:
                            if "executionFailedEventDetails" in event:
                                error_details["error"] = event["executionFailedEventDetails"].get("error")
                                error_details["cause"] = event["executionFailedEventDetails"].get("cause")
                            elif "executionTimedOutEventDetails" in event:
                                error_details["error"] = "Execution timed out"
                                error_details["cause"] = event["executionTimedOutEventDetails"].get("cause")
                            elif "executionAbortedEventDetails" in event:
                                error_details["error"] = "Execution aborted"
                                error_details["cause"] = event["executionAbortedEventDetails"].get("cause")
                            break

                except ClientError:
                    pass  # Ignore history retrieval errors

                return error_details

            return None

        except ClientError as e:
            logger.error(f"Failed to get workflow output for {execution_id}: {e}")
            return None

    async def stop_workflow(self, execution_id: str, reason: str = "User requested") -> bool:
        """Stop a running workflow execution."""
        try:
            self._stepfunctions.stop_execution(executionArn=execution_id, error="UserRequested", cause=reason)

            logger.info(f"Stopped workflow execution {execution_id}: {reason}")
            return True

        except ClientError as e:
            logger.error(f"Failed to stop workflow {execution_id}: {e}")
            return False

    async def list_workflow_executions(
        self, workflow_name: str, status_filter: Optional[WorkflowStatus] = None, max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """List workflow executions for a given workflow."""
        try:
            state_machine_arn = self._get_state_machine_arn(workflow_name)

            list_params = {"stateMachineArn": state_machine_arn, "maxResults": min(max_results, 1000)}  # AWS max is 1000

            # Add status filter if provided
            if status_filter:
                # Map our status to AWS status
                aws_status_map = {
                    WorkflowStatus.RUNNING: "RUNNING",
                    WorkflowStatus.SUCCEEDED: "SUCCEEDED",
                    WorkflowStatus.FAILED: "FAILED",
                    WorkflowStatus.TIMED_OUT: "TIMED_OUT",
                    WorkflowStatus.ABORTED: "ABORTED",
                }

                aws_status = aws_status_map.get(status_filter)
                if aws_status:
                    list_params["statusFilter"] = aws_status

            response = self._stepfunctions.list_executions(**list_params)

            executions = []
            for execution in response.get("executions", []):
                execution_summary = {
                    "execution_arn": execution["executionArn"],
                    "name": execution["name"],
                    "status": self._map_execution_status(execution["status"]).value,
                    "start_date": execution["startDate"].isoformat() if execution.get("startDate") else None,
                    "stop_date": execution["stopDate"].isoformat() if execution.get("stopDate") else None,
                }
                executions.append(execution_summary)

            logger.info(f"Listed {len(executions)} executions for workflow {workflow_name}")
            return executions

        except ClientError as e:
            logger.error(f"Failed to list executions for workflow {workflow_name}: {e}")
            return []

    def get_execution_history(self, execution_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get execution history for debugging (utility method).

        Args:
            execution_id: Execution ARN
            max_results: Maximum number of events to return

        Returns:
            List[Dict[str, Any]]: List of execution events
        """
        try:
            response = self._stepfunctions.get_execution_history(
                executionArn=execution_id, maxResults=min(max_results, 1000), reverseOrder=True
            )

            events = []
            for event in response.get("events", []):
                event_summary = {
                    "timestamp": event["timestamp"].isoformat() if event.get("timestamp") else None,
                    "type": event["type"],
                    "id": event["id"],
                    "previous_event_id": event.get("previousEventId"),
                }

                # Add type-specific details
                if "stateEnteredEventDetails" in event:
                    event_summary["state_name"] = event["stateEnteredEventDetails"].get("name")
                elif "stateExitedEventDetails" in event:
                    event_summary["state_name"] = event["stateExitedEventDetails"].get("name")
                elif "taskFailedEventDetails" in event:
                    event_summary["error"] = event["taskFailedEventDetails"].get("error")
                    event_summary["cause"] = event["taskFailedEventDetails"].get("cause")

                events.append(event_summary)

            logger.debug(f"Retrieved {len(events)} history events for execution {execution_id}")
            return events

        except ClientError as e:
            logger.error(f"Failed to get execution history for {execution_id}: {e}")
            return []

    def create_state_machine(
        self, name: str, definition: Dict[str, Any], role_arn: str, machine_type: str = "STANDARD"
    ) -> str:
        """
        Create a new state machine (utility method).

        Args:
            name: Name of the state machine
            definition: State machine definition (ASL)
            role_arn: IAM role ARN for the state machine
            machine_type: Type of state machine ('STANDARD' or 'EXPRESS')

        Returns:
            str: State machine ARN
        """
        try:
            definition_json = json.dumps(definition, separators=(",", ":"))

            response = self._stepfunctions.create_state_machine(
                name=name, definition=definition_json, roleArn=role_arn, type=machine_type
            )

            state_machine_arn = response["stateMachineArn"]

            # Cache the ARN
            self._state_machine_arns[name] = state_machine_arn

            logger.info(f"Created state machine {name}: {state_machine_arn}")
            return state_machine_arn

        except ClientError as e:
            logger.error(f"Failed to create state machine {name}: {e}")
            raise RuntimeError(f"Failed to create state machine: {e}")
        except json.JSONEncodeError as e:
            logger.error(f"Failed to serialize state machine definition: {e}")
            raise ValueError(f"State machine definition is not JSON serializable: {e}")

    def delete_state_machine(self, workflow_name: str) -> bool:
        """
        Delete a state machine (utility method).

        Args:
            workflow_name: Name of the workflow/state machine to delete

        Returns:
            bool: True if successful
        """
        try:
            state_machine_arn = self._get_state_machine_arn(workflow_name)

            self._stepfunctions.delete_state_machine(stateMachineArn=state_machine_arn)

            # Remove from cache
            if workflow_name in self._state_machine_arns:
                del self._state_machine_arns[workflow_name]

            logger.warning(f"Deleted state machine: {workflow_name}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete state machine {workflow_name}: {e}")
            return False
