import requests

WALLETS = [
    "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance hot wallet (test wallet)
    # Add more wallet addresses here
]

SUBGRAPHS = {
    "Compound V2": "https://api.thegraph.com/subgraphs/name/graphprotocol/compound-v2",
    "Compound V3": "https://api.thegraph.com/subgraphs/name/messari/compound-v3-ethereum"
}

def build_query(wallet):
    return {
        "query": f"""
        {{
            account(id: "{wallet.lower()}") {{
                id
                tokens {{
                    symbol
                    cTokenBalance
                    totalUnderlyingSupplied
                    totalUnderlyingBorrowed
                    enteredMarket
                }}
                hasBorrowed
                health
                totalBorrowValueInEth
                totalCollateralValueInEth
            }}
        }}
        """
    }

def fetch_wallet_data(wallet):
    for name, url in SUBGRAPHS.items():
        print(f"\n🔍 Checking {name} for wallet: {wallet}")
        try:
            response = requests.post(url, json=build_query(wallet))
            data = response.json()
            account_data = data.get("data", {}).get("account", {})
            
            if account_data and account_data.get("tokens"):
                print(f"✅ Found account data in {name}:")
                print(f"Health Factor: {account_data.get('health', 'N/A')}")
                print(f"Total Borrow Value (ETH): {account_data.get('totalBorrowValueInEth', '0')}")
                print(f"Total Collateral Value (ETH): {account_data.get('totalCollateralValueInEth', '0')}")
                print(f"Has Borrowed: {account_data.get('hasBorrowed', False)}")
                
                print("\nToken Positions:")
                for token in account_data["tokens"]:
                    print(f"  - {token['symbol']}")
                    print(f"    Supplied: {token['totalUnderlyingSupplied']}")
                    print(f"    Borrowed: {token['totalUnderlyingBorrowed']}")
                    print(f"    Used as Collateral: {token['enteredMarket']}")
            else:
                print("⚠️ No account data found.")
        except Exception as e:
            print(f"❌ Error: {e}")

# Run test
for wallet in WALLETS:
    fetch_wallet_data(wallet)
