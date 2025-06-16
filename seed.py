from supabase import create_client, Client

url = "https://dfhuqxvvyajbsawmmlzb.supabase.co"  # your project URL
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRmaHVxeHZ2eWFqYnNhd21tbHpiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk5OTkzODgsImV4cCI6MjA2NTU3NTM4OH0.BRcyjG1pyVHvHogImc6atbICfAFddQ7KCM6VUniLVUU"  # the anon/public API key from your settings

supabase: Client = create_client(url, key)


# seed the prices table
starting_price = 300
tickers = ['ANGL', 'ARYE', 'DANL', 'DRNC', 'ELLI', 'FRDY', 'JIN', 'RCHL']

for ticker in tickers:
    supabase.table("prices").insert({
        "ticker": ticker,
        "price": starting_price,
        "original_price": starting_price
    }).execute()