import sys
import os
import json

# Add src directory to path for importing the new DI-based handler
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    # Import the new DI-based handler
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.connect_handler import ConnectHandler
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.connect_handler import ConnectHandler
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase


def lambda_handler(event, context):
    """Lambda entry point using dependency injection architecture."""
    try:
        # Handle warmer requests efficiently
        if event.get('warmer'):
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Lambda warmed successfully",
                    "function": "connect_handler"
                })
            }
        
        # Get DI container
        container = get_container()
        
        # Create handler with dependencies
        handler = ConnectHandler(
            connection_management_use_case=container.get(ConnectionManagementUseCase),
            logger=container.get_logger("connect_handler")
        )
        
        # Handle request
        import asyncio
        return asyncio.run(handler.handle_request(event))
        
    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in connect handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': 'Connection failed'
            })
        }
"""
    # In DynamoDB speichern
    try:
        session_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        item = {
            'session_id': session_id,
            'connection_id': connection_id,
            'timestamp': timestamp,
            'status': 'connected',
            'address': {
                'street': street,
                'house_number': house_number,
                'city': city,
                'postal_code': postal_code
            } if all([street, house_number, city, postal_code]) else {}
        }

        # Eindeutige Share-ID für den Teilen-Link generieren
        share_id = str(uuid.uuid4())[:8]  # Kürzere Version für den Link
        item['share_id'] = share_id

        # Log session details at DEBUG level
        logger.debug(f"Generated session ID: {session_id}")
        logger.debug(f"Generated share ID: {share_id}")
        logger.debug(f"Session timestamp: {timestamp}")
        logger.debug(f"DynamoDB item: {json.dumps(item, default=str)}")

        # In DynamoDB speichern
        table.put_item(Item=item)

        # Connection saved successfully at INFO level
        logger.info(f"Connection session saved successfully - Connection: {connection_id}, Session: {session_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Verbunden',
                'session_id': session_id,
                'share_id': share_id
            })
        }
    except Exception as e:
        logger.error(f"Failed to save connection session: {str(e)}")
        return {'statusCode': 500, 'body': 'Internal server error'}
        """
