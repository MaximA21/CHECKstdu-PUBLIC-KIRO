from storage_interface import IStorageService
from typing import Dict, Any, Optional
import json


class MockStorageService(IStorageService):
    """Fake storage for testing - no AWS needed!"""

    def __init__(self):
        # Just store everything in memory
        self.tables = {}  # table_name -> dict of items

    async def put_item(self, table_name: str, item: Dict[str, Any]) -> bool:
        """Fake storage - just keeps items in memory"""
        if table_name not in self.tables:
            self.tables[table_name] = {}

        # Create a simple key from the item
        key_str = json.dumps(item.get('request_id', 'unknown'), sort_keys=True)
        self.tables[table_name][key_str] = item
        return True

    async def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fake retrieval - just looks in memory"""
        if table_name not in self.tables:
            return None

        key_str = json.dumps(key.get('request_id', 'unknown'), sort_keys=True)
        return self.tables[table_name].get(key_str)
