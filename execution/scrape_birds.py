import os
import json
import time
import requests
from bs4 import BeautifulSoup
from googletrans import Translator

# List of 100 common birds (based on search result)
BIRD_LIST = [
    "Turkey Vulture", "Dunlin", "Western Sandpiper", "Mallard", "Great Blue Heron",
    "Spotted Towhee", "Snow Goose", "Wood Duck", "Gadwall", "American Wigeon",
    "Northern Shoveler", "Northern Pintail", "Green-Winged Teal", "Hooded Merganser", "Bald Eagle",
    "American Coot", "Sandhill Crane", "Greater Yellowlegs", "Long-Billed Dowitcher", "Barred Owl",
    "Black-Capped Chickadee", "Red-Winged Blackbird", "Bufflehead", "American Robin", "Brant",
    "Sanderling", "Northwestern Crow", "Golden-Crowned Sparrow", "Wilson's Snipe", "Varied Thrush",
    "Dark-Eyed Junco", "Song Sparrow", "House Finch", "Northern Flicker", "Downy Woodpecker",
    "Bushtit", "Fox Sparrow", "White-Crowned Sparrow", "Chestnut-Backed Chickadee", "House Sparrow",
    "Canada Goose", "Osprey", "Anna's Hummingbird", "Ruby-Crowned Kinglet", "Yellow-Rumped Warbler",
    "Eurasian Collared Dove", "Lesser Scaup", "Red-tailed Hawk", "Rock Pigeon", "Rufous Hummingbird",
    "Tree Swallow", "Barn Swallow", "Marsh Wren", "Savannah Sparrow", "Brown-Headed Cowbird",
    "Cinnamon Teal", "European Starling", "Double-Crested Cormorant", "American Goldfinch", "Glaucous-Winged Gull",
    "Belted Kingfisher", "Cedar Waxwing", "Eurasian Wigeon", "Mew Gull", "Ring-Billed Gull",
    "California Gull", "Trumpeter Swan", "Ring-Necked Duck", "Common Merganser", "Great Horned Owl",
    "Northern Saw-Whet Owl", "Merlin", "Red-Breasted Merganser", "Golden-Crowned Kinglet", "Purple Finch",
    "Horned Grebe", "Common Goldeneye", "Cooper's Hawk", "Red Crossbill", "Pine Siskin",
    "Western Gull", "Black-Crowned Night Heron", "Northern Harrier", "Brewer's Blackbird", "Common Loon",
    "Surf Scoter", "Black Oystercatcher", "Long-Tailed Duck", "Barrow's Goldeneye", "Pied-Billed Grebe",
    "Common Raven", "Brown Creeper", "Black Turnstone", "Ring-Necked Pheasant", "Rough-Legged Hawk",
    "Peregrine Falcon", "Sharp-Shinned Hawk", "Pileated Woodpecker", "Red-Breasted Nuthatch", "Mute Swan"
]

# Mapping rules for categories
CATEGORY_MAP = {
    'Predator': ['Hawk', 'Eagle', 'Falcon', 'Owl', 'Vulture', 'Merlin', 'Harrier', 'Osprey'],
    'Water Bird': ['Heron', 'Duck', 'Goose', 'Teal', 'Merganser', 'Coot', 'Crane', 'Grebe', 'Gull', 'Swan', 'Loon', 'Scoter', 'Oystercatcher', 'Turnstone', 'Mew', 'Dunlin', 'Sandpiper', 'Yellowlegs', 'Dowitcher', 'Snipe', 'Brant', 'Sanderling', 'Cormorant', 'Scaup', 'Bufflehead', 'Wigeon', 'Shoveler', 'Pintail', 'Gadwall', 'Goldeneye'],
    'Songbird': ['Sparrow', 'Chickadee', 'Blackbird', 'Robin', 'Finch', 'Junco', 'Thrush', 'Bushtit', 'Kinglet', 'Warbler', 'Swallow', 'Wren', 'Cowbird', 'Goldfinch', 'Waxwing', 'Nuthatch', 'Starling', 'Siskin', 'Crossbill', 'Creeper', 'Towhee'],
    'Other': ['Woodpecker', 'Dove', 'Hummingbird', 'Kingfisher', 'Pheasant', 'Raven', 'Crow', 'Pigeon', 'Flicker']
}

