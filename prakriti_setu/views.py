from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from .models import User, SosAlert
from django.views.decorators.csrf import csrf_exempt
from .utils import generate_jwt_token, token_required  # Import our JWT utilities
from prakirti_admin.models import VolunteeringEvent, EventRegistration, DonationField, Donation, Admin
from .api_utils import callGPT, get_location_info,fetch_disaster_news
import uuid
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
from django.utils import timezone
import jwt
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Sum, Count, Avg, Max
from .call_gemini import get_environmental_metrics
from bs4 import BeautifulSoup
from facebook_scraper import get_posts
import traceback
import time
import random
import requests

# Add this new function to scrape Facebook posts related to disasters
def scrape_facebook_disaster_posts(pages=5, disaster_keywords=None):
    """
    Scrape Facebook public pages for disaster-related posts
    """
    if disaster_keywords is None:
        disaster_keywords = [
            'flood', 'earthquake', 'hurricane', 'tornado', 'wildfire', 'tsunami', 
            'landslide', 'drought', 'cyclone', 'disaster', 'emergency', 'evacuation', 
            'relief', 'rescue', 'damage', 'crisis', 'alert', 'warning'
        ]
    
    # Public Facebook pages related to disaster management/news to scrape
    disaster_pages = [
        'ndmaindia',       # National Disaster Management Authority, India
        'NWSIndianapolis', # National Weather Service
        'NIDM.MHA.India',  # National Institute of Disaster Management
        'CMRFKerala',      # Kerala Chief Minister's Distress Relief Fund
        'DDNewslive',      # Doordarshan News
        'airnewsalerts',   # All India Radio News
        'RedCrossIndia',   # Red Cross India
        'UNICEF'           # UNICEF
    ]
    
    disaster_posts = []
    
    import os
    # Get the current directory (where views.py is located)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to facebook.json in the same directory
    facebook_cookies_path = os.path.join(current_dir, 'facebook.json')
    
    print(f"Looking for Facebook cookies at: {facebook_cookies_path}")
    
    for page in disaster_pages:
        try:
            # Add a delay to avoid rate limiting
            time.sleep(2)
            
            # Try to scrape posts from the page with cookies if the file exists
            try:
                if os.path.exists(facebook_cookies_path):
                    print(f"Using Facebook cookies from: {facebook_cookies_path}")
                    posts = list(get_posts(page, pages=2, cookies=facebook_cookies_path))
                else:
                    # If cookies file doesn't exist, try without cookies
                    print(f"Warning: {facebook_cookies_path} not found. Attempting to scrape without cookies.")
                    posts = list(get_posts(page, pages=1))  # Reduced pages when no cookies to avoid blocking
            except FileNotFoundError as e:
                # Fall back to scraping without cookies
                print(f"Error finding cookie file: {e}")
                print(f"Attempting to scrape without cookies.")
                posts = list(get_posts(page, pages=1))  # Reduced pages when no cookies to avoid blocking
            
            for post in posts:
                # Skip posts without text
                if not post.get('text'):
                    continue
                
                # Check if post contains disaster-related keywords
                if any(keyword.lower() in post.get('text', '').lower() for keyword in disaster_keywords):
                    # Determine importance based on keywords in the text
                    importance = 'normal'
                    if any(keyword.lower() in post.get('text', '').lower() 
                           for keyword in ['emergency', 'evacuate', 'evacuating', 'evacuation', 'urgent', 'immediate']):
                        importance = 'very-important'
                    elif any(keyword.lower() in post.get('text', '').lower() 
                            for keyword in ['warning', 'alert', 'caution', 'prepare', 'advise']):
                        importance = 'mild-important'
                    
                    # Try to extract location information from the post
                    location = 'India'  # Default location
                    indian_states = [
                        'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
                        'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
                        'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
                        'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana',
                        'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal'
                    ]
                    
                    # Look for state names in the post text
                    for state in indian_states:
                        if state.lower() in post.get('text', '').lower():
                            location = state
                            break
                    
                    # Extract post time or use current time
                    post_time = post.get('time', datetime.now())
                    time_ago = "Just now"
                    if post_time:
                        # Calculate time ago
                        time_diff = datetime.now() - post_time
                        if time_diff.days > 0:
                            time_ago = f"{time_diff.days} days ago"
                        elif time_diff.seconds // 3600 > 0:
                            time_ago = f"{time_diff.seconds // 3600} hours ago"
                        else:
                            time_ago = f"{time_diff.seconds // 60} minutes ago"
                    
                    # Add the post to our disaster posts list
                    disaster_posts.append({
                        'title': post.get('text', '')[:100] + ('...' if len(post.get('text', '')) > 100 else ''),
                        'source': f"Facebook - {page}",
                        'type': 'social',
                        'importance': importance,
                        'timestamp': time_ago,
                        'state': location,
                        'description': post.get('text'),
                        'url': post.get('post_url', '#'),
                        'author': post.get('username', 'Facebook User'),
                        'imageUrl': post.get('image', 'https://images.unsplash.com/photo-1590856029826-c7a73142bbf1?q=80&w=2073&auto=format&fit=crop')
                    })
        except Exception as e:
            print(f"Error scraping Facebook page {page}: {str(e)}")
            traceback.print_exc()
    
    # If Facebook scraping failed or returned no results, generate mock data
    if not disaster_posts:
        print("Facebook scraping failed or returned no data. Generating mock data...")
        disaster_posts = generate_mock_facebook_posts(10)
    
    return disaster_posts

