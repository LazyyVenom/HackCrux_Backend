from GoogleNews import GoogleNews
import requests
import json
from bs4 import BeautifulSoup

API_KEY = "12c6ced676b749258b582edd76600aa4"
X_API_KEY = "McrnrlNgOrlAhF305v95DYCjR"
X_API_SECRET = "8XnjlfgD3jMJfQn4vB6r1IbAfOpJQSSzo64kug5hqgU7iYxy6v"
X_BEARER = "AAAAAAAAAAAAAAAAAAAAACsK0QEAAAAAD1Ri0zcZKYp8PP6kDHKyo7tP%2Brc%3DNKvCzk4eP8OJLPkPreO2baCA3QfBcmFuTMd4eAyAFFaeysERXx"

headers = {
    "Content-Type": "application/json",
    "api-key": API_KEY,
}

ENDPOINT = "https://lexiai1.openai.azure.com/openai/deployments/lexiaiapi/chat/completions?api-version=2024-08-01-preview"

def callGPT(system_prompt, user_prompt):
    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "max_tokens": 4096
    }

    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        print('response_data:', response_data)
        return response_data.get("choices")[0].get("message").get("content")
    except requests.RequestException as e:
        error_message = f"Failed to make the request. Error: {e}"
        print(error_message)
        raise RuntimeError(error_message)


def get_news_articles(query, num_articles=20):
    googlenews = GoogleNews(lang='en', region='IN')
    googlenews.set_period('7d')
    googlenews.set_encode('utf-8')
    googlenews.search(query)
    googlenews.get_page(1)
    result = googlenews.result(num_articles)
    return result

