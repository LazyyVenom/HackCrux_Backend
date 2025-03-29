from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Admin, VolunteeringEvent, EventRegistration, DonationField, Donation, ResourceCapacity
from django.utils import timezone
from prakriti_setu.models import User, SosAlert
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

@api_view(['GET', 'PUT'])
@token_required
def admin_profile(request):
    """
    GET: Get admin profile details
    PUT: Update admin profile details
    """
    admin_email = request.username  # Set by token_required decorator
    
    try:
        admin = Admin.objects.get(email=admin_email)
        
        if request.method == 'GET':
            return Response({
                'success': True,
                'admin': {
                    'id': admin.id,
                    'name': admin.name,
                    'email': admin.email,
                    'created_at': admin.created_at,
                    'updated_at': admin.updated_at
                }
            }, status=status.HTTP_200_OK)
            
        elif request.method == 'PUT':
            data = request.data
            
            # Update name if provided
            if 'name' in data:
                admin.name = data['name']
                
            # Update password if provided
            if 'current_password' in data and 'new_password' in data:
                if admin.password != hash_password(data['current_password']):
                    return Response({'error': 'Current password is incorrect'}, 
                                 status=status.HTTP_400_BAD_REQUEST)
                admin.password = hash_password(data['new_password'])
                
            admin.save()
            
            return Response({
                'success': True,
                'admin': {
                    'id': admin.id,
                    'name': admin.name,
                    'email': admin.email,
                    'created_at': admin.created_at,
                    'updated_at': admin.updated_at
                }
            }, status=status.HTTP_200_OK)
            
    except Admin.DoesNotExist:
        return Response({'error': 'Admin not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def initialize_donation_fields(request):
    """Initialize or update donation fields with predefined data"""
    try:
        donation_fields_data = [
            {
                "title": "Disaster Relief Fund",
                "description": "Provides immediate assistance to communities affected by natural disasters like floods and earthquakes.",
                "icon": "LifeBuoy",
                "color": "red",
                "target_amount": 50000,
                "is_active": True
            },
            {
                "title": "Tree Plantation Drive",
                "description": "Support our initiative to plant 10,000 trees across vulnerable ecosystems to combat deforestation.",
                "icon": "Trees",
                "color": "emerald",
                "target_amount": 30000,
                "is_active": True
            },
            {
                "title": "Clean Water Project",
                "description": "Help provide clean drinking water to rural communities through sustainable water management systems.",
                "icon": "Droplet",
                "color": "blue",
                "target_amount": 45000,
                "is_active": True
            },
            {
                "title": "Environmental Education",
                "description": "Fund educational programs that raise awareness about environmental conservation among school children.",
                "icon": "BookOpen",
                "color": "amber",
                "target_amount": 25000,
                "is_active": True
            },
            {
                "title": "Climate Action Fund",
                "description": "Support research and implementation of climate change mitigation strategies in vulnerable regions.",
                "icon": "Leaf",
                "color": "indigo",
                "target_amount": 60000,
                "is_active": True
            },
            {
                "title": "General Donation",
                "description": "Your contribution will be allocated where it's needed most across all our environmental initiatives.",
                "icon": "Heart",
                "color": "purple",
                "target_amount": 0,
                "is_active": True
            }
        ]

        created_count = 0
        updated_count = 0

        for field_data in donation_fields_data:
            field, created = DonationField.objects.update_or_create(
                title=field_data['title'],
                defaults={
                    'description': field_data['description'],
                    'icon': field_data['icon'],
                    'color': field_data['color'],
                    'target_amount': field_data['target_amount'],
                    'is_active': field_data['is_active']
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        return Response({
            'success': True,
            'message': f'Successfully initialized donation fields. Created: {created_count}, Updated: {updated_count}'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@token_required
def get_donations(request):
    """
    Get all donations with fields information
    """
    try:
        donations = Donation.objects.all().order_by('-created_at')
        donations_data = []
        
        for donation in donations:
            # Get the donation field details
            donation_field = donation.donation_field
            
            # Format user information based on anonymity setting
            user_info = {
                'name': 'Anonymous' if donation.is_anonymous else donation.donor_name or (donation.user.name if donation.user else 'Unknown'),
                'email': '' if donation.is_anonymous else donation.donor_email or (donation.user.email if donation.user else ''),
            }
            
            donations_data.append({
                'id': donation.id,
                'field': {
                    'id': donation_field.id,
                    'title': donation_field.title,
                    'description': donation_field.description,
                    'icon': donation_field.icon,
                    'color': donation_field.color,
                },
                'user': user_info,
                'amount': float(donation.amount),
                'transaction_id': donation.transaction_id,
                'status': donation.status,
                'is_anonymous': donation.is_anonymous,
                'message': donation.message,
                'created_at': donation.created_at,
                'completed_at': donation.completed_at,
            })
            
        return Response(donations_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@token_required
def get_donation_fields(request):
    """
    Get all donation fields with their statistics
    """
    try:
        fields = DonationField.objects.all().order_by('title')
        fields_data = []
        
        for field in fields:
            fields_data.append({
                'id': field.id,
                'title': field.title,
                'description': field.description,
                'icon': field.icon,
                'color': field.color,
                'target_amount': float(field.target_amount),
                'raised_amount': float(field.raised_amount),
                'progress_percentage': field.progress_percentage,
                'is_active': field.is_active,
                'created_at': field.created_at,
                'updated_at': field.updated_at,
            })
            
        return Response(fields_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@token_required
def update_donation_status(request, pk):
    """
    Update the status of a donation
    """
    try:
        try:
            donation = Donation.objects.get(pk=pk)
        except Donation.DoesNotExist:
            return Response({'error': 'Donation not found'}, status=status.HTTP_404_NOT_FOUND)
            
        data = request.data
        
        if 'status' not in data:
            return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate status
        valid_statuses = [s[0] for s in Donation.STATUS_CHOICES]
        if data['status'] not in valid_statuses:
            return Response({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}, 
                          status=status.HTTP_400_BAD_REQUEST)
            
        donation.status = data['status']
        
        # If status is changed to completed, update completed_at timestamp
        if data['status'] == 'completed' and not donation.completed_at:
            
            donation.completed_at = timezone.now()
            
        donation.save()
        
        return Response({
            'success': True,
            'donation': {
                'id': donation.id,
                'status': donation.status,
                'completed_at': donation.completed_at,
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
@token_required
def admin_get_all_sos_alerts(request):
    """Get all SOS alerts with additional details for admin dashboard"""
    try:
        # Verify admin access
        username = request.username
        try:
            admin = Admin.objects.get(email=username)
        except Admin.DoesNotExist:
            # Check if the user is an organization with admin privileges
            try:
                user = User.objects.get(username=username)
                if not user.is_organization:
                    return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
                
        # Get all SOS alerts, including resolved and false alarms
        alerts = SosAlert.objects.all().order_by('-created_at')
        
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'id': alert.id,
                'user': {
                    'id': alert.user.id,
                    'username': alert.user.username,
                    'name': alert.user.name or alert.user.username,
                    'contact_number': alert.contact_number or 'Not provided'
                },
                'latitude': alert.latitude,
                'longitude': alert.longitude,
                'location_name': alert.location_name,
                'city': alert.city,
                'country': alert.country,
                'message': alert.message,
                'status': alert.status,
                'created_at': alert.created_at,
                'updated_at': alert.updated_at,
                'resolved_at': alert.resolved_at
            })
            
        return Response(alerts_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
@token_required
def admin_get_sos_alerts_by_city(request):
    """Get all SOS alerts grouped by city for admin dashboard"""
    try:
        # Verify admin access
        username = request.username
        try:
            admin = Admin.objects.get(email=username)
        except Admin.DoesNotExist:
            # Check if the user is an organization with admin privileges
            try:
                user = User.objects.get(username=username)
                if not user.is_organization:
                    return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
                
        # Get active SOS alerts grouped by city
        alerts = SosAlert.objects.filter(status='active').order_by('-created_at')
            
        # Group by city
        cities = {}
        for alert in alerts:
            city_name = alert.city
            if city_name not in cities:
                cities[city_name] = {
                    'city': city_name,
                    'country': alert.country,
                    'count': 0,
                    'alerts': []
                }
                
            cities[city_name]['count'] += 1
            cities[city_name]['alerts'].append({
                'id': alert.id,
                'user': {
                    'id': alert.user.id,
                    'username': alert.user.username,
                    'name': alert.user.name or alert.user.username
                },
                'latitude': alert.latitude,
                'longitude': alert.longitude,
                'location_name': alert.location_name,
                'message': alert.message,
                'contact_number': alert.contact_number,
                'created_at': alert.created_at
            })
            
        # Convert dictionary to list
        result = list(cities.values())
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
@token_required
def admin_get_sos_alerts_by_city_name(request, city):
    """Get all SOS alerts for a specific city"""
    try:
        # Verify admin access
        username = request.username
        try:
            admin = Admin.objects.get(email=username)
        except Admin.DoesNotExist:
            # Check if the user is an organization with admin privileges
            try:
                user = User.objects.get(username=username)
                if not user.is_organization:
                    return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
                
        # Get active SOS alerts for the specified city
        alerts = SosAlert.objects.filter(status='active', city__iexact=city).order_by('-created_at')
        
        if not alerts:
            return Response([], status=status.HTTP_200_OK)
            
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'id': alert.id,
                'user': {
                    'id': alert.user.id,
                    'username': alert.user.username,
                    'name': alert.user.name or alert.user.username,
                    'contact_number': alert.contact_number or 'Not provided'
                },
                'latitude': alert.latitude,
                'longitude': alert.longitude,
                'location_name': alert.location_name,
                'message': alert.message,
                'created_at': alert.created_at,
                'updated_at': alert.updated_at
            })
            
        return Response(alerts_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['PUT'])
@token_required
def admin_update_sos_alert_status(request, alert_id):
    """Update status of a SOS alert (respond, resolve, etc.)"""
    try:
        # Verify admin access
        username = request.username
        try:
            admin = Admin.objects.get(email=username)
        except Admin.DoesNotExist:
            # Check if the user is an organization with admin privileges
            try:
                user = User.objects.get(username=username)
                if not user.is_organization:
                    return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
                
        # Get the SOS alert
        try:
            sos_alert = SosAlert.objects.get(pk=alert_id)
        except SosAlert.DoesNotExist:
            return Response({'error': 'SOS alert not found'}, status=status.HTTP_404_NOT_FOUND)
            
        # Update status
        data = request.data
        new_status = data.get('status')
        
        if not new_status or new_status not in ['active', 'responding', 'resolved', 'false_alarm']:
            return Response({'error': 'Invalid status. Must be active, responding, resolved, or false_alarm'}, 
                           status=status.HTTP_400_BAD_REQUEST)
                           
        # Update the alert
        sos_alert.status = new_status
        
        # Set resolved_at if status is changing to resolved or false_alarm
        if new_status in ['resolved', 'false_alarm'] and sos_alert.status != 'resolved':
            sos_alert.resolved_at = timezone.now()
            
        sos_alert.save()
        
        return Response({
            'success': True,
            'message': f'SOS alert status updated to {new_status}',
            'alert': {
                'id': sos_alert.id,
                'status': sos_alert.status,
                'updated_at': sos_alert.updated_at,
                'resolved_at': sos_alert.resolved_at
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
@token_required
def admin_get_sos_statistics(request):
    """Get SOS alert statistics for admin dashboard"""
    try:
        # Verify admin access
        username = request.username
        try:
            admin = Admin.objects.get(email=username)
        except Admin.DoesNotExist:
            # Check if the user is an organization with admin privileges
            try:
                user = User.objects.get(username=username)
                if not user.is_organization:
                    return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
                
        # Get statistics
        total_alerts = SosAlert.objects.count()
        active_alerts = SosAlert.objects.filter(status='active').count()
        responding_alerts = SosAlert.objects.filter(status='responding').count()
        resolved_alerts = SosAlert.objects.filter(status='resolved').count()
        false_alarm_alerts = SosAlert.objects.filter(status='false_alarm').count()
        
        # Get cities with active alerts
        cities_with_alerts = SosAlert.objects.filter(status='active').values('city').distinct().count()
        
        # Count high priority alerts (3+ alerts in same city)
        city_alert_counts = {}
        for alert in SosAlert.objects.filter(status='active'):
            city = alert.city
            if city not in city_alert_counts:
                city_alert_counts[city] = 0
            city_alert_counts[city] += 1
        
        high_priority_count = sum(1 for count in city_alert_counts.values() if count >= 3)
        
        return Response({
            'total_alerts': total_alerts,
            'active_alerts': active_alerts,
            'responding': responding_alerts,
            'resolved': resolved_alerts,
            'false_alarms': false_alarm_alerts,
            'total_cities': cities_with_alerts,
            'high_priority': high_priority_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['PUT'])
@token_required
def admin_update_sos_alert_status_by_city(request, city):
    """Update status of all SOS alerts in a specific city"""
    try:
        # Verify admin access
        username = request.username
        try:
            admin = Admin.objects.get(email=username)
        except Admin.DoesNotExist:
            # Check if the user is an organization with admin privileges
            try:
                user = User.objects.get(username=username)
                if not user.is_organization:
                    return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
                
        # Update status
        data = request.data
        new_status = data.get('status')
        
        if not new_status or new_status not in ['active', 'responding', 'resolved', 'false_alarm']:
            return Response({'error': 'Invalid status. Must be active, responding, resolved, or false_alarm'}, 
                           status=status.HTTP_400_BAD_REQUEST)
                           
        # Get all active SOS alerts for the city
        alerts = SosAlert.objects.filter(city__iexact=city, status='active')
        
        if not alerts:
            return Response({'error': f'No active SOS alerts found for {city}'}, status=status.HTTP_404_NOT_FOUND)
            
        # Update all alerts
        updated_count = 0
        updated_ids = []
        current_time = timezone.now()
        
        for alert in alerts:
            alert.status = new_status
            
            # Set resolved_at if status is changing to resolved or false_alarm
            if new_status in ['resolved', 'false_alarm']:
                alert.resolved_at = current_time
                
            alert.save()
            updated_count += 1
            updated_ids.append(alert.id)
            
        return Response({
            'success': True,
            'message': f'Updated {updated_count} SOS alerts in {city} to {new_status}',
            'updated_alerts': {
                'count': updated_count,
                'ids': updated_ids,
                'city': city,
                'status': new_status
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@token_required
def get_resources(request):
    """
    Get all resource capacities
    """
    try:
        resources = ResourceCapacity.objects.all().order_by('resource_type', 'state', 'city')
        resources_data = []
        
        for resource in resources:
            resources_data.append({
                'id': resource.id,
                'resource_type': resource.resource_type,
                'name': resource.name,
                'total_capacity': resource.total_capacity,
                'available_capacity': resource.available_capacity,
                'state': resource.state,
                'city': resource.city,
                'created_at': resource.created_at,
                'updated_at': resource.updated_at,
            })
            
        return Response(resources_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@token_required
def get_resources_by_type(request, resource_type):
    """
    Get resources filtered by type
    """
    try:
        resources = ResourceCapacity.objects.filter(resource_type=resource_type).order_by('state', 'city')
        resources_data = []
        
        for resource in resources:
            resources_data.append({
                'id': resource.id,
                'resource_type': resource.resource_type,
                'name': resource.name,
                'total_capacity': resource.total_capacity,
                'available_capacity': resource.available_capacity,
                'state': resource.state,
                'city': resource.city,
                'created_at': resource.created_at,
                'updated_at': resource.updated_at,
            })
            
        return Response(resources_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@token_required
def get_resources_by_location(request):
    """
    Get resources filtered by state and/or city
    """
    try:
        # Get query parameters
        state = request.query_params.get('state', '')
        city = request.query_params.get('city', '')
        
        # Filter resources
        query_filter = {}
        if state:
            query_filter['state__iexact'] = state
        if city:
            query_filter['city__iexact'] = city
            
        if not query_filter:
            return Response({'error': 'Please provide state and/or city parameters'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        resources = ResourceCapacity.objects.filter(**query_filter).order_by('resource_type')
        resources_data = []
        
        for resource in resources:
            resources_data.append({
                'id': resource.id,
                'resource_type': resource.resource_type,
                'name': resource.name,
                'total_capacity': resource.total_capacity,
                'available_capacity': resource.available_capacity,
                'state': resource.state,
                'city': resource.city,
                'created_at': resource.created_at,
                'updated_at': resource.updated_at,
            })
            
        return Response(resources_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@token_required
def add_resource(request):
    """
    Add a new resource capacity
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['resource_type', 'name', 'total_capacity', 'available_capacity', 'state', 'city']
        for field in required_fields:
            if field not in data:
                return Response({'error': f'{field} is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate capacity values
        if int(data['available_capacity']) > int(data['total_capacity']):
            return Response({'error': 'Available capacity cannot exceed total capacity'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Create a new resource
        resource = ResourceCapacity.objects.create(
            resource_type=data['resource_type'],
            name=data['name'],
            total_capacity=data['total_capacity'],
            available_capacity=data['available_capacity'],
            state=data['state'],
            city=data['city']
        )
        
        return Response({
            'success': True,
            'resource': {
                'id': resource.id,
                'resource_type': resource.resource_type,
                'name': resource.name,
                'total_capacity': resource.total_capacity,
                'available_capacity': resource.available_capacity,
                'state': resource.state,
                'city': resource.city,
                'created_at': resource.created_at,
                'updated_at': resource.updated_at,
            }
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@token_required
def update_resource(request, pk):
    """
    Update a resource capacity
    """
    try:
        try:
            resource = ResourceCapacity.objects.get(pk=pk)
        except ResourceCapacity.DoesNotExist:
            return Response({'error': 'Resource not found'}, status=status.HTTP_404_NOT_FOUND)
            
        data = request.data
        
        # Update resource fields if provided
        if 'resource_type' in data:
            resource.resource_type = data['resource_type']
        if 'name' in data:
            resource.name = data['name']
        if 'total_capacity' in data:
            resource.total_capacity = data['total_capacity']
        if 'available_capacity' in data:
            resource.available_capacity = data['available_capacity']
        if 'state' in data:
            resource.state = data['state']
        if 'city' in data:
            resource.city = data['city']
            
        # Validate capacity values
        if resource.available_capacity > resource.total_capacity:
            return Response({'error': 'Available capacity cannot exceed total capacity'}, 
                           status=status.HTTP_400_BAD_REQUEST)
            
        resource.save()
        
        return Response({
            'success': True,
            'resource': {
                'id': resource.id,
                'resource_type': resource.resource_type,
                'name': resource.name,
                'total_capacity': resource.total_capacity,
                'available_capacity': resource.available_capacity,
                'state': resource.state,
                'city': resource.city,
                'created_at': resource.created_at,
                'updated_at': resource.updated_at,
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@token_required
def delete_resource(request, pk):
    """
    Delete a resource capacity
    """
    try:
        try:
            resource = ResourceCapacity.objects.get(pk=pk)
        except ResourceCapacity.DoesNotExist:
            return Response({'error': 'Resource not found'}, status=status.HTTP_404_NOT_FOUND)
            
        resource_id = resource.id  # Store ID before deletion
        resource.delete()
        
        return Response({
            'success': True,
            'message': 'Resource capacity deleted successfully',
            'id': resource_id
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)