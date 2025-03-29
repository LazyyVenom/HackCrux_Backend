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
from prakirti_admin.models import VolunteeringEvent, EventRegistration, DonationField, Donation
import uuid
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
from django.utils import timezone
import jwt
from django.conf import settings

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

@api_view(['GET', 'PUT'])
@token_required
def user_profile(request):
    """
    GET: Get user profile details
    PUT: Update user profile details
    """
    username = request.username  # Set by token_required decorator
    
    try:
        user = User.objects.get(username=username)
        
        if request.method == 'GET':
            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'name': user.name,
                    'bio': user.bio,
                    'address': user.address,
                    'city': user.city,
                    'state': user.state,
                    'postal_code': user.postal_code,
                    'is_volunteer': user.is_volunteer,
                    'is_organization': user.is_organization,
                    'created_at': user.created_at,
                    'updated_at': user.updated_at
                }
            }, status=status.HTTP_200_OK)
            
        elif request.method == 'PUT':
            data = request.data
            
            # Update fields if provided
            if 'name' in data:
                user.name = data['name']
            if 'bio' in data:
                user.bio = data['bio']
            if 'address' in data:
                user.address = data['address']
            if 'city' in data:
                user.city = data['city']
            if 'state' in data:
                user.state = data['state']
            if 'postal_code' in data:
                user.postal_code = data['postal_code']
                
            # Update password if provided
            if 'current_password' in data and 'new_password' in data:
                if not check_password(data['current_password'], user.password):
                    return Response({'error': 'Current password is incorrect'}, 
                                 status=status.HTTP_400_BAD_REQUEST)
                user.password = make_password(data['new_password'])
                
            user.save()
            
            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'name': user.name,
                    'bio': user.bio,
                    'address': user.address,
                    'city': user.city,
                    'state': user.state,
                    'postal_code': user.postal_code,
                    'is_volunteer': user.is_volunteer,
                    'is_organization': user.is_organization,
                    'created_at': user.created_at,
                    'updated_at': user.updated_at
                }
            }, status=status.HTTP_200_OK)
            
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
def get_donation_fields(request):
    """Get all active donation fields that users can donate to"""
    try:
        fields = DonationField.objects.filter(is_active=True)
        fields_data = []
        
        for field in fields:
            fields_data.append({
                'id': field.id,
                'title': field.title,
                'description': field.description,
                'icon': field.icon,
                'color': field.color,
                'target_amount': field.target_amount,
                'raised_amount': field.raised_amount,
                'progress_percentage': field.progress_percentage
            })
            
        return Response(fields_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@token_required
def create_donation(request):
    """Create a new donation with QR code"""
    try:
        data = request.data
        donation_field_id = data.get('donation_field_id')
        amount = data.get('amount')
        message = data.get('message', '')
        is_anonymous = data.get('is_anonymous', False)
        
        # Validate input
        if not donation_field_id:
            return Response({'error': 'Donation field is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not amount or float(amount) <= 0:
            return Response({'error': 'Valid amount is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the donation field
        try:
            donation_field = DonationField.objects.get(pk=donation_field_id, is_active=True)
        except DonationField.DoesNotExist:
            return Response({'error': 'Invalid donation field'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get the user
        username = request.username
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Generate unique QR code ID
        qr_code_id = str(uuid.uuid4())
        
        # Create the donation record
        donation = Donation.objects.create(
            donation_field=donation_field,
            user=user,
            donor_name='' if is_anonymous else (user.name or user.username),
            donor_email='' if is_anonymous else user.email,
            amount=amount,
            qr_code_id=qr_code_id,
            is_anonymous=is_anonymous,
            message=message,
        )
        
        # Create JWT payload with expiration of 24 hours
        payload = {
            'donation_id': donation.id,
            'amount': str(amount),
            'field_id': donation_field.id,
            'qr_code_id': qr_code_id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        # Sign the payload
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        # Generate QR code with the token URL
        qr_url = f"{settings.FRONTEND_URL}/verify-donation/{token}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer)
        qr_code_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return Response({
            'success': True,
            'donation': {
                'id': donation.id,
                'field_title': donation_field.title,
                'amount': float(donation.amount),
                'qr_code_id': donation.qr_code_id,
                'status': donation.status,
                'created_at': donation.created_at,
                'qr_code_image': qr_code_image,
                'token': token
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
def verify_donation(request, token):
    """Verify donation token and mark donation as completed"""
    try:
        # Decode and verify the JWT token
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({'error': 'Donation link has expired'}, status=status.HTTP_400_BAD_REQUEST)
        except jwt.InvalidTokenError:
            return Response({'error': 'Invalid donation token'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract donation details from payload
        donation_id = payload.get('donation_id')
        qr_code_id = payload.get('qr_code_id')
        
        # Get the donation
        try:
            donation = Donation.objects.get(id=donation_id, qr_code_id=qr_code_id)
        except Donation.DoesNotExist:
            return Response({'error': 'Donation not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if donation is already completed
        if donation.status == 'completed':
            return Response({'message': 'Donation already processed'}, status=status.HTTP_200_OK)
        
        # Update donation status to completed
        donation.status = 'completed'
        donation.completed_at = timezone.now()
        donation.transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        donation.save()
        
        return Response({
            'success': True,
            'message': 'Donation verified and completed successfully',
            'donation': {
                'id': donation.id,
                'field_title': donation.donation_field.title,
                'amount': float(donation.amount),
                'transaction_id': donation.transaction_id,
                'completed_at': donation.completed_at
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
@token_required
def get_user_donations(request):
    """Get all donations made by a user"""
    try:
        # Get the username from the token
        username = request.username
        
        # Get the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all donations for the user
        donations = Donation.objects.filter(user=user).order_by('-created_at')
        
        donations_data = []
        for donation in donations:
            donations_data.append({
                'id': donation.id,
                'field_id': donation.donation_field.id,
                'field_title': donation.donation_field.title,
                'amount': float(donation.amount),
                'status': donation.status,
                'transaction_id': donation.transaction_id,
                'created_at': donation.created_at,
                'completed_at': donation.completed_at
            })
        
        return Response(donations_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
def verify_donation_details(request, token):
    """Get donation details from token without completing the transaction"""
    try:
        # Decode and verify the JWT token
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return Response({'error': 'Donation link has expired'}, status=status.HTTP_400_BAD_REQUEST)
        except jwt.InvalidTokenError:
            return Response({'error': 'Invalid donation token'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract donation details from payload
        donation_id = payload.get('donation_id')
        qr_code_id = payload.get('qr_code_id')
        
        # Get the donation
        try:
            donation = Donation.objects.get(id=donation_id, qr_code_id=qr_code_id)
        except Donation.DoesNotExist:
            return Response({'error': 'Donation not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Return donation details without completing the transaction
        return Response({
            'id': donation.id,
            'field_title': donation.donation_field.title,
            'amount': float(donation.amount),
            'status': donation.status,
            'created_at': donation.created_at
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)