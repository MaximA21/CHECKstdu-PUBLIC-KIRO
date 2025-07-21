"""AWS SQS message queue adapter implementation."""

import boto3
import json
import logging
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError
from datetime import datetime

from ...application.interfaces.messaging import (
    IMessageQueue, 
    MessagePriority
)


logger = logging.getLogger(__name__)


class AWSSQSMessageQueue(IMessageQueue):
    """AWS SQS implementation of message queue interface."""
    
    def __init__(self, region_name: str = 'eu-central-1', queue_url_prefix: Optional[str] = None):
        """
        Initialize AWS SQS message queue.
        
        Args:
            region_name: AWS region name
            queue_url_prefix: Optional prefix for queue URLs (e.g., account-specific prefix)
        """
        self.region_name = region_name
        self.queue_url_prefix = queue_url_prefix or ""
        self._sqs = boto3.client('sqs', region_name=region_name)
        self._queue_urls = {}  # Cache for queue URLs
        
        logger.info(f"Initialized AWS SQS adapter for region: {region_name}")
    
    def _get_queue_url(self, queue_name: str) -> str:
        """Get or resolve queue URL for a given queue name."""
        if queue_name in self._queue_urls:
            return self._queue_urls[queue_name]
        
        try:
            # Try to get queue URL by name
            response = self._sqs.get_queue_url(QueueName=queue_name)
            queue_url = response['QueueUrl']
            
            # Cache the URL
            self._queue_urls[queue_name] = queue_url
            logger.debug(f"Resolved queue URL for {queue_name}: {queue_url}")
            
            return queue_url
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'AWS.SimpleQueueService.NonExistentQueue':
                logger.error(f"Queue {queue_name} does not exist")
                raise ValueError(f"Queue {queue_name} does not exist")
            else:
                logger.error(f"Failed to get queue URL for {queue_name}: {e}")
                raise RuntimeError(f"Failed to get queue URL: {e}")
    
    def _get_message_attributes(self, priority: MessagePriority) -> Dict[str, Any]:
        """Get SQS message attributes for priority and metadata."""
        attributes = {
            'Priority': {
                'StringValue': priority.value,
                'DataType': 'String'
            },
            'Timestamp': {
                'StringValue': datetime.utcnow().isoformat(),
                'DataType': 'String'
            }
        }
        
        # Add priority-specific attributes
        if priority == MessagePriority.HIGH:
            attributes['HighPriority'] = {
                'StringValue': 'true',
                'DataType': 'String'
            }
        elif priority == MessagePriority.URGENT:
            attributes['Urgent'] = {
                'StringValue': 'true',
                'DataType': 'String'
            }
        
        return attributes
    
    async def send_message(self, queue_name: str, message: Dict[str, Any], 
                          priority: MessagePriority = MessagePriority.NORMAL,
                          delay_seconds: int = 0) -> str:
        """Send a message to a queue."""
        try:
            queue_url = self._get_queue_url(queue_name)
            
            # Prepare message body
            message_body = json.dumps(message, default=str, separators=(',', ':'))
            
            # Prepare send parameters
            send_params = {
                'QueueUrl': queue_url,
                'MessageBody': message_body,
                'MessageAttributes': self._get_message_attributes(priority)
            }
            
            # Add delay if specified
            if delay_seconds > 0:
                send_params['DelaySeconds'] = min(delay_seconds, 900)  # Max 15 minutes
            
            # Send message
            response = self._sqs.send_message(**send_params)
            
            message_id = response['MessageId']
            logger.info(f"Sent message to {queue_name} with ID: {message_id}")
            logger.debug(f"Message details: priority={priority.value}, delay={delay_seconds}s")
            
            return message_id
            
        except ClientError as e:
            logger.error(f"Failed to send message to {queue_name}: {e}")
            raise RuntimeError(f"Failed to send message: {e}")
        except json.JSONEncodeError as e:
            logger.error(f"Failed to serialize message: {e}")
            raise ValueError(f"Message is not JSON serializable: {e}")
    
    async def receive_messages(self, queue_name: str, max_messages: int = 10,
                              wait_time_seconds: int = 20) -> List[Dict[str, Any]]:
        """Receive messages from a queue."""
        try:
            queue_url = self._get_queue_url(queue_name)
            
            response = self._sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=min(max_messages, 10),  # SQS max is 10
                WaitTimeSeconds=min(wait_time_seconds, 20),  # SQS max is 20
                MessageAttributeNames=['All'],
                AttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            # Process and format messages
            formatted_messages = []
            for msg in messages:
                try:
                    # Parse message body
                    body = json.loads(msg['Body'])
                    
                    # Extract message attributes
                    attributes = {}
                    for attr_name, attr_data in msg.get('MessageAttributes', {}).items():
                        attributes[attr_name] = attr_data.get('StringValue', attr_data.get('BinaryValue'))
                    
                    formatted_message = {
                        'message_id': msg['MessageId'],
                        'receipt_handle': msg['ReceiptHandle'],
                        'body': body,
                        'attributes': attributes,
                        'approximate_receive_count': int(msg.get('Attributes', {}).get('ApproximateReceiveCount', '1')),
                        'sent_timestamp': msg.get('Attributes', {}).get('SentTimestamp'),
                        'approximate_first_receive_timestamp': msg.get('Attributes', {}).get('ApproximateFirstReceiveTimestamp')
                    }
                    
                    formatted_messages.append(formatted_message)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message body: {e}")
                    # Include raw message for debugging
                    formatted_messages.append({
                        'message_id': msg['MessageId'],
                        'receipt_handle': msg['ReceiptHandle'],
                        'body': msg['Body'],  # Raw body
                        'parse_error': str(e)
                    })
            
            logger.info(f"Received {len(formatted_messages)} messages from {queue_name}")
            return formatted_messages
            
        except ClientError as e:
            logger.error(f"Failed to receive messages from {queue_name}: {e}")
            raise RuntimeError(f"Failed to receive messages: {e}")
    
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """Delete a message from the queue."""
        try:
            queue_url = self._get_queue_url(queue_name)
            
            self._sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
            
            logger.debug(f"Deleted message from {queue_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete message from {queue_name}: {e}")
            return False
    
    async def get_queue_attributes(self, queue_name: str) -> Dict[str, Any]:
        """Get queue attributes and statistics."""
        try:
            queue_url = self._get_queue_url(queue_name)
            
            response = self._sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            
            attributes = response.get('Attributes', {})
            
            # Format common attributes
            formatted_attributes = {
                'approximate_number_of_messages': int(attributes.get('ApproximateNumberOfMessages', '0')),
                'approximate_number_of_messages_not_visible': int(attributes.get('ApproximateNumberOfMessagesNotVisible', '0')),
                'approximate_number_of_messages_delayed': int(attributes.get('ApproximateNumberOfMessagesDelayed', '0')),
                'created_timestamp': attributes.get('CreatedTimestamp'),
                'last_modified_timestamp': attributes.get('LastModifiedTimestamp'),
                'visibility_timeout_seconds': int(attributes.get('VisibilityTimeout', '30')),
                'message_retention_period_seconds': int(attributes.get('MessageRetentionPeriod', '1209600')),
                'delay_seconds': int(attributes.get('DelaySeconds', '0')),
                'receive_message_wait_time_seconds': int(attributes.get('ReceiveMessageWaitTimeSeconds', '0')),
                'queue_arn': attributes.get('QueueArn'),
                'raw_attributes': attributes  # Include all raw attributes
            }
            
            logger.debug(f"Retrieved attributes for queue {queue_name}")
            return formatted_attributes
            
        except ClientError as e:
            logger.error(f"Failed to get queue attributes for {queue_name}: {e}")
            return {}
    
    async def purge_queue(self, queue_name: str) -> bool:
        """Purge all messages from a queue."""
        try:
            queue_url = self._get_queue_url(queue_name)
            
            self._sqs.purge_queue(QueueUrl=queue_url)
            
            logger.warning(f"Purged all messages from queue: {queue_name}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'AWS.SimpleQueueService.PurgeQueueInProgress':
                logger.warning(f"Purge already in progress for queue: {queue_name}")
                return True
            else:
                logger.error(f"Failed to purge queue {queue_name}: {e}")
                return False
    
    def create_queue(self, queue_name: str, attributes: Optional[Dict[str, str]] = None) -> str:
        """
        Create a new SQS queue (utility method).
        
        Args:
            queue_name: Name of the queue to create
            attributes: Optional queue attributes
            
        Returns:
            str: Queue URL
        """
        try:
            create_params = {'QueueName': queue_name}
            
            if attributes:
                create_params['Attributes'] = attributes
            
            response = self._sqs.create_queue(**create_params)
            queue_url = response['QueueUrl']
            
            # Cache the URL
            self._queue_urls[queue_name] = queue_url
            
            logger.info(f"Created queue {queue_name}: {queue_url}")
            return queue_url
            
        except ClientError as e:
            logger.error(f"Failed to create queue {queue_name}: {e}")
            raise RuntimeError(f"Failed to create queue: {e}")
    
    def delete_queue(self, queue_name: str) -> bool:
        """
        Delete an SQS queue (utility method).
        
        Args:
            queue_name: Name of the queue to delete
            
        Returns:
            bool: True if successful
        """
        try:
            queue_url = self._get_queue_url(queue_name)
            
            self._sqs.delete_queue(QueueUrl=queue_url)
            
            # Remove from cache
            if queue_name in self._queue_urls:
                del self._queue_urls[queue_name]
            
            logger.warning(f"Deleted queue: {queue_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete queue {queue_name}: {e}")
            return False
    
    def list_queues(self, queue_name_prefix: Optional[str] = None) -> List[str]:
        """
        List available queues (utility method).
        
        Args:
            queue_name_prefix: Optional prefix to filter queues
            
        Returns:
            List[str]: List of queue URLs
        """
        try:
            list_params = {}
            if queue_name_prefix:
                list_params['QueueNamePrefix'] = queue_name_prefix
            
            response = self._sqs.list_queues(**list_params)
            queue_urls = response.get('QueueUrls', [])
            
            logger.info(f"Found {len(queue_urls)} queues")
            return queue_urls
            
        except ClientError as e:
            logger.error(f"Failed to list queues: {e}")
            return []