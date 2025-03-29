import requests
import json
import re


API_KEY = 'AIzaSyCNyeeQiDw-boVJRe-GYTXTSjxgX4CbF5Q'

# Updated to use the Gemini Flash model
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def extract_json_from_text(text):
    """Extract JSON content from text that might contain markdown code blocks or other text."""
    # Look for content between triple backticks with json identifier
    json_pattern = r'(?:json)?\s*([\s\S]*?)'
    match = re.search(json_pattern, text)
    
    if match:
        # Return only the JSON content within the code block
        return match.group(1).strip()
    
    # If no code blocks found, return the original text (it might be direct JSON)
    return text.strip()

def callGPT(system_prompt, user_prompt):
    # Payload structure remains the same for Gemini Flash
    payload = {
        "contents": [{
            "parts": [{
                "text": f"System: {system_prompt}\nUser: {user_prompt}"
            }]
        }]
    }

    try:
        response = requests.post(
            f"{ENDPOINT}?key={API_KEY}",
            json=payload
        )
        response.raise_for_status()
        response_data = response.json()
        raw_text = response_data['candidates'][0]['content']['parts'][0]['text']
        
        # Extract only the JSON content without extra text
        clean_response = extract_json_from_text(raw_text)
        
        # For debugging
        print('clean_response:', clean_response)
        
        return clean_response
    except requests.RequestException as e:
        error_message = f"Failed to make the request. Error: {e}"
        print(error_message)
        raise RuntimeError(error_message)

def get_environmental_metrics(location):
    """Get environmental metrics for a specific location."""
    system_prompt = """You are an environmental data analyst. Provide metrics for the given location.
    Respond with a JSON object containing the following metrics:
    1. flood_risk (percentage between 0-100)
    2. fire_danger (percentage between 0-100)
    3. air_quality (percentage between 0-100)
    4. seismic_activity (percentage between 0-100)
    
    Base your assessment on the location's known natural disaster risks, current season, and geography.
    The response must be valid JSON without any explanatory text."""
    
    user_prompt = f"Provide environmental metrics for {location}. Respond only with JSON."
    
    try:
        response = callGPT(system_prompt, user_prompt)
        metrics = json.loads(response)
        return metrics
    except Exception as e:
        print(f"Error getting environmental metrics: {str(e)}")
        # Provide fallback metrics
        return {
            "flood_risk": 35,
            "fire_danger": 45,
            "air_quality": 60,
            "seismic_activity": 25
        }
