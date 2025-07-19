import boto3
from storage_interface import IStorageService
from typing import Dict, Any, Optional


class AWSDynamoDBService(IStorageService):
    """AWS DynamoDB implementation """

    def __init__(self, region_name: str = 'eu-central-1'):
        self.resource = boto3.resource('dynamodb', region_name=region_name)
        self._tables = {}

    def _get_table(self, table_name: str):

        if table_name not in self._tables:
            self._tables[table_name] = self.resource.Table(table_name)
        return self._tables[table_name]

    async def put_item(self, table_name: str, item: Dict[str, Any]) -> bool:
        try:
            table = self._get_table(table_name)
            table.put_item(Item=item)
            return True
        except Exception:
            return False

    async def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            table = self._get_table(table_name)
            response = table.get_item(Key=key)
            return response.get('Item')
        except Exception:
            return None
