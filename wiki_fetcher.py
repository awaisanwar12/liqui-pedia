import requests
import json
from parser import parse_tournament_data


def get_api_url(game):
    """Constructs the API URL for a given game on Liquipedia."""
    return f"https://liquipedia.net/{game}/api.php"

def search_tournament(api_url, tournament_name):
    """
    Searches for a tournament on a MediaWiki site.
    """
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": tournament_name,
        "formatversion": 2 # For a cleaner JSON output
    }

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("query", {}).get("search", [])
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return None

def get_page_content(api_url, page_title):
    """
    Fetches the content of a specific wiki page.
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": page_title,
        "prop": "revisions",
        "rvprop": "content",
        "formatversion": 2 # For a cleaner JSON output
    }

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        # The content is nested within the page data
        page = data.get("query", {}).get("pages", [{}])[0]
        if "revisions" in page:
            return page["revisions"][0]["content"]
        else:
            return "Page content not found."
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return None

def get_tournament_data(game, tournament_name):
    """
    Fetches and returns the data for a given tournament.
    """
    api_url = get_api_url(game)
    results = search_tournament(api_url, tournament_name)

    if results:
        target_page = results[0]
        content = get_page_content(api_url, target_page['title'])
        if content:
            return {
                "title": target_page['title'],
                "pageid": target_page['pageid'],
                "content": content
            }
        else:
            return {"error": "Could not retrieve page content."}
    else:
        return {"error": "No results found."}

def main():
    """
    Main function to orchestrate fetching tournament data.
    """
    # You can change these values to fetch data for any tournament on Liquipedia
    game = "valorant"
    tournament_to_find = "VCT/2025/Game_Changers/Latin_America_North/Main_Event"

    print(f"Searching for '{tournament_to_find}' on {game} Liquipedia...")
    data = get_tournament_data(game, tournament_to_find)

    if data and "content" in data:
        # Saving the content to a file
        filename = f"{data['title'].replace('/', '_')}.wikitext"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(data['content'])
        print(f"Successfully saved page content to '{filename}'")
        parsed_data = parse_tournament_data(data['content'])
        print("\nParsed Tournament Data:")
        print(json.dumps(parsed_data, indent=4))
    elif data:
        print(data["error"])
    else:
        print("An unknown error occurred.")


if __name__ == "__main__":
    main()
