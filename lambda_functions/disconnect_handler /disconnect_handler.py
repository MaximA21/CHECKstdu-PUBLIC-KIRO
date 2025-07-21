import sys
import os

# Add src directory to path for importing the new DI-based handler
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import the new DI-based handler
from presentation.lambda_handlers.disconnect_handler import lambda_handler as di_lambda_handler


def lambda_handler(event, context):
    """Lambda entry point that delegates to DI-based handler."""
    return di_lambda_handler(event, context)