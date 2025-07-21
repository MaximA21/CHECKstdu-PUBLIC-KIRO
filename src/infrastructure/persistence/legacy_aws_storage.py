"""
Legacy AWS DynamoDB storage service implementation.

This module provides the original IStorageService implementation for backward
compatibility with existing code that hasn't been migrated to the new repository pattern.
"""

import boto3
import logging
from typing import Dict, Any, Optional

from ...application.interfaces.storage import IStorageService


logger = logging.getLogger(__name__)


class AWSDynamoDBService(IStorageService):
    """
    AWS DynamoDB implementation of the legacy IStorageService interface.
    
    This class maintains backward compatibility with existing code while
    providing the same functionality as the original services/aws_storage.py.
    """

    def __init__(self, region_name: str = 'eu-central-1'):
        """
        Initialize AWS DynamoDB service.
        
        Args:
            region_name: AWS region name for DynamoDB resource
        """
        self.region_name = region_name
        self.resource = boto3.resource('dynamodb', region_name=region_name)
        self._tables = {}
        
        logger.info(f"Initialized AWS DynamoDB service in region: {region_name}")

    def _get_table(self, table_name: str):
        """
        Get or create a cached table reference.
        
        Args:
            table_name: Name of the DynamoDB table
            
        Returns:
            DynamoDB table resource
        """
        if table_name not in self._tables:
            self._tables[table_name] = self.resource.Table(table_name)
            logger.debug(f"Created table reference for: {table_name}")
        return self._tables[table_name]

    async def put_item(self, table_name: str, item: Dict[str, Any]) -> bool:
        """
        Store an item in DynamoDB table.
        
        Args:
            table_name: Name of the DynamoDB table
            item: Item data to store
            
        Returns:
            bool: True if storage was successful, False otherwise
        """
        try:
            table = self._get_table(table_name)
            table.put_item(Item=item)
            logger.debug(f"Successfully stored item in table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to store item in table {table_name}: {str(e)}")
            return False

    async def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve an item from DynamoDB table.
        
        Args:
            table_name: Name of the DynamoDB table
            key: Key to look up the item
            
        Returns:
            Optional[Dict[str, Any]]: Retrieved item or None if not found
        """
        try:
            table = self._get_table(table_name)
            response = table.get_item(Key=key)
            item = response.get('Item')
            
            if item:
                logger.debug(f"Successfully retrieved item from table: {table_name}")
            else:
                logger.debug(f"Item not found in table: {table_name}")
                
            return item
        except Exception as e:
            logger.error(f"Failed to retrieve item from table {table_name}: {str(e)}")
            return None