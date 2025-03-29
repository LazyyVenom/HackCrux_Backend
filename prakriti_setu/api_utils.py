from GoogleNews import GoogleNews
import requests
import json
from bs4 import BeautifulSoup
import time

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
        JSON response with location information or None if error occurs
    """
    
    user_prompt = f"""
    Analyze and provide threat levels for {user_location}. Return ONLY a JSON object with the following structure:
    {{
        "threat_levels": {{
            "flood_risk": {{
                "level": "Low",
                "icon": "Droplet",
                "color": "border-blue-500",
                "bgColor": "bg-blue-900/30"
            }},
            "fire_danger": {{
                "level": "Low",
                "icon": "Activity",
                "color": "border-red-500",
                "bgColor": "bg-red-900/30"
            }},
            "air_quality": {{
                "level": "Good",
                "icon": "Wind",
                "color": "border-purple-500",
                "bgColor": "bg-purple-900/30"
            }},
            "drought_level": {{
                "level": "Low",
                "icon": "AlertTriangle",
                "color": "border-amber-500",
                "bgColor": "bg-amber-900/30"
            }},
            "seismic_activity": {{
                "level": "Low",
                "icon": "Activity",
                "color": "border-emerald-500",
                "bgColor": "bg-emerald-900/30"
            }}
        }}
    }}
    
    For each threat level:
    - "level" should be one of: "Low", "Moderate", "High", "Severe"
    - Keep the icon, color, and bgColor values exactly as shown
    - Base the levels on the location's geography, climate, and historical data
    - If uncertain about a specific risk, default to "Low"
    
    Return ONLY the JSON object, no other text or explanations.
    """
    
    try:
        # Get response from GPT
        response = callGPT(system_prompt, user_prompt)
        
        if not response:
            print(f"Empty response from GPT for location: {user_location}")
            return None
            
        # Try to parse the response as JSON to validate it
        try:
            import json
            parsed = json.loads(response)
            
            # Validate the structure
            if not isinstance(parsed, dict) or 'threat_levels' not in parsed:
                print(f"Invalid response structure from GPT: {response}")
                return None
                
            # Validate each threat level
            required_threats = ['flood_risk', 'fire_danger', 'air_quality', 'drought_level', 'seismic_activity']
            valid_levels = ['Low', 'Moderate', 'High', 'Severe']
            
            threat_levels = parsed['threat_levels']
            for threat in required_threats:
                if threat not in threat_levels:
                    print(f"Missing threat level: {threat}")
                    return None
                    
                threat_data = threat_levels[threat]
                if not isinstance(threat_data, dict):
                    print(f"Invalid threat data for {threat}")
                    return None
                    
                if 'level' not in threat_data or threat_data['level'] not in valid_levels:
                    print(f"Invalid level for {threat}")
                    return None
            
            return response
            
        except json.JSONDecodeError:
            print(f"Invalid JSON response from GPT: {response}")
            return None
            
    except Exception as e:
        print(f"Error in get_location_info: {str(e)}")
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

def scrape_news18_india():
    url = "https://www.news18.com/india/"
    
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to retrieve the webpage: Status code {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    captions = soup.find_all('figcaption', class_='jsx-1976791735')
    
    news_list = []
    
    for caption in captions:
        title = caption.text.strip()
        
        parent = caption.find_parent('figure') or caption.find_parent('a') or caption.find_parent('article')
        link = None
        
        if parent:
            if parent.name == 'a':
                link = parent.get('href')
            else:
                anchor = parent.find('a')
                if anchor:
                    link = anchor.get('href')
        
        if title and link:
            if link.startswith('/'):
                link = "https://www.news18.com" + link
            
            news_list.append({
                'title': title,
                'link': link,
                'img_url': ""
            })
    
    return news_list


def scrape_hindu_state_news(state='andhra-pradesh', pages=1):
    """
    Scrape news articles from The Hindu website for a specific state.
    
    Args:
        state (str): The state name to fetch news for, default is 'andhra-pradesh'
        pages (int): Number of pages to scrape, default is 1
        
    Returns:
        list: A list of dictionaries containing news article details
    """
    all_articles = []
    
    for page in range(1, pages + 1):
        # Construct URL with page parameter
        if page == 1:
            url = f"https://www.thehindu.com/news/national/{state}/"
        else:
            url = f"https://www.thehindu.com/news/national/{state}/?page={page}"
        
        print(f"Scraping page {page} of {pages}: {url}")
        
        # Send HTTP request with user agent to avoid blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to retrieve page {page}. Status code: {response.status_code}")
            continue
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all news article elements (both types)
        page_articles = []
        
        # Process "element smaller" type articles
        article_elements = soup.find_all('div', class_='element smaller')
        for element in article_elements:
            article_data = extract_article_data_smaller(element)
            if article_data:
                page_articles.append(article_data)
        
        # Process "element row-element" type articles
        row_elements = soup.find_all('div', class_='element row-element')
        for element in row_elements:
            article_data = extract_article_data_row(element)
            if article_data:
                page_articles.append(article_data)
        
        # Add articles from this page to the total collection
        all_articles.extend(page_articles)
        print(f"Found {len(page_articles)} articles on page {page}")
        
        # Add a small delay between page requests to avoid overwhelming the server
        if page < pages:
            time.sleep(1)
    
    print(f"Scraped a total of {len(all_articles)} articles from {pages} pages")
    return all_articles

def extract_article_data_smaller(element):
    """
    Extract article data from 'element smaller' type elements
    """
    article_data = {}
    
    try:
        # Extract location/category
        label_div = element.find('div', class_='label')
        if label_div and label_div.find('a'):
            article_data['category'] = label_div.find('a').text.strip()
            article_data['category_url'] = label_div.find('a')['href']
        else:
            article_data['category'] = "N/A"
            article_data['category_url'] = "N/A"
        
        # Extract article title and URL
        title_element = element.find('h3', class_='title big')
        if title_element and title_element.find('a'):
            article_data['title'] = title_element.find('a').text.strip()
            article_data['article_url'] = title_element.find('a')['href']
        else:
            article_data['title'] = "N/A"
            article_data['article_url'] = "N/A"
        
        # Extract author information
        by_line = element.find('div', class_='by-line')
        if by_line and by_line.find('div', class_='author-name'):
            author_element = by_line.find('div', class_='author-name')
            if author_element.find('a'):
                article_data['author'] = author_element.find('a').text.strip()
                article_data['author_url'] = author_element.find('a')['href']
            else:
                article_data['author'] = author_element.text.strip()
                article_data['author_url'] = "N/A"
        else:
            article_data['author'] = "N/A"
            article_data['author_url'] = "N/A"
        
        return article_data
        
    except Exception as e:
        print(f"Error parsing 'element smaller' article: {e}")
        return None

def extract_article_data_row(element):
    """
    Extract article data from 'element row-element' type elements
    """
    article_data = {}
    
    try:
        # For row-element, we might not have a category label in the same way
        article_data['category'] = "N/A"
        article_data['category_url'] = "N/A"
        
        # Get the first link which typically contains the article URL
        first_link = element.find('a')
        if first_link:
            # Store the article URL
            article_data['article_url'] = first_link['href']
        else:
            article_data['article_url'] = "N/A"
        
        # Extract article title from right-content section
        right_content = element.find('div', class_='right-content')
        if right_content:
            title_element = right_content.find('h3', class_='title big')
            if title_element and title_element.find('a'):
                article_data['title'] = title_element.find('a').text.strip()
                # Update article URL if we find it here (should be the same as above)
                article_data['article_url'] = title_element.find('a')['href']
            else:
                article_data['title'] = "N/A"
        else:
            article_data['title'] = "N/A"
        
        # Extract author information
        by_line = element.find('div', class_='by-line')
        if by_line and by_line.find('div', class_='author-name'):
            author_element = by_line.find('div', class_='author-name')
            if author_element.find('a'):
                article_data['author'] = author_element.find('a').text.strip()
                article_data['author_url'] = author_element.find('a')['href']
            else:
                article_data['author'] = author_element.text.strip()
                article_data['author_url'] = "N/A"
        else:
            article_data['author'] = "N/A"
            article_data['author_url'] = "N/A"
        
        return article_data
        
    except Exception as e:
        print(f"Error parsing 'element row-element' article: {e}")
        return None


def scrape_hindu_national_news(pages=1):
    """
    Scrape national news articles from The Hindu website.
    
    Args:
        pages (int): Number of pages to scrape, default is 1
        
    Returns:
        list: A list of dictionaries containing news article details
    """
    all_articles = []
    
    for page in range(1, pages + 1):
        # Construct URL with page parameter
        url = f"https://www.thehindu.com/news/national/?page={page}"
        
        print(f"Scraping page {page} of {pages}: {url}")
        
        # Send HTTP request with user agent to avoid blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to retrieve page {page}. Status code: {response.status_code}")
            continue
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all news article elements (both types)
        page_articles = []
        
        # Process "element smaller" type articles
        article_elements = soup.find_all('div', class_='element smaller')
        for element in article_elements:
            article_data = extract_article_data_smaller(element)
            if article_data:
                page_articles.append(article_data)
        
        # Process "element row-element" type articles
        row_elements = soup.find_all('div', class_='element row-element')
        for element in row_elements:
            article_data = extract_article_data_row(element)
            if article_data:
                page_articles.append(article_data)
        
        # Add articles from this page to the total collection
        all_articles.extend(page_articles)
        print(f"Found {len(page_articles)} articles on page {page}")
        
        # Add a small delay between page requests to avoid overwhelming the server
        if page < pages:
            time.sleep(1)
    
    print(f"Scraped a total of {len(all_articles)} articles from {pages} pages")
    return all_articles

def extract_article_data_smaller(element):
    """
    Extract article data from 'element smaller' type elements
    """
    article_data = {}
    
    try:
        # Extract location/category
        label_div = element.find('div', class_='label')
        if label_div and label_div.find('a'):
            article_data['category'] = label_div.find('a').text.strip()
            article_data['category_url'] = label_div.find('a')['href']
        else:
            article_data['category'] = "N/A"
            article_data['category_url'] = "N/A"
        
        # Extract article title and URL
        title_element = element.find('h3', class_='title big')
        if title_element and title_element.find('a'):
            article_data['title'] = title_element.find('a').text.strip()
            article_data['article_url'] = title_element.find('a')['href']
        else:
            article_data['title'] = "N/A"
            article_data['article_url'] = "N/A"
        
        # Extract author information
        by_line = element.find('div', class_='by-line')
        if by_line and by_line.find('div', class_='author-name'):
            author_element = by_line.find('div', class_='author-name')
            if author_element.find('a'):
                article_data['author'] = author_element.find('a').text.strip()
                article_data['author_url'] = author_element.find('a')['href']
            else:
                article_data['author'] = author_element.text.strip()
                article_data['author_url'] = "N/A"
        else:
            article_data['author'] = "N/A"
            article_data['author_url'] = "N/A"
        
        return article_data
        
    except Exception as e:
        print(f"Error parsing 'element smaller' article: {e}")
        return None

def extract_article_data_row(element):
    """
    Extract article data from 'element row-element' type elements
    """
    article_data = {}
    
    try:
        # For row-element, we might not have a category label in the same way
        article_data['category'] = "N/A"
        article_data['category_url'] = "N/A"
        
        # Get the first link which typically contains the article URL
        first_link = element.find('a')
        if first_link:
            # Store the article URL
            article_data['article_url'] = first_link['href']
        else:
            article_data['article_url'] = "N/A"
        
        # Extract article title from right-content section
        right_content = element.find('div', class_='right-content')
        if right_content:
            title_element = right_content.find('h3', class_='title big')
            if title_element and title_element.find('a'):
                article_data['title'] = title_element.find('a').text.strip()
                # Update article URL if we find it here (should be the same as above)
                article_data['article_url'] = title_element.find('a')['href']
            else:
                article_data['title'] = "N/A"
        else:
            article_data['title'] = "N/A"
        
        # Extract author information
        by_line = element.find('div', class_='by-line')
        if by_line and by_line.find('div', class_='author-name'):
            author_element = by_line.find('div', class_='author-name')
            if author_element.find('a'):
                article_data['author'] = author_element.find('a').text.strip()
                article_data['author_url'] = author_element.find('a')['href']
            else:
                article_data['author'] = author_element.text.strip()
                article_data['author_url'] = "N/A"
        else:
            article_data['author'] = "N/A"
            article_data['author_url'] = "N/A"
        
        return article_data
        
    except Exception as e:
        print(f"Error parsing 'element row-element' article: {e}")
        return None

def display_articles(articles):
    """
    Display the scraped articles in a readable format.
    """
    if not articles:
        print("No articles found.")
        return
    
    for i, article in enumerate(articles, 1):
        print(f"\nArticle {i}:")
        print(f"Category: {article['category']} ({article['category_url']})")
        print(f"Title: {article['title']}")
        print(f"URL: {article['article_url']}")
        print(f"Author: {article['author']} ({article['author_url']})")
        print("-" * 50)