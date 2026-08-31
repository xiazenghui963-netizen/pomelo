class BizError(Exception):
    def __init__(self, message: str, code: int = 40000, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)