def fetch_disaster_news(query="natural disaster india", num_articles=20, output_format="json", states=None):
    """
    Fetch disaster news specific to India with distinct disaster events
    
    Args:
        query: Search query (default focuses on Indian disasters)
        num_articles: Maximum number of articles to fetch
        output_format: "json" or "python"
        states: Optional list of Indian states to filter by
    """
    # Try more India-specific queries if needed
    news_articles = get_news_articles(query, num_articles)
    if not news_articles and "india" not in query.lower():
        news_articles = get_news_articles(query + " india", num_articles)
    
    if not news_articles:  # If no disaster news, generate future risks
        prompt = """Generate 5 different potential disaster scenarios for India based on regional vulnerabilities:
        1. For North India (e.g., Himalayas, Delhi NCR)
        2. For South India (e.g., Tamil Nadu, Kerala)
        3. For East India (e.g., West Bengal, Odisha)
        4. For West India (e.g., Gujarat, Maharashtra)
        5. For Central India (e.g., Madhya Pradesh)
        
        For each scenario, provide a title and a brief description considering historical patterns, 
        geographical vulnerabilities, and climate trends specific to that region.
        Format as: Region: Title | Description
        """
        future_scenarios = callGPT(system_prompt='General', user_prompt=prompt).split('\n')
        result = []
        for i, scenario in enumerate(future_scenarios[:5]):
            parts = scenario.split('|')
            if len(parts) == 2:
                region_title = parts[0].strip().split(':')
                if len(region_title) == 2:
                    result.append({
                        "id": i+1,
                        "link": "N/A",
                        "new_desc": parts[1].strip()[:20],
                        "title": region_title[1].strip(),
                        "severity": 1,
                        "region": region_title[0].strip()
                    })
        if result:
            if output_format == "json":
                return json.dumps(result, indent=2)
            return result
    
    # Group articles into different disaster events
    clustering_prompt = f"""
    Group these disaster news articles into 5 distinct disaster events in India.
    For each group, provide the line number range (e.g., "1-3, 7, 9") of articles that belong together.
    If there are fewer than 5 distinct events, suggest additional potential disasters in different regions.
    
    Articles:
    {chr(10).join([f"{i+1}. {article['title']} - {article['desc'][:100]}..." for i, article in enumerate(news_articles)])}
    
    Format your response as:
    Event 1: [line numbers] | [disaster type] | [region]
    Event 2: [line numbers] | [disaster type] | [region]
    ...and so on
    """
    
    clustering_result = callGPT(system_prompt='General', user_prompt=clustering_prompt)
    event_groups = []
    
    # Parse the clustering results
    for line in clustering_result.split('\n'):
        if ':' in line:
            parts = line.split('|')
            if len(parts) >= 3:
                article_indices = []
                id_part = parts[0].split(':')[1].strip()
                for range_str in id_part.split(','):
                    range_str = range_str.strip()
                    if '-' in range_str:
                        start, end = map(int, range_str.split('-'))
                        article_indices.extend(range(start-1, end))  # Adjust for 0-indexing
                    else:
                        try:
                            article_indices.append(int(range_str)-1)  # Adjust for 0-indexing
                        except ValueError:
                            continue
                
                disaster_type = parts[1].strip()
                region = parts[2].strip()
                
                # Get the articles for this event
                event_articles = []
                for idx in article_indices:
                    if 0 <= idx < len(news_articles):
                        event_articles.append(news_articles[idx])
                
                if event_articles:
                    event_groups.append({
                        'articles': event_articles,
                        'disaster_type': disaster_type,
                        'region': region
                    })
    
    # Process each event group separately
    structured_data = []
    for i, event in enumerate(event_groups[:5]):
        # Combine news descriptions for this event
        event_descriptions = "\n".join([article["desc"] for article in event['articles']])
        
        # Determine severity level for this specific event
        severity_prompt = f"""
        Based on this specific disaster in {event['region']}, assign a severity level from 1 (low) to 5 (high) as a single number only:
        {event_descriptions}
        """
        try:
            severity_level = int(callGPT(system_prompt='General', user_prompt=severity_prompt))
        except ValueError:
            severity_level = 3  # Default if we can't parse a number
        
        # Generate a concise description for this event
        desc_prompt = f"""
        Summarize this {event['disaster_type']} disaster in {event['region']} in under 20 words:
        {event_descriptions}
        """
        concise_desc = callGPT(system_prompt='General', user_prompt=desc_prompt)
        
        # Generate a title for this event
        title_prompt = f"""
        Create a brief, informative title for this {event['disaster_type']} disaster in {event['region']}:
        {event_descriptions}
        """
        new_title = callGPT(system_prompt='General', user_prompt=title_prompt)
        
        # Add this event to our structured data
        structured_data.append({
            "id": i+1,
            "link": event['articles'][0]["link"] if event['articles'] else "N/A",
            "new_desc": concise_desc,
            "title": new_title,
            "severity": severity_level,
            "region": event['region']
        })
    
    # If we have fewer than 5 events, generate additional hypothetical ones
    if len(structured_data) < 5:
        regions_covered = [item["region"] for item in structured_data]
        
        additional_prompt = f"""
        Generate {5 - len(structured_data)} additional potential disaster scenarios for different regions in India 
        not already covered in this list: {', '.join(regions_covered)}.
        For each scenario, provide the disaster type, affected region, a title, and a brief description.
        """
        
        additional_scenarios = callGPT(system_prompt='General', user_prompt=additional_prompt).split('\n')
        for i, scenario in enumerate(additional_scenarios[:5-len(structured_data)]):
            if ':' in scenario:
                parts = scenario.split(':')
                if len(parts) >= 2:
                    title = parts[0].strip()
                    desc = parts[1].strip()
                    region = "Other Indian Region"
                    if "in " in title:
                        region_part = title.split("in ")[-1]
                        region = region_part
                    
                    structured_data.append({
                        "id": len(structured_data) + 1,
                        "link": "N/A",
                        "new_desc": desc[:20],
                        "title": title,
                        "severity": 2,  # Lower severity for hypothetical events
                        "region": region
                    })
    
    # Sort by severity (highest first)
    structured_data.sort(key=lambda x: x["severity"], reverse=True)
    
    # Return only the top 5
    result = structured_data[:5]
    
    if output_format == "json":
        return json.dumps(result, indent=2)
    else:
        return result

