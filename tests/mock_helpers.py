"""
Mock helpers for testing
"""

class MockAsyncContextManager:
    """Mock async context manager for testing"""
    def __init__(self, return_value):
        self.return_value = return_value
        
    async def __aenter__(self):
        return self.return_value
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None