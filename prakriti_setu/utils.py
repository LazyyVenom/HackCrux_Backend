import jwt
import datetime
from functools import wraps
from django.http import JsonResponse
from django.conf import settings

# JWT Secret key - in production, this should be in environment variables
JWT_SECRET = getattr(settings, 'JWT_SECRET', 'your_jwt_secret_key')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_DELTA = datetime.timedelta(days=1)  # Token valid for 1 day

def generate_jwt_token(username):
    """
    Generate a JWT token with the username
    """
    payload = {
        'username': username,
        'exp': datetime.datetime.utcnow() + JWT_EXPIRATION_DELTA,
        'iat': datetime.datetime.utcnow()
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def verify_jwt_token(token):
    """
    Verify the JWT token and return the username if valid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload['username']
    except jwt.ExpiredSignatureError:
        return None  # Token has expired
    except jwt.InvalidTokenError:
        return None  # Invalid token
    
def token_required(view_func):
    """
    Decorator for views that require a valid token
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return JsonResponse({'error': 'Authorization header is missing'}, status=401)
        
        try:
            # Extract token from "Bearer <token>"
            token = auth_header.split(' ')[1]
            username = verify_jwt_token(token)
            
            if not username:
                return JsonResponse({'error': 'Invalid or expired token'}, status=401)
                
            # Add username to request for use in view
            request.username = username
            
            return view_func(request, *args, **kwargs)
        except IndexError:
            return JsonResponse({'error': 'Invalid Authorization header format'}, status=401)
            
    return wrapped_view