def generate_mock_facebook_posts(count=10):
    """Generate mock Facebook posts for testing when scraping fails"""
    mock_posts = []
    
    disaster_types = ['flood', 'earthquake', 'wildfire', 'landslide', 'cyclone']
    states = ['Kerala', 'Tamil Nadu', 'Karnataka', 'Rajasthan', 'Gujarat', 'Maharashtra', 'Andhra Pradesh']
    
    disaster_templates = [
        "ALERT: {disaster} warning issued for {location}. Please stay safe and follow evacuation orders.",
        "UPDATE: {disaster} situation in {location} worsening. Emergency services on high alert.",
        "Volunteers needed: {disaster} relief operations in {location}. Please contact local authorities.",
        "BREAKING: {disaster} reported in {location}. Residents advised to stay indoors.",
        "Relief camps set up in {location} for {disaster} victims. Donations needed.",
        "Road closures in {location} due to {disaster}. Avoid travel if possible.",
        "Schools closed in {location} due to {disaster} warning. Stay updated with official announcements.",
        "Weather update: High risk of {disaster} in {location} over next 24 hours.",
        "Emergency response teams deployed to {location} for {disaster} relief.",
        "Community support growing for {disaster} victims in {location}. How you can help:"
    ]
    
    for i in range(count):
        disaster = random.choice(disaster_types)
        state = random.choice(states)
        importance = random.choice(['normal', 'mild-important', 'very-important'])
        template = random.choice(disaster_templates)
        
        # Generate post text
        post_text = template.format(disaster=disaster, location=state)
        
        # Generate random time ago
        hours = random.randint(1, 12)
        time_ago = f"{hours} hours ago"
        
        mock_posts.append({
            'title': post_text[:100] + ('...' if len(post_text) > 100 else ''),
            'source': f"Facebook - DisasterWatch",
            'type': 'social',
            'importance': importance,
            'timestamp': time_ago,
            'state': state,
            'description': post_text + " " + "Please follow official guidance and stay informed through local news channels. #StaySafe #DisasterResponse",
            'url': '#',
            'author': 'DisasterWatch',
            'imageUrl': f'https://source.unsplash.com/random/800x600?{disaster}'
        })
    
    return mock_posts

@csrf_exempt
@api_view(['GET'])
def get_social_disaster_news(request):
    """Get disaster-related posts from social media"""
    try:
        # Get parameter for number of posts to return
        count = int(request.GET.get('count', 10))
        
        # Get disaster posts from Facebook
        disaster_posts = scrape_facebook_disaster_posts()
        
        # Limit the number of posts returned
        limited_posts = disaster_posts[:count]
        
        # Add unique IDs to each post
        for i, post in enumerate(limited_posts):
            post['id'] = f"social-{i+1}"
        
        return Response(limited_posts, status=status.HTTP_200_OK)
    except Exception as e:
        print(f"Error getting social disaster news: {str(e)}")
        traceback.print_exc()
        
        # If there's an error, generate and return mock data
        mock_posts = generate_mock_facebook_posts(count=10)
        for i, post in enumerate(mock_posts):
            post['id'] = f"social-mock-{i+1}"
            
        return Response(mock_posts, status=status.HTTP_200_OK)

