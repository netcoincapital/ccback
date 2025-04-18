class ResourceAlreadyExists(Exception):
    """Exception raised when a resource already exists."""
    
    def __init__(self, message="Resource already exists"):
        self.message = message
        super().__init__(self.message) 