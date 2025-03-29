from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Admin
import json
import hashlib
from prakriti_setu.utils import generate_jwt_token, token_required, verify_jwt_token

def hash_password(password):
    """Hash a password for storing."""
    return hashlib.sha256(password.encode()).hexdigest()

@csrf_exempt
@api_view(['POST'])
def admin_login(request):
    try:
        data = request.data
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Hash the password before comparing
        hashed_password = hash_password(password)
        
        try:
            admin = Admin.objects.get(email=email)
            if admin.password == hashed_password:
                # Generate JWT token for admin
                token = generate_jwt_token(admin.email)
                
                return Response({
                    'success': True,
                    'admin': {
                        'id': admin.id,
                        'name': admin.name,
                        'email': admin.email
                    },
                    'token': token  # Include token in response
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except Admin.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
            
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def admin_register(request):
    try:
        data = request.data
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        if not name or not email or not password:
            return Response({'error': 'Name, email, and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if admin with this email already exists
        if Admin.objects.filter(email=email).exists():
            return Response({'error': 'Email already in use'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Hash the password before storing
        hashed_password = hash_password(password)
        
        # Create the admin
        admin = Admin.objects.create(
            name=name,
            email=email,
            password=hashed_password
        )
        
        # Generate JWT token for the new admin
        token = generate_jwt_token(admin.email)
        
        return Response({
            'success': True,
            'admin': {
                'id': admin.id,
                'name': admin.name,
                'email': admin.email
            },
            'token': token  # Include token in response
        }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def admin_logout(request):
    # No server-side session to invalidate with JWT
    # Client will handle token removal
    return Response({'success': True})

@api_view(['GET'])
@token_required
def admin_dashboard(request):
    # The token_required decorator ensures authentication
    # We can get the username from the request
    admin_email = request.username  # Set by token_required decorator
    
    try:
        admin = Admin.objects.get(email=admin_email)
        return Response({
            'message': 'Admin dashboard',
            'admin': {
                'id': admin.id,
                'name': admin.name,
                'email': admin.email
            }
        })
    except Admin.DoesNotExist:
        return Response({'error': 'Admin not found'}, status=status.HTTP_404_NOT_FOUND)
