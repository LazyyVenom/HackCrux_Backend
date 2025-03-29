from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from .models import User
from django.views.decorators.csrf import csrf_exempt
from .utils import generate_jwt_token, token_required  # Import our JWT utilities
from prakirti_admin.models import VolunteeringEvent, EventRegistration

@csrf_exempt
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

@csrf_exempt
@api_view(['POST'])
def login_user(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')
    
    try:
        user = User.objects.get(email=email)
        if check_password(password, user.password):
            # Create session in request.session
            request.session['user_id'] = user.id
            
            # Generate JWT token
            token = generate_jwt_token(user.username)
            
            return Response({
                'message': 'Login successful',
                'user_id': user.id,
                'username': user.username,
                'token': token,  # Return the token to the client
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

@csrf_exempt
@api_view(['POST'])
def logout_user(request):
    # Clear session
    if 'user_id' in request.session:
        del request.session['user_id']
    return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)

@csrf_exempt
@api_view(['GET'])
@token_required  # Apply our token_required decorator for protected routes
def get_user(request):
    # Get username from the request added by the decorator
    username = request.username
    
    try:
        user = User.objects.get(username=username)
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

@csrf_exempt
@api_view(['PUT'])
@token_required  # Apply our token_required decorator for protected routes
def update_user(request):
    username = request.username
    
    try:
        user = User.objects.get(username=username)
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

@csrf_exempt
@api_view(['GET'])
def get_active_events(request):
    """
    Get all active volunteering events
    """
    try:
        events = VolunteeringEvent.objects.filter(status='active').order_by('date')
        events_data = []
        
        for event in events:
            events_data.append({
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'date': event.date,
                'time': event.time,
                'location': event.location,
                'category': event.category,
                'spots_total': event.spots_total,
                'spots_filled': event.spots_filled,
                'spots_remaining': event.spots_remaining,
                'organizer': event.organizer,
                'status': event.status,
                'created_at': event.created_at,
            })
            
        return Response(events_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@token_required
def register_for_event(request, event_id):
    """
    Register a user for a volunteering event
    """
    try:
        # Get the username from the token
        username = request.username
        
        # Get the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get the event
        try:
            event = VolunteeringEvent.objects.get(pk=event_id)
        except VolunteeringEvent.DoesNotExist:
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if event is active
        if event.status != 'active':
            return Response({'error': 'Event is not active'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if there are spots available
        if event.spots_remaining <= 0:
            return Response({'error': 'No spots left for this event'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the user is already registered
        if EventRegistration.objects.filter(event=event, email=user.email).exists():
            return Response({'error': 'You are already registered for this event'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Get data from the request
        data = request.data
        phone = data.get('phone', '')
        
        if not phone:
            return Response({'error': 'Phone number is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a new registration
        registration = EventRegistration.objects.create(
            event=event,
            name=user.name or user.username,
            email=user.email,
            phone=phone,
            status='confirmed'
        )
        
        # No need to update spots_filled, as it's a calculated property
        # that gets its value from the number of confirmed registrations
        
        return Response({
            'success': True,
            'message': 'Successfully registered for the event',
            'registration': {
                'id': registration.id,
                'event_title': event.title,
                'event_date': event.date,
                'event_time': event.time,
                'event_location': event.location,
                'registration_date': registration.registration_date,
                'status': registration.status
            }
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
@token_required
def get_user_registrations(request):
    """
    Get all event registrations for a user
    """
    try:
        # Get the username from the token
        username = request.username
        
        # Get the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all registrations for the user's email
        registrations = EventRegistration.objects.filter(email=user.email).order_by('-registration_date')
        
        registrations_data = []
        for registration in registrations:
            event = registration.event
            registrations_data.append({
                'id': registration.id,
                'event_id': event.id,
                'event_title': event.title,
                'event_description': event.description,
                'event_date': event.date,
                'event_time': event.time,
                'event_location': event.location,
                'event_category': event.category,
                'event_organizer': event.organizer,
                'event_status': event.status,
                'registration_date': registration.registration_date,
                'status': registration.status
            })
        
        return Response(registrations_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)