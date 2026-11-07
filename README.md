Global airline routes data
==========================

This is a single JSON file that describes every passenger airport and their outbound airline routes, automatically updated weekly.

The file is indexed by IATA airport code. Routes specify the destination airport IATA code, flight time in minutes, and distance in kilometers.

You probably want to look at [airline_routes.json](airline_routes.json).

Running and troubleshooting updates
-----------------------------------
Run the scraper with Python 3.10 and the dependencies in `requirements.txt`:

```sh
uv run --python 3.10 --with-requirements requirements.txt -- python -u scrape_airline_routes.py
```

Run the regression tests with the same environment:

```sh
uv run --python 3.10 --with-requirements requirements.txt -- python -m unittest discover -v
```

The scraper reads FlightsFrom's airport directory and `/api/airport/IATA?from=IATA`
JSON endpoint; destination HTML pages no longer embed the old `window.airport` data.

FlightsFrom may return a Cloudflare JavaScript challenge instead of data, particularly
from GitHub-hosted runner IPs. The scraper reuses a browser-impersonating HTTP session
and retries transient failures three times, but it cannot solve JavaScript challenges.
Persistent blocks fail the update without replacing the existing dataset.

If GitHub-hosted requests remain blocked, use a runner with an IP permitted by the
source site, or configure an authorized HTTP/SOCKS proxy. For the latter, add a
repository Actions secret named `FLIGHTSFROM_PROXY` containing its full proxy URL
(for example, `http://user:password@proxy.example.com:8080`). Locally, set the same
environment variable. Keep proxy credentials out of source control. Proxy requests
pass through the proxy operator and may incur charges; use a trusted provider and
ensure automated access is permitted by the source site.

A nice map of the data
----------------------
<img src="https://raw.githubusercontent.com/Jonty/airline-route-data/master/map.png">

Example entry
-------------
```JSON
{
    "LHR": {
        "city_name": "London",
        "continent": "EU",
        "country": "United Kingdom",
        "country_code": "GB",
        "display_name": "London (LHR), United Kingdom",
        "elevation": 80,
        "iata": "LHR",
        "icao": "EGLL",
        "latitude": "51.469603",
        "longitude": "-0.453566",
        "name": "Heathrow",
        "routes": [
            {
                "carriers": [
                    {
                        "iata": "BA",
                        "name": "British Airways"
                    },
                    {
                        "iata": "KL",
                        "name": "KLM"
                    }
                ],
                "iata": "AMS",
                "km": 371,
                "min": 80
            },
            {
                "carriers": [
                    {
                        "iata": "BA",
                        "name": "British Airways"
                    },
                    {
                        "iata": "LH",
                        "name": "Lufthansa"
                    }
                ],
                "iata": "MUC",
                "km": 943,
                "min": 115
            },
            {
                "carriers": [
                    {
                        "iata": "AF",
                        "name": "Air France"
                    },
                    {
                        "iata": "BA",
                        "name": "British Airways"
                    }
                ],
                "iata": "CDG",
                "km": 348,
                "min": 80
            },
            ...
        ],
        "timezone": "Europe/London"
    }
}
```
