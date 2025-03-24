from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from .models import User

@api_view(['POST'])
def register_user(request):
    data = request.data
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)
    
    user = User.objects.create(
        username=username,
        email=email,
        password=make_password(password),
    )
    
    return Response({
        'message': 'User registered successfully',
        'user_id': user.id,
        'username': user.username,
    }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def login_user(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')
    
    try:
        user = User.objects.get(email=email)
        if check_password(password, user.password):
            # Create simple session in request.session
            request.session['user_id'] = user.id
            
            return Response({
                'message': 'Login successful',
                'user_id': user.id,
                'username': user.username,
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def logout_user(request):
    # Clear session
    if 'user_id' in request.session:
        del request.session['user_id']
    return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)

@api_view(['GET'])
def get_user(request):
    user_id = request.session.get('user_id')
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'name': user.name,
                'bio': user.bio,
                'is_volunteer': user.is_volunteer,
                'is_organization': user.is_organization
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'error': 'Not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['PUT'])
def update_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return Response({'error': 'Not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        user = User.objects.get(id=user_id)
        data = request.data
        
        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'name' in data:
            user.name = data['name']
        if 'bio' in data:
            user.bio = data['bio']
        
        user.save()
        
        return Response({
            'message': 'User updated successfully',
            'user_id': user.id,
            'username': user.username,
        }, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)