# Function to combine news from different sources with proper categorization
@csrf_exempt
@api_view(['GET'])
def get_combined_disaster_news(request):
    """Get combined disaster news from multiple sources"""
    try:
        # Get parameters
        count = int(request.GET.get('count', 20))
        sources = request.GET.get('sources', 'all')  # all, news, social
        state = request.GET.get('state', 'All States')
        
        all_news = []
        
        # Get national news if sources is 'all' or 'news'
        if sources in ['all', 'news']:
            try:
                # Use existing national news API
                news_response = scrape_hindu_national_news(pages=3)
                # Process and filter for disaster news
                disaster_news = analyze_news_for_disasters(news_response, limit=count)
                
                # If analysis fails or returns too few results, use keyword filtering
                if len(disaster_news) < 5:
                    disaster_news = filter_disaster_related_news(news_response, limit=count)
                
                # Process for frontend display
                for i, article in enumerate(disaster_news):
                    if article['title'] == "N/A" or article['article_url'] == "N/A":
                        continue
                    
                    # Determine importance
                    severity = article.get('importance', 'normal')
                    if not severity in ['very-important', 'mild-important', 'normal']:
                        severity = 'normal'
                        if any(keyword in article['title'].lower() for keyword in 
                              ['disaster', 'flood', 'earthquake', 'crisis', 'emergency', 'alert', 'warning']):
                            severity = 'very-important'
                        elif any(keyword in article['title'].lower() for keyword in 
                                ['damage', 'risk', 'danger', 'threat', 'concern', 'issue']):
                            severity = 'mild-important'
                    
                    # Create formatted news item
                    all_news.append({
                        'id': f"news-{i+1}",
                        'title': article['title'],
                        'source': 'The Hindu',
                        'type': 'news',
                        'importance': severity,
                        'timestamp': '24 hours ago',
                        'state': article.get('category', 'National') if article.get('category') != 'N/A' else 'National',
                        'description': article.get('description', f"Disaster update from {article.get('category', 'National')} category."),
                        'url': article['article_url'],
                        'author': article.get('author', 'The Hindu Staff') if article.get('author') != 'N/A' else 'The Hindu Staff',
                        'imageUrl': 'https://images.unsplash.com/photo-1546422904-90eab23c3d7e?q=80&w=2972&auto=format&fit=crop'
                    })
            except Exception as e:
                print(f"Error getting news articles: {str(e)}")
                traceback.print_exc()
        
        # Get social media posts if sources is 'all' or 'social'
        if sources in ['all', 'social']:
            try:
                # Get disaster posts from social media
                social_posts = scrape_facebook_disaster_posts()
                
                # Add to all news
                for i, post in enumerate(social_posts):
                    post['id'] = f"social-{i+1}"
                    all_news.append(post)
            except Exception as e:
                print(f"Error getting social posts: {str(e)}")
                traceback.print_exc()
        
        # Filter by state if specified
        if state != 'All States':
            filtered_news = [
                item for item in all_news if 
                item['state'] == state or 
                item['state'].lower() == state.lower() or
                'National' in item['state']
            ]
        else:
            filtered_news = all_news
        
        # Sort by importance and recency
        importance_order = {'very-important': 0, 'mild-important': 1, 'normal': 2}
        sorted_news = sorted(
            filtered_news, 
            key=lambda x: (importance_order.get(x['importance'], 3), 0 if 'just now' in x.get('timestamp', '').lower() else 1)
        )
        
        # Limit to requested count
        limited_news = sorted_news[:count]
        
        return Response(limited_news, status=status.HTTP_200_OK)
    except Exception as e:
        print(f"Error getting combined disaster news: {str(e)}")
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        
        if not donation_id or not qr_code_id:
            return Response({'error': 'Missing donation details in token'}, status=status.HTTP_400_BAD_REQUEST)
        
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
        # More detailed error logging
        import traceback
        print(f"Error in verify_donation_details: {str(e)}")
        print(traceback.format_exc())
        return Response({'error': f'Error verifying donation: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@token_required
def create_sos_alert(request):
    """Create a new SOS alert"""
    try:
        data = request.data
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        location_name = data.get('location_name')
        city = data.get('city')
        country = data.get('country')
        message = data.get('message', '')
        contact_number = data.get('contact_number', '')
        
        # Validate required fields
        if not all([latitude, longitude, city, country]):
            return Response({
                'error': 'Latitude, longitude, city and country are required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Get the user from the token
        username = request.username
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
        # Create SOS alert
        sos_alert = SosAlert.objects.create(
            user=user,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name or f"{city}, {country}",
            city=city,
            country=country,
            message=message,
            contact_number=contact_number,
            status='active'
        )
        
        # Send email notification to admins
        send_sos_email_notification(sos_alert, user)
        
        return Response({
            'success': True,
            'message': 'SOS alert created successfully',
            'alert': {
                'id': sos_alert.id,
                'latitude': sos_alert.latitude,
                'longitude': sos_alert.longitude,
                'location_name': sos_alert.location_name,
                'city': sos_alert.city,
                'country': sos_alert.country,
                'status': sos_alert.status,
                'created_at': sos_alert.created_at
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def send_sos_email_notification(sos_alert, user):
    """Send email notification to admins for SOS alert"""
    try:
        # Get all admin emails
        admin_emails = list(Admin.objects.values_list('email', flat=True))
        
        # Get organization users who can also handle SOS alerts
        org_emails = list(User.objects.filter(is_organization=True).values_list('email', flat=True))
        
        # Combine email lists
        recipient_emails = admin_emails + org_emails
        
        # Remove duplicates
        recipient_emails = list(set(recipient_emails))
        
        if not recipient_emails:
            # Log that no recipients were found
            print("Warning: No admin or organization emails found for SOS alert notification")
            return
            
        # Format created_at time in a human-readable format
        formatted_time = sos_alert.created_at.strftime("%B %d, %Y at %I:%M %p")
        
        # Prepare context for email template
        context = {
            'alert_id': sos_alert.id,
            'username': user.name or user.username,
            'location_name': sos_alert.location_name,
            'city': sos_alert.city,
            'country': sos_alert.country,
            'latitude': sos_alert.latitude,
            'longitude': sos_alert.longitude,
            'contact_number': sos_alert.contact_number or "Not provided",
            'message': sos_alert.message or "No message provided",
            'created_at': formatted_time,
            'dashboard_url': f"{settings.FRONTEND_URL}/admin/sos-tracker"
        }
        
        # Render HTML content using the template
        html_content = render_to_string('email.html', context)
        
        # Create plain text version of the email
        text_content = strip_tags(html_content)
        
        # Create email
        subject = f"URGENT: SOS Alert from {user.name or user.username} in {sos_alert.city}"
        from_email = settings.DEFAULT_FROM_EMAIL
        
        # Create message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=recipient_emails
        )
        
        # Attach HTML content
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send()
        
        print(f"SOS alert email notification sent to {len(recipient_emails)} recipients")
        
    except Exception as e:
        # Log the error but don't fail the request
        print(f"Error sending SOS alert email notification: {str(e)}")

@csrf_exempt
@api_view(['GET'])
@token_required
def get_user_sos_alerts(request):
    """Get all SOS alerts created by the current user"""
    try:
        # Get the username from the token
        username = request.username
        
        # Get the user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
        # Get all SOS alerts for the user
        sos_alerts = SosAlert.objects.filter(user=user).order_by('-created_at')
        
        alerts_data = []
        for alert in sos_alerts:
            alerts_data.append({
                'id': alert.id,
                'latitude': alert.latitude,
                'longitude': alert.longitude,
                'location_name': alert.location_name,
                'city': alert.city,
                'country': alert.country,
                'message': alert.message,
                'contact_number': alert.contact_number,
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
def get_all_active_sos_alerts(request):
    """Get all active SOS alerts (only accessible by organizations and admins)"""
    try:
        # Get the username from the token
        username = request.username
        
        # Check if the user is an organization or admin
        is_authorized = False
        
        try:
            # First check if user exists in User model
            user = User.objects.get(username=username)
            if user.is_organization:
                is_authorized = True
                print(f"User {username} is an organization, granting access")
        except User.DoesNotExist:
            # Check if user is an admin by email
            try:
                if '@' in username:
                    admin = Admin.objects.get(email=username)
                    is_authorized = True
                    print(f"User {username} is an admin, granting access")
            except Admin.DoesNotExist:
                print(f"User {username} not found in Admin table")
        
        # For development purposes, temporarily allow access
        # REMOVE THIS IN PRODUCTION
        is_authorized = True
        
        if not is_authorized:
            print(f"Unauthorized access attempt by: {username}")
            return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            
        # Get all active SOS alerts
        sos_alerts = SosAlert.objects.filter(status='active').order_by('-created_at')
        
        alerts_data = []
        for alert in sos_alerts:
            alerts_data.append({
                'id': alert.id,
                'user': {
                    'id': alert.user.id,
                    'name': alert.user.name or alert.user.username,
                    'username': alert.user.username
                },
                'latitude': alert.latitude,
                'longitude': alert.longitude,
                'location_name': alert.location_name,
                'city': alert.city,
                'country': alert.country,
                'message': alert.message,
                'contact_number': alert.contact_number,
                'status': alert.status,
                'created_at': alert.created_at,
                'updated_at': alert.updated_at
            })
            
        return Response(alerts_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Error in get_all_active_sos_alerts: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['PUT'])
@token_required
def update_sos_alert_status(request, alert_id):
    """Update the status of an SOS alert"""
    try:
        # Get the username from the token
        username = request.username
        
        # Get the SOS alert
        try:
            sos_alert = SosAlert.objects.get(pk=alert_id)
        except SosAlert.DoesNotExist:
            return Response({'error': 'SOS alert not found'}, status=status.HTTP_404_NOT_FOUND)
            
        # Check if the user is the creator of the alert, an organization, or an admin
        is_authorized = False
        try:
            user = User.objects.get(username=username)
            if user.id == sos_alert.user.id or user.is_organization:
                is_authorized = True
        except User.DoesNotExist:
            # Check if user is an admin
            try:
                Admin.objects.get(email=username)
                is_authorized = True
            except Admin.DoesNotExist:
                pass
                
        if not is_authorized:
            return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            
        # Update the status
        data = request.data
        new_status = data.get('status')
        
        if not new_status:
            return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        if new_status not in [status for status, _ in SosAlert.STATUS_CHOICES]:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
            
        sos_alert.status = new_status
        
        # If status is being changed to 'resolved', update resolved_at timestamp
        if new_status == 'resolved' and not sos_alert.resolved_at:
            sos_alert.resolved_at = timezone.now()
            
        sos_alert.save()
        
        return Response({
            'success': True,
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
def get_sos_alerts_by_city(request):
    """Get SOS alerts grouped by city (only accessible by organizations and admins)"""
    try:
        # Get the username from the token
        username = request.username
        
        # Check if the user is an organization or admin
        is_authorized = False
        
        try:
            # First check if user exists in User model
            user = User.objects.get(username=username)
            if user.is_organization:
                is_authorized = True
                print(f"User {username} is an organization, granting access")
        except User.DoesNotExist:
            # Check if user is an admin by email
            try:
                if '@' in username:
                    admin = Admin.objects.get(email=username)
                    is_authorized = True
                    print(f"User {username} is an admin, granting access")
            except Admin.DoesNotExist:
                print(f"User {username} not found in Admin table")
        
        # For development purposes, temporarily allow access
        # REMOVE THIS IN PRODUCTION
        is_authorized = True
        
        if not is_authorized:
            print(f"Unauthorized access attempt by: {username}")
            return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
            
        # Get all active SOS alerts
        sos_alerts = SosAlert.objects.filter(status='active').order_by('-created_at')
        
        # Group by city
        cities = {}
        for alert in sos_alerts:
            city = alert.city
            if city not in cities:
                cities[city] = {
                    'city': city,
                    'country': alert.country,
                    'count': 0,
                    'alerts': []
                }
                
            cities[city]['count'] += 1
            cities[city]['alerts'].append({
                'id': alert.id,
                'user': {
                    'id': alert.user.id,
                    'name': alert.user.name or alert.user.username,
                    'username': alert.user.username
                },
                'latitude': alert.latitude,
                'longitude': alert.longitude,
                'location_name': alert.location_name,
                'city': alert.city,
                'country': alert.country,
                'message': alert.message,
                'contact_number': alert.contact_number,
                'status': alert.status,
                'created_at': alert.created_at,
                'updated_at': alert.updated_at
            })
            
        # Convert dictionary to list
        result = list(cities.values())
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Error in get_sos_alerts_by_city: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@token_required
def get_location_details(request):
    """Get detailed information about a location"""
    try:
        data = request.data
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        city = data.get('city', 'Unknown')
        country = data.get('country', 'Unknown')
        location_string = f"{city}, {country}"

        # Set default threat levels (fallback)
        default_response = {
            "threat_levels": {
                "flood_risk": {
                    "level": "Low",
                    "icon": "Droplet",
                    "color": "border-blue-500",
                    "bgColor": "bg-blue-900/30"
                },
                "fire_danger": {
                    "level": "Low",
                    "icon": "Activity", 
                    "color": "border-red-500",
                    "bgColor": "bg-red-900/30"
                },
                "air_quality": {
                    "level": "Good",
                    "icon": "Wind",
                    "color": "border-purple-500",
                    "bgColor": "bg-purple-900/30"
                },
                "drought_level": {
                    "level": "Low",
                    "icon": "AlertTriangle",
                    "color": "border-amber-500",
                    "bgColor": "bg-amber-900/30"
                },
                "seismic_activity": {
                    "level": "Low",
                    "icon": "Activity",
                    "color": "border-emerald-500",
                    "bgColor": "bg-emerald-900/30"
                }
            },
            "weather": {
                "condition": "Clear",
                "temperature": "25°C",
                "forecast": "Stable conditions expected"
            },
            "emergency_contacts": {
                "police": "100",
                "ambulance": "108",
                "fire": "101",
                "disaster_management": "1078"
            },
            "disaster_risks": [
                {
                    "type": "General",
                    "severity": "Low",
                    "description": "No immediate risks detected"
                }
            ],
            "safety_tips": [
                "Stay informed about local weather conditions",
                "Keep emergency contact numbers handy",
                "Maintain an emergency kit"
            ],
            "recent_disasters": []
        }

        try:
            # Set system prompt for GPT
            system_prompt = """You are a disaster management expert. Provide a complete JSON response with:
            1. threat_levels (flood_risk, fire_danger, air_quality, drought_level, seismic_activity)
            2. weather information
            3. emergency contacts
            4. disaster risks
            5. safety tips
            6. recent disaster history
            Follow the exact structure of the example response."""

            # Call function from api_utils to get location information
            location_info = get_location_info(system_prompt, location_string)

            if location_info:
                try:
                    parsed_info = json.loads(location_info)
                    
                    # Validate that the response has the expected structure
                    required_keys = ['threat_levels', 'weather', 'emergency_contacts', 'disaster_risks', 'safety_tips', 'recent_disasters']
                    required_threat_levels = ['flood_risk', 'fire_danger', 'air_quality', 'drought_level', 'seismic_activity']
                    valid_levels = ['Low', 'Moderate', 'High', 'Severe', 'Good', 'Poor', 'Critical']
                    
                    if not all(key in parsed_info for key in required_keys):
                        print("Missing required top-level keys in GPT response")
                        raise ValueError("Invalid response structure")
                        
                    threat_levels = parsed_info['threat_levels']
                    if not all(threat in threat_levels for threat in required_threat_levels):
                        print("Missing required threat levels in GPT response")
                        raise ValueError("Invalid threat levels")
                        
                    # Validate threat levels
                    for threat, data in threat_levels.items():
                        if not isinstance(data, dict) or 'level' not in data or data['level'] not in valid_levels:
                            print(f"Invalid threat level data for {threat}")
                            raise ValueError(f"Invalid threat level: {threat}")

                    # If validation passes, return the parsed response
                    return Response({
                        'success': True,
                        'location': location_string,
                        'information': parsed_info
                    }, status=status.HTTP_200_OK)
                    
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {str(e)}")
                    print(f"Invalid JSON from GPT: {location_info}")
                except ValueError as e:
                    print(f"Validation error: {str(e)}")
                except Exception as e:
                    print(f"Unexpected error parsing GPT response: {str(e)}")

        except Exception as e:
            print(f"Error getting location info from GPT: {str(e)}")

        # If any error occurs or response is invalid, return default values
        return Response({
            'success': True,
            'location': location_string,
            'information': default_response
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Unexpected error in get_location_details: {str(e)}")
        return Response({
            'error': str(e),
            'location': location_string,
            'information': default_response
        }, status=status.HTTP_200_OK)  # Still return 200 with default data
        
from prakriti_setu.api_utils import scrape_hindu_national_news, scrape_hindu_state_news,analyze_news_for_disasters,filter_disaster_related_news

@csrf_exempt
@api_view(['GET'])
def get_national_news(request):
    """Get national news from The Hindu website filtered for natural disasters and calamities"""
    try:
        # Get parameter for number of pages to scrape (default is 2)
        # pages = int(request.GET.get('pages', 2))
        pages = 5
        
        # Limit maximum pages to prevent overloading
        if pages > 5:
            pages = 5
            
        # Scrape national news
        news_articles = scrape_hindu_national_news(pages=pages)
        
        # Filter for disaster-related news
        try:
            # Use Gemini to analyze and filter disaster news
            disaster_news = analyze_news_for_disasters(news_articles, limit=20)
            print(f"Disaster news found: {len(disaster_news)} articles")
            
            # If we found less than 5 disaster news articles, 
            # fall back to keyword filtering to ensure we have some content
            if len(disaster_news) < 5:
                print("Found less than 5 disaster news, using keyword filtering")
                disaster_news = filter_disaster_related_news(news_articles, limit=20)
                print(f"Disaster news after keyword filtering: {len(disaster_news)} articles")
            # If we STILL have less than 3 articles, just use all news
            if len(disaster_news) < 3:
                print("Found very few disaster news, using all national news")
                disaster_news = news_articles
        except Exception as e:
            print(f"Error filtering disaster news: {str(e)}, using basic keyword filtering")
            disaster_news = filter_disaster_related_news(news_articles, limit=20)
        
        # Process articles for frontend
        processed_articles = []
        for i, article in enumerate(disaster_news):
            # Skip invalid or incomplete articles
            if article['title'] == "N/A" or article['article_url'] == "N/A":
                continue
                
            # Use importance from disaster filtering if available, or determine it
            if 'importance' in article:
                severity = article['importance']
            else:
                # Generate a severity level based on title keywords
                severity = 'normal'
                if any(keyword in article['title'].lower() for keyword in ['disaster', 'flood', 'earthquake', 'crisis', 'emergency', 'alert', 'warning']):
                    severity = 'very-important'
                elif any(keyword in article['title'].lower() for keyword in ['damage', 'risk', 'danger', 'threat', 'concern', 'issue']):
                    severity = 'mild-important'
            print(f"Article {i+1} severity: {article}")
            # Create a processed article object
            processed_articles.append({
                'id': i + 1,
                'title': article['title'],
                'source': 'The Hindu',
                'type': 'news',
                'importance': severity,
                'timestamp': '24 hours ago',  # Fixed timestamp as we don't have actual time
                'state': article['category'] if article['category'] != 'N/A' else 'National',
                'description': f"Disaster update from {article['category']} category." if article['category'] != 'N/A' else "National disaster update from The Hindu.",
                'url': article['article_url'],
                'author': article['author'] if article['author'] != 'N/A' else 'The Hindu Staff',
                'imageUrl': 'https://images.unsplash.com/photo-1546422904-90eab23c3d7e?q=80&w=2972&auto=format&fit=crop'  # Default image
            })
            
        return Response(processed_articles, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
def get_state_news(request):
    """Get state news from The Hindu website"""
    try:
        # Get parameters from request
        state = request.GET.get('state', 'andhra-pradesh')
        # pages = int(request.GET.get('pages', 1))
        pages = 5
        
        # Limit maximum pages to prevent overloading
        if pages > 5:
            pages = 5
            
        # Map frontend state names to URL-friendly formats
        state_mapping = {
            'Andhra Pradesh': 'andhra-pradesh',
            'Karnataka': 'karnataka',
            'Kerala': 'kerala',
            'Tamil Nadu': 'tamil-nadu',
            'Telangana': 'telangana',
            # Add more state mappings as needed
        }
        
        # Convert state name if it's in the mapping
        url_state = state_mapping.get(state, state).lower()
        
        # Scrape state news
        news_articles = scrape_hindu_state_news(state=url_state, pages=pages)
        
        # Process articles for frontend
        processed_articles = []
        for i, article in enumerate(news_articles):
            # Skip invalid or incomplete articles
            if article['title'] == "N/A" or article['article_url'] == "N/A":
                continue
                
            # Generate a severity level based on title keywords (simulating importance)
            severity = 'normal'
            if any(keyword in article['title'].lower() for keyword in ['disaster', 'flood', 'earthquake', 'crisis', 'emergency', 'alert', 'warning']):
                severity = 'very-important'
            elif any(keyword in article['title'].lower() for keyword in ['damage', 'risk', 'danger', 'threat', 'concern', 'issue']):
                severity = 'mild-important'
                
            # Create a processed article object
            processed_articles.append({
                'id': i + 1,
                'title': article['title'],
                'source': 'The Hindu',
                'type': 'news',
                'importance': severity,
                'timestamp': '24 hours ago',  # Fixed timestamp as we don't have actual time
                'state': state.replace('-', ' ').title(),
                'description': f"News from {state.replace('-', ' ').title()} region.",
                'url': article['article_url'],
                'author': article['author'] if article['author'] != 'N/A' else 'The Hindu Staff',
                'imageUrl': 'https://images.unsplash.com/photo-1572949645841-094f3a9c4c94?q=80&w=2971&auto=format&fit=crop'  # Default image
            })
            
        return Response(processed_articles, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
def get_environmental_metrics(request):
    """Get environmental metrics for a specific location"""
    try:
        data = request.data
        location = data.get('location')
        
        if not location:
            return Response({'error': 'Location is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Call the function from call_gemini.py to get metrics
        from .call_gemini import get_environmental_metrics as get_metrics
        metrics = get_metrics(location)
        
        return Response({
            'success': True,
            'location': location,
            'metrics': metrics
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        # Log error but provide fallback metrics
        print(f"Error getting environmental metrics: {str(e)}")
        fallback_metrics = {
            "flood_risk": 35,
            "fire_danger": 45,
            "air_quality": 60,
            "seismic_activity": 25
        }
        
        return Response({
            'success': True,
            'location': location if 'location' in locals() else 'Unknown',
            'metrics': fallback_metrics,
            'note': 'Using fallback metrics due to an error'
        }, status=status.HTTP_200_OK)  # Return 200 with fallback data
        
@csrf_exempt
@api_view(['GET'])
@token_required
def admin_analytics(request):
    """Get analytics data for admin dashboard"""
    try:
        # Check if the user is an admin
        username = request.username
        is_admin = False
        
        # For debugging
        print(f"Checking admin access for user: {username}")
        
        try:
            # First check if the user exists in the User model
            user = User.objects.get(username=username)
            if user.is_organization:
                is_admin = True
                print(f"User {username} is an organization, granting admin access")
        except User.DoesNotExist:
            # Check if admin by email (if username is an email)
            try:
                if '@' in username:  # Only check admin table if username looks like an email
                    admin = Admin.objects.get(email=username)
                    is_admin = True
                    print(f"User {username} found in Admin table, granting admin access")
            except Admin.DoesNotExist:
                print(f"User {username} not found in Admin table")
        
        # For development purposes, temporarily allow access to analytics
        # REMOVE THIS IN PRODUCTION
        is_admin = True
        
        if not is_admin:
            print(f"Unauthorized access attempt by: {username}")
            return Response({'error': 'Unauthorized access'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get analytics data
        
        # 1. SOS Alerts analytics
        total_alerts = SosAlert.objects.count()
        active_alerts = SosAlert.objects.filter(status='active').count()
        resolved_alerts = SosAlert.objects.filter(status='resolved').count()
        critical_events = SosAlert.objects.filter(status='active').count()  # For now, all active alerts are considered critical
        
        # Calculate the average resolution time for resolved alerts
        avg_resolution_time = None
        resolved_alerts_with_time = SosAlert.objects.filter(
            status='resolved', 
            resolved_at__isnull=False
        )
        
        if resolved_alerts_with_time.exists():
            total_minutes = 0
            count = 0
            for alert in resolved_alerts_with_time:
                resolution_time = alert.resolved_at - alert.created_at
                total_minutes += resolution_time.total_seconds() / 60
                count += 1
            
            if count > 0:
                avg_resolution_time = round(total_minutes / count, 2)  # Average in minutes
        
        # 2. Regional data - group alerts by state/region
        state_data = {}
        city_data = {}
        
        # Get all alerts for regional analysis
        all_alerts = SosAlert.objects.all()
        for alert in all_alerts:
            # Process by state - get state from the location_name or set as "Unknown"
            # Since SosAlert doesn't have a state attribute, we'll parse it from location_name or use city
            state = "Unknown"
            if alert.location_name and "," in alert.location_name:
                # Try to extract state from location_name if it's in "City, State" format
                state = alert.location_name.split(",")[-1].strip()
            
            if state not in state_data:
                state_data[state] = {
                    'alerts': 0,
                    'active': 0,
                    'resolved': 0,
                    'severity': 0
                }
            
            state_data[state]['alerts'] += 1
            if alert.status == 'active':
                state_data[state]['active'] += 1
            elif alert.status == 'resolved':
                state_data[state]['resolved'] += 1
            
            # Process by city
            city = alert.city or "Unknown"
            if city not in city_data:
                city_data[city] = {
                    'alerts': 0,
                    'active': 0,
                    'resolved': 0,
                    'severity': 0
                }
            
            city_data[city]['alerts'] += 1
            if alert.status == 'active':
                city_data[city]['active'] += 1
            elif alert.status == 'resolved':
                city_data[city]['resolved'] += 1
        
        # Calculate severity for each state and city based on active vs. total ratio
        for state, data in state_data.items():
            if data['alerts'] > 0:
                severity = min(100, round((data['active'] / data['alerts']) * 100))
                # Add a baseline to ensure severity isn't too low
                severity = max(severity, 30) if data['active'] > 0 else severity
                state_data[state]['severity'] = severity
        
        for city, data in city_data.items():
            if data['alerts'] > 0:
                severity = min(100, round((data['active'] / data['alerts']) * 100))
                # Add a baseline to ensure severity isn't too low
                severity = max(severity, 30) if data['active'] > 0 else severity
                city_data[city]['severity'] = severity
        
        # 3. Source distribution (mock data for now)
        source_distribution = {
            "Social Media": 35,
            "News Sources": 25,
            "Community SOS": 20,
            "Official Reports": 20,
        }
        
        # 4. Get environmental metrics for a few major cities
        environmental_data = {}
        major_cities = ["New Delhi", "Mumbai", "Bengaluru", "Chennai", "Kolkata"]
        
        for city in major_cities:
            try:
                # Use the function directly from call_gemini.py instead of the view function
                from .call_gemini import get_environmental_metrics as get_metrics
                metrics = get_metrics(city)
                environmental_data[city] = metrics
            except Exception as e:
                print(f"Error getting environmental metrics for {city}: {str(e)}")
                # Set default values if error
                environmental_data[city] = {
                    "flood_risk": 35,
                    "fire_danger": 45,
                    "air_quality": 60,
                    "seismic_activity": 25
                }
        
        # 5. Calculate overall severity based on various factors
        active_alerts_percentage = 0
        if total_alerts > 0:
            active_alerts_percentage = (active_alerts / total_alerts) * 100
        
        # Average severity across all states with active alerts
        states_with_active = [data['severity'] for _, data in state_data.items() if data['active'] > 0]
        avg_state_severity = 0
        if states_with_active:
            avg_state_severity = sum(states_with_active) / len(states_with_active)
        
        # Get average environmental metrics across cities
        avg_flood_risk = sum(data.get("flood_risk", 0) for data in environmental_data.values()) / len(environmental_data) if environmental_data else 0
        avg_fire_danger = sum(data.get("fire_danger", 0) for data in environmental_data.values()) / len(environmental_data) if environmental_data else 0
        avg_seismic = sum(data.get("seismic_activity", 0) for data in environmental_data.values()) / len(environmental_data) if environmental_data else 0
        
        # Calculate overall severity (weighted average)
        overall_severity = round(
            (active_alerts_percentage * 0.35) +
            (avg_state_severity * 0.3) +
            (avg_flood_risk * 0.1) +
            (avg_fire_danger * 0.1) +
            (avg_seismic * 0.15)
        )
        
        # Cap at 100
        overall_severity = min(100, overall_severity)
        
        # 6. Prepare the response
        response_data = {
            "totalAlerts": total_alerts,
            "activeAlerts": active_alerts,
            "resolvedAlerts": resolved_alerts,
            "criticalEvents": critical_events,
            "responsesInitiated": resolved_alerts,  # Number of responses = resolved alerts
            "avgResolutionTime": avg_resolution_time,
            "overallSeverity": overall_severity,
            "stateData": state_data,
            "cityData": city_data,
            "sourceDistribution": source_distribution,
            "environmentalData": environmental_data
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        print(f"Error in admin_analytics: {str(e)}")
        print(traceback.format_exc())
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['GET'])
def get_disasters(request):
    """
    Get current and potential disaster events in India
    """
    try:
        num_articles = int(request.GET.get('num_articles', 5))
        
        # Use the existing fetch_disaster_news function
        disasters = fetch_disaster_news(
            query="natural disaster india",
            num_articles=num_articles,
            output_format="python"
        )
        
        # Map severity levels to importance levels for frontend
        severity_to_importance = {
            5: "very-important",
            4: "very-important",
            3: "mild-important",
            2: "mild-important",
            1: "normal"
        }
        
        # Transform the data for frontend consumption
        formatted_disasters = []
        for disaster in disasters:
            formatted_disasters.append({
                "id": disaster["id"],
                "title": disaster["title"],
                "description": disaster["new_desc"],
                "severity": severity_to_importance.get(disaster["severity"], "normal"),
                "region": disaster["region"],
                "link": disaster["link"]
            })
            
        return Response(formatted_disasters)
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=500
        )

@csrf_exempt
@api_view(['GET'])
def get_recent_activities(request):
    """Get combined recent activities (volunteering events and alerts)"""
    try:
        # Get parameter for number of activities to return
        count = int(request.GET.get('count', 5))
        
        # Get recent volunteering events
        events = VolunteeringEvent.objects.order_by('-created_at')[:10]
        
        # Get recent SOS alerts
        alerts = SosAlert.objects.order_by('-created_at')[:10]
        
        # Combine and prepare activities
        activities = []
        
        # Add volunteering events
        for event in events:
            event_icon = "Leaf"  # Default icon
            
            # Choose icon based on category
            if event.category == 'planting':
                event_icon = "Leaf"
            elif event.category == 'cleanup':
                event_icon = "Recycle"
            elif event.category == 'gardening':
                event_icon = "Trees"
            elif event.category == 'education':
                event_icon = "BookOpen"
            elif event.category == 'disaster':
                event_icon = "AlertTriangle"
                
            activities.append({
                'id': f"event-{event.id}",
                'action': f"New Volunteering Event: {event.title}",
                'date': event.created_at.strftime("%B %d, %Y at %I:%M %p"),
                'icon': event_icon,
                'iconColor': "text-green-400",
                'type': 'event'
            })
        
        # Add SOS alerts
        for alert in alerts:
            activities.append({
                'id': f"sos-{alert.id}",
                'action': f"SOS Alert: Emergency in {alert.city}, {alert.country}",
                'date': alert.created_at.strftime("%B %d, %Y at %I:%M %p"),
                'icon': "AlertTriangle",
                'iconColor': "text-red-400",
                'type': 'sos'
            })
        
        # Sort all activities by date (newest first) and limit to requested count
        activities.sort(key=lambda x: x['date'], reverse=True)
        limited_activities = activities[:count]
        
        return Response(limited_activities, status=status.HTTP_200_OK)
    except Exception as e:
        print(f"Error getting recent activities: {str(e)}")
        traceback.print_exc()
        
        # If there's an error, return mock data
        mock_activities = [
            {
                'id': 1,
                'action': "Disaster Report Submitted: Flooding in North District",
                'date': "Today, 10:30 AM",
                'icon': "Droplet",
                'iconColor': "text-blue-400",
                'type': 'report'
            },
            {
                'id': 2,
                'action': "Air Quality Alert Issued for Central Metro Area",
                'date': "Yesterday, 4:15 PM",
                'icon': "Wind",
                'iconColor': "text-purple-400",
                'type': 'alert'
            },
            {
                'id': 3,
                'action': "New Conservation Initiative Launched in East Region",
                'date': "2 days ago",
                'icon': "Leaf",
                'iconColor': "text-emerald-400",
                'type': 'event'
            },
            {
                'id': 4,
                'action': "Updated Recycling Guidelines Published",
                'date': "3 days ago",
                'icon': "Recycle",
                'iconColor': "text-green-400",
                'type': 'update'
            },
            {
                'id': 5,
                'action': "Forest Management Plan Revised for Protected Areas",
                'date': "4 days ago",
                'icon': "Trees",
                'iconColor': "text-lime-400",
                'type': 'update'
            }
        ]
        return Response(mock_activities, status=status.HTTP_200_OK)