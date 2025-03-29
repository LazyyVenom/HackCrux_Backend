from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Admin, VolunteeringEvent, EventRegistration
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
        secret_key = data.get('secret_key')
        
        if not name or not email or not password or not secret_key:
            return Response({'error': 'Name, email, password, and secret key are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate the secret key
        # Using a hardcoded value here, but in a production app, consider using environment variables
        valid_secret_key = "prakriti_admin_key_2025"
        if secret_key != valid_secret_key:
            return Response({'error': 'Invalid secret key'}, status=status.HTTP_403_FORBIDDEN)
            
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

@api_view(['GET'])
@token_required
def get_events(request):
    """
    Get all volunteering events
    """
    try:
        events = VolunteeringEvent.objects.all().order_by('-created_at')
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
                'updated_at': event.updated_at,
            })
            
        return Response(events_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@token_required
def add_event(request):
    """
    Add a new volunteering event
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'description', 'date', 'time', 'location', 'category', 'spots_total', 'organizer']
        for field in required_fields:
            if field not in data:
                return Response({'error': f'{field} is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a new event
        event = VolunteeringEvent.objects.create(
            title=data['title'],
            description=data['description'],
            date=data['date'],
            time=data['time'],
            location=data['location'],
            category=data['category'],
            spots_total=data['spots_total'],
            organizer=data['organizer'],
            status=data.get('status', 'active')  # Default to 'active' if not provided
        )
        
        return Response({
            'success': True,
            'event': {
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'date': event.date,
                'time': event.time,
                'location': event.location,
                'category': event.category,
                'spots_total': event.spots_total,
                'spots_filled': 0,  # New event, no registrations yet
                'spots_remaining': event.spots_total,
                'organizer': event.organizer,
                'status': event.status,
                'created_at': event.created_at,
                'updated_at': event.updated_at,
            }
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@token_required
def update_event(request, pk):
    """
    Update a volunteering event
    """
    try:
        try:
            event = VolunteeringEvent.objects.get(pk=pk)
        except VolunteeringEvent.DoesNotExist:
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
            
        data = request.data
        
        # Update event fields if provided
        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            event.description = data['description']
        if 'date' in data:
            event.date = data['date']
        if 'time' in data:
            event.time = data['time']
        if 'location' in data:
            event.location = data['location']
        if 'category' in data:
            event.category = data['category']
        if 'spots_total' in data:
            event.spots_total = data['spots_total']
        if 'organizer' in data:
            event.organizer = data['organizer']
        if 'status' in data:
            event.status = data['status']
            
        event.save()
        
        return Response({
            'success': True,
            'event': {
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
                'updated_at': event.updated_at,
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@token_required
def update_event_status(request, pk):
    """
    Update the status of a volunteering event
    """
    try:
        try:
            event = VolunteeringEvent.objects.get(pk=pk)
        except VolunteeringEvent.DoesNotExist:
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
            
        data = request.data
        
        if 'status' not in data:
            return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate status
        if data['status'] not in [status for status, _ in VolunteeringEvent.STATUS_CHOICES]:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
            
        event.status = data['status']
        event.save()
        
        return Response({
            'success': True,
            'event': {
                'id': event.id,
                'status': event.status,
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@token_required
def delete_event(request, pk):
    """
    Delete a volunteering event
    """
    try:
        try:
            event = VolunteeringEvent.objects.get(pk=pk)
        except VolunteeringEvent.DoesNotExist:
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
            
        event_id = event.id  # Store ID before deletion
        event.delete()
        
        return Response({
            'success': True,
            'message': 'Event deleted successfully',
            'id': event_id
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@token_required
def get_event_registrations(request, pk):
    """
    Get all registrations for a specific event
    """
    try:
        try:
            event = VolunteeringEvent.objects.get(pk=pk)
        except VolunteeringEvent.DoesNotExist:
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
            
        registrations = event.registrations.all().order_by('-registration_date')
        registrations_data = []
        
        for registration in registrations:
            registrations_data.append({
                'id': registration.id,
                'name': registration.name,
                'email': registration.email,
                'phone': registration.phone,
                'registration_date': registration.registration_date,
                'status': registration.status,
            })
            
        return Response(registrations_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
