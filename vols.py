from amadeus import Client, ResponseError
import requests

client_id='tiws0QnE2yKrC8ZFQFDBGpXAm59YM03a',
client_secret='IleXqznvvqkdY3Fg'

def tt_():
    amadeus = Client(
        client_id='unpxBTR8p85VmUisxPjTSf1jnab4YX60',
        client_secret='U44l1pZNzCmiRv8A'
    )
    try:
        '''
        Find the cheapest flights from SYD to BKK
        '''
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode='SYD', destinationLocationCode='BKK', departureDate='2025-09-01', adults=1)
        print(response.data)
    except ResponseError as error:
        raise error

token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"

data = {
    "grant_type": "client_credentials",
    "client_id": client_id,
    "client_secret": client_secret
}

re = requests.post(token_url, data=data)
t = re.json()["access_token"]
def token():
    return t