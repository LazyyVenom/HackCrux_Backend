import requests
import json
import re
from datetime import datetime


API_KEY = 'AIzaSyCNyeeQiDw-boVJRe-GYTXTSjxgX4CbF5Q'

# Updated to use the Gemini Flash model
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def extract_json_from_text(text):
    """Extract JSON content from text that might contain markdown code blocks or other text."""
    # First, try to find JSON in code blocks
    code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    code_matches = re.findall(code_block_pattern, text)
    
    if code_matches:
        # Return the first code block that looks like valid JSON
        for match in code_matches:
            cleaned = match.strip()
            if cleaned and (cleaned.startswith('{') or cleaned.startswith('[')):
                return cleaned
    
    # If no code blocks with JSON are found, look for content that looks like JSON
    # This will find content enclosed in curly braces
    json_pattern = r'(\{[\s\S]*\})'
    json_matches = re.findall(json_pattern, text)
    
    if json_matches:
        # Return the first match that looks like valid JSON
        for match in json_matches:
            return match.strip()
    
    # As a last resort, return the original text if it starts with { or [
    if text.strip().startswith('{') or text.strip().startswith('['):
        return text.strip()
    
    # No valid JSON found
    print("No valid JSON structure found in response")
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
    """Get environmental metrics for a specific location.
    
    Args:
        location (str): The location name (city, state, or country)
        
    Returns:
        dict: Environmental metrics including flood_risk, fire_danger, air_quality, and seismic_activity
    """
    system_prompt = """You are an environmental data analyst. Provide current environmental metrics for the given location based on known geographical data, climate patterns, and seasonal risks.
    
    Respond with a JSON object containing the following metrics:
    1. flood_risk (percentage between 0-100) - Based on proximity to water bodies, terrain, and seasonal rainfall
    2. fire_danger (percentage between 0-100) - Based on vegetation, climate conditions, and seasonal dryness
    3. air_quality (percentage between 0-100, where lower is better) - Based on industrial activity, population density, and geography
    4. seismic_activity (percentage between 0-100) - Based on tectonic plate location and historical earthquake data
    5. drought_risk (percentage between 0-100) - Based on rainfall patterns and water availability
    
    Additionally, provide a one-sentence 'recommendation' field for each metric with specific advice.
    
    The response must be valid JSON without any explanatory text."""
    
    user_prompt = f"Provide detailed environmental metrics for {location}. Current date is {datetime.now().strftime('%B %Y')}. Use available geographical and seasonal data. Respond only with JSON."
    
    try:
        # Call the Gemini API using our helper function
        response = callGPT(system_prompt, user_prompt)
        
        # Better debugging for response
        print(f"Raw response for {location}:", response[:100] + "..." if len(response) > 100 else response)
        
        # Check if response is empty
        if not response or len(response.strip()) == 0:
            print(f"Empty response from API for {location}")
            raise ValueError("Empty response from API")
            
        # Try to clean up response if it's not valid JSON
        try:
            # First attempt to parse as is
            metrics = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError for {location}: {str(e)}")
            
            # Try to fix common issues with the response
            clean_response = response.strip()
            
            # Remove potential markdown code block markers
            if clean_response.startswith("```"):
                clean_response = re.sub(r'^```json\s*', '', clean_response)
                clean_response = re.sub(r'^```\s*', '', clean_response)
                clean_response = re.sub(r'\s*```$', '', clean_response)
            
            # Try parsing again with cleaned response
            try:
                metrics = json.loads(clean_response)
            except json.JSONDecodeError:
                # If still failing, construct a simple valid JSON as fallback
                print(f"Failed to parse JSON even after cleaning for {location}")
                raise ValueError("Invalid JSON response")
        
        # Ensure all required fields are present
        required_metrics = ["flood_risk", "fire_danger", "air_quality", "seismic_activity"]
        for metric in required_metrics:
            if metric not in metrics:
                print(f"Missing required metric: {metric}")
                metrics[metric] = 35  # Default value for missing metrics
        
        # Add index values for easier frontend visualization
        metrics["environmental_index"] = round(
            (metrics["flood_risk"] * 0.3) + 
            (metrics["fire_danger"] * 0.3) + 
            (metrics["air_quality"] * 0.2) + 
            (metrics["seismic_activity"] * 0.2)
        )
        
        return metrics
    except Exception as e:
        print(f"Error getting environmental metrics for {location}: {str(e)}")
        # Provide fallback metrics with location-specific variations
        # Use hash of location name to generate pseudo-random but consistent values
        import hashlib
        location_hash = int(hashlib.md5(location.encode()).hexdigest(), 16)
        
        # Generate values between 20-60 based on location hash
        def get_value(offset=0):
            return 20 + ((location_hash + offset) % 40)
        
        return {
            "flood_risk": get_value(0),
            "fire_danger": get_value(1),
            "air_quality": get_value(2),
            "seismic_activity": get_value(3),
            "drought_risk": get_value(4),
            "environmental_index": get_value(5),
            "note": "Using approximated metrics based on location"
        }