def get_location_info(system_prompt, user_location):
    """
    Get detailed information about a location using GPT
    
    Args:
        system_prompt: The system prompt for GPT
        user_location: The user's location (city, country)
    
    Returns:
        JSON response with location information
    """
    
    user_prompt = f"""
    Provide detailed information about {user_location} in the following JSON format:
    
    1. Current weather conditions (approximate based on season and location)
    2. Local disaster risks based on geography and season
    3. Safety tips specific to this location
    4. Emergency contact information for this location
    5. Recent disaster history (if any)
    6. Threat levels for the dashboard display
    7. Try stay positive as much possible as these happens only rarely 

    Format the response as a JSON object with the following structure:
    {{
        "weather": {{
            "condition": "Clear/Rainy/etc",
            "temperature": "Approximate temperature",
            "forecast": "Brief forecast"
        }},
        "disaster_risks": [
            {{
                "type": "Risk type",
                "severity": "Low/Medium/High",
                "description": "Brief description"
            }}
        ],
        "safety_tips": [
            "Tip 1", 
            "Tip 2"
        ],
        "emergency_contacts": {{
            "police": "Number",
            "ambulance": "Number",
            "fire": "Number",
            "disaster_management": "Number"
        }},
        "recent_disasters": [
            {{
                "type": "Disaster type",
                "date": "Approximate date",
                "impact": "Brief description of impact"
            }}
        ],
        "threat_levels": {{
            "flood_risk": {{
                "level": "Low/Moderate/High/Severe/Extreme",
                "icon": "Droplet",
                "color": "border-blue-500",
                "bgColor": "bg-blue-900/30"
            }},
            "fire_danger": {{
                "level": "Low/Moderate/High/Severe/Extreme",
                "icon": "Activity",
                "color": "border-red-500",
                "bgColor": "bg-red-900/30"
            }},
            "air_quality": {{
                "level": "Good/Moderate/Poor/Unhealthy/Hazardous",
                "icon": "Wind",
                "color": "border-purple-500",
                "bgColor": "bg-purple-900/30"
            }},
            "drought_level": {{
                "level": "None/Moderate/Severe/Extreme/Exceptional",
                "icon": "AlertTriangle",
                "color": "border-amber-500",
                "bgColor": "bg-amber-900/30"
            }},
            "seismic_activity": {{
                "level": "Low/Moderate/High/Very High/Extreme",
                "icon": "Activity",
                "color": "border-emerald-500",
                "bgColor": "bg-emerald-900/30"
            }}
        }}
    }}
    
    For the threat_levels, evaluate the current risk levels based on the location, season, and historical data.
    Note: If you don't have specific information, provide reasonable estimates based on the general characteristics of the location.
    """
    
    try:
        response = callGPT(system_prompt, user_prompt)
        return response
    except Exception as e:
        error_message = f"Failed to get location information. Error: {e}"
        print(error_message)
        return None

def scrape_ndtv_india_news():
    url = "https://www.ndtv.com/india#pfrom=home-ndtv_mainnavigation"
    
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to retrieve the webpage: Status code {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    news_items = soup.find_all('h2', class_='NwsLstPg_ttl')
    
    news_list = []
    
    for item in news_items:
        link_element = item.find('a', class_='NwsLstPg_ttl-lnk')
        
        if link_element:
            title = link_element.text.strip()
            link = link_element.get('href')
            
            news_list.append({
                'title': title,
                'link': link,
                'img_url': ""
            })
    
    return news_list

def scrape_ndtv_india_news():
    url = "https://www.ndtv.com/india#pfrom=home-ndtv_mainnavigation"
    
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to retrieve the webpage: Status code {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    news_items = soup.find_all('h2', class_='NwsLstPg_ttl')
    
    news_list = []
    
    for item in news_items:
        link_element = item.find('a', class_='NwsLstPg_ttl-lnk')
        
        if link_element:
            title = link_element.text.strip()
            link = link_element.get('href')
            
            news_list.append({
                'title': title,
                'link': link,
                'img_url': ""
            })
    
    return news_list