# Common birds for difficulty 1
DIFFICULTY_1 = ['House Sparrow', 'Rock Pigeon', 'American Robin', 'European Starling', 'Common Raven', 'Mallard', 'Canada Goose']
# For difficulty 2
DIFFICULTY_2 = ['Bald Eagle', 'American Goldfinch', 'Downy Woodpecker', 'Barn Swallow', 'Red-tailed Hawk']

def get_category(name):
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in name for kw in keywords):
            return cat
    return 'Other'

def get_difficulty(name):
    if name in DIFFICULTY_1:
        return 1
    if name in DIFFICULTY_2:
        return 2
    if any(kw in name for kw in ['Sparrow', 'Duck', 'Gull']):
        return 2
    if any(kw in name for kw in ['Hawk', 'Owl', 'Hummingbird']):
        return 3
    if any(kw in name for kw in ['Falcon', 'Merganser', 'Warbler']):
        return 4
    return 5

# User-Agent is required by Wikipedia API policy
HEADERS = {
    'User-Agent': 'BirdQuizBot/1.0 (contact: your-email@example.com) requests/2.0'
}

def get_wikipedia_info(bird_name):
    """Fetch scientific name and image URL from Wikipedia."""
    try:
        encoded_name = requests.utils.quote(bird_name)
        # Use redirects=1 to follow redirects
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={encoded_name}&prop=pageimages|revisions&redirects=1&rvprop=content&format=json&pithumbsize=1000"
        response = requests.get(search_url, headers=HEADERS)
        
        if response.status_code != 200:
            return None, None
            
        data = response.json()
        pages = data.get('query', {}).get('pages', {})
        if not pages:
            return None, None
        
        page_id = list(pages.keys())[0]
        if page_id == "-1":
            # Try a search if direct title doesn't work
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_name}&format=json"
            search_data = requests.get(search_url, headers=HEADERS).json()
            search_results = search_data.get('query', {}).get('search', [])
            if search_results:
                best_match = search_results[0]['title']
                return get_wikipedia_info(best_match)
            return None, None
        
        page_data = pages[page_id]
        img_url = page_data.get('thumbnail', {}).get('source')
        
        # Extract scientific name
        content = page_data.get('revisions', [{}])[0].get('*', '')
        scientific_name = "Unknown"
        
        # Look for binomial in infobox
        import re
        # Try both binomial and binominal
        match = re.search(r'\|\s*bi[no]minal\s*=\s*([^|\n}]+)', content, re.I)
        if match:
            scientific_name = match.group(1).strip().replace("''", "").replace("[[", "").replace("]]", "")
        else:
            # Fallback: look for bold italics in the first paragraph
            match = re.search(r"'''''([^']+)'''''", content)
            if not match:
                match = re.search(r"''([^']+)''", content) # Just italics
            if match:
                scientific_name = match.group(1)
            
        return scientific_name, img_url
    except Exception as e:
        print(f"Error fetching info for {bird_name}: {e}")
        return None, None

def download_image(url, filename):
    try:
        response = requests.get(url, headers=HEADERS, stream=True)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return False

def main():
    assets_dir = "./assets/birds/"
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
        
    translator = Translator()
    data = []
    
    print(f"Starting to process {len(BIRD_LIST)} birds...")
    
    for i, english_name in enumerate(BIRD_LIST):
        print(f"[{i+1}/100] Processing: {english_name}")
        bird_id = f"bird_{str(i+1).zfill(3)}"
        
        # Get Wikipedia info
        sci_name, img_url = get_wikipedia_info(english_name)
        
        # Translation
        names = {"en": english_name}
        try:
            # Add a small sleep to avoid rate limiting
            time.sleep(1)
            translated_he = translator.translate(english_name, dest='he').text
            translated_es = translator.translate(english_name, dest='es').text
            names["he"] = translated_he
            names["es"] = translated_es
        except Exception as e:
            print(f"Translation error for {english_name}: {e}")
            names["he"] = english_name # Fallback
            names["es"] = english_name
            
        # Image download
        image_path = f"{assets_dir}{english_name.lower().replace(' ', '_')}.jpg"
        if img_url:
            success = download_image(img_url, image_path)
            if not success:
                image_path = ""
        else:
            image_path = ""
            
        bird_entry = {
            "id": bird_id,
            "names": names,
            "scientificName": sci_name or "Unknown",
            "category": get_category(english_name),
            "difficulty": get_difficulty(english_name),
            "imagePath": image_path
        }
        data.append(bird_entry)
        
    # Save JSON
    with open("birds_data.json", "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("Dataset generation complete!")

if __name__ == "__main__":
    main()
