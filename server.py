from fastapi import FastAPI, HTTPException
from wiki_fetcher import get_tournament_data
from parser import parse_tournament_data
import os

app = FastAPI()

@app.get('/tournament')
def tournament_endpoint(game: str, tournament_name: str):
    """
    API endpoint to fetch tournament data using FastAPI.
    Requires 'game' and 'tournament_name' as query parameters.
    """
    if not game or not tournament_name:
        raise HTTPException(status_code=400, detail="Missing 'game' or 'tournament_name' parameter")

    raw_data = get_tournament_data(game, tournament_name)

    if raw_data:
        if "content" in raw_data:
            # Parse the wikitext to get structured data
            structured_data = parse_tournament_data(raw_data['content'])

            # Define a single filename for the latest wikitext
            wikitext_filename = "latest_tournament.wikitext"
            
            # Save the raw wikitext to the file, overwriting if it exists
            with open(wikitext_filename, 'w', encoding='utf-8') as f:
                f.write(raw_data['content'])

            return {
                "title": raw_data['title'],
                "pageid": raw_data['pageid'],
                "wikitext_file": wikitext_filename,
                "structured_data": structured_data
            }
        else:
            raise HTTPException(status_code=404, detail=raw_data.get("error", "Not Found"))
    else:
        raise HTTPException(status_code=500, detail="Failed to fetch data from Liquipedia")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
