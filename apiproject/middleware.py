# ไฟล์: apiproject/middleware.py
import time
import logging

logger = logging.getLogger('django')

class ResponseTimeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        process_time = time.time() - start_time
        response['X-Process-Time'] = str(process_time)
        
        print(f"Request {request.path} took: {process_time:.2f} seconds")
        logger.info(f"API {request.path} took: {process_time:.2f} seconds")
        
        return response