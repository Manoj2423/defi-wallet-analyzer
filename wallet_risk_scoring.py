import pandas as pd
import numpy
import requests
from tqdm import tqdm
import time
import os
import sys
from typing import Dict, List, Optional
import logging
from datetime import datetime

# === Setup Logging ===
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f'risk_scoring_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# === Config ===
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(CURRENT_DIR, "Wallet id - Sheet1.csv")
OUTPUT_CSV = os.path.join(CURRENT_DIR, "wallet_risk_scores.csv")  
FINAL_CSV = os.path.join(CURRENT_DIR, "final_results.csv") 

# Covalent API Configuration
COVALENT_API_KEY = ""  # Replace with your actual API key
CHAIN_ID = 1  # Ethereum Mainnet 

# === Load Wallets ===
try:
    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")
    
    wallet_df = pd.read_csv(INPUT_CSV)
    if 'wallet_id' not in wallet_df.columns:
        raise ValueError("CSV file must contain a 'wallet_id' column")
    
    # Clean and validate wallet addresses
    wallet_df['wallet_id'] = wallet_df['wallet_id'].str.strip().str.lower()
    wallet_addresses = wallet_df["wallet_id"].dropna().unique().tolist()
    
    if not wallet_addresses:
        raise ValueError("No valid wallet addresses found in the input file")
        
    logger.info(f"Loaded {len(wallet_addresses)} unique wallet addresses")
    
except Exception as e:
    logger.error(f"Failed to load wallet addresses: {str(e)}")
    sys.exit(1)

# === Fetch Wallet Data ===
def fetch_wallet_data(address: str, retries: int = 3) -> Optional[Dict]:
    """
    Fetch wallet balance data from Covalent API with retries
    """
    url = f"https://api.covalenthq.com/v1/{CHAIN_ID}/address/{address}/balances_v2/"
    params = {"key": COVALENT_API_KEY}
    
    for attempt in range(retries):
        try:
            logger.debug(f"Fetching data for {address}, attempt {attempt + 1}")
            
            response = requests.get(
                url,
                params=params,
                timeout=15,
                headers={'User-Agent': 'WalletRiskScorer/1.0'}
            )
            
            if response.status_code == 429:
                logger.warning(f"Rate limit hit for {url}, waiting longer...")
                time.sleep(10 * (attempt + 1))
                continue
            
            response.raise_for_status()
            data = response.json()
            
            if not data or 'errors' in data:
                logger.warning(f"API returned errors for {address}: {data.get('errors', 'No data')}")
                continue
            
            if 'data' in data:
                return data
            
            logger.warning(f"No data found for {address}")
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout for {address} from {url} on attempt {attempt + 1}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {address} on {url}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error for {address}: {str(e)}")
        
        # Exponential backoff
        if attempt < retries - 1:
            sleep_time = min(2 ** attempt, 30)  # Cap at 30 seconds
            logger.debug(f"Waiting {sleep_time} seconds before retry...")
            time.sleep(sleep_time)
    
    logger.error(f"Failed to fetch data for {address} after all attempts")
    return None

# === Extract Features ===
def extract_features(data: Dict) -> Dict:
    """
    Extract and validate features from Covalent API response data
    """
    try:
        # Initialize features
        features = {
            "total_usd": 0,
            "num_assets": 0,
            "largest_holding_usd": 0,
            "portfolio_concentration": 0
        }
        
        # Get token balances
        items = data.get("data", {}).get("items", [])
        if not items:
            return features
            
        # Calculate total portfolio value and count assets
        valid_holdings = []
        for item in items:
            try:
                # Handle potential None values and ensure numeric conversion
                quote_raw = item.get("quote")
                if quote_raw is None:
                    continue
                    
                
                try:
                    quote = float(quote_raw)
                except (ValueError, TypeError):
                    continue
                    
                if quote > 0:
                    token_symbol = item.get("contract_ticker_symbol", "UNKNOWN")
                    logger.debug(f"Processing token {token_symbol} with value ${quote:,.2f}")
                    valid_holdings.append(quote)
                    features["total_usd"] += quote
                    features["num_assets"] += 1
                    features["largest_holding_usd"] = max(features["largest_holding_usd"], quote)
            except Exception as e:
                logger.warning(f"Error processing token balance for {item.get('contract_ticker_symbol', 'UNKNOWN')}: {str(e)}")
                continue
                
        # Calculate portfolio concentration (largest holding as % of total)
        if features["total_usd"] > 0:
            features["portfolio_concentration"] = features["largest_holding_usd"] / features["total_usd"]
        
        return features
        
    except Exception as e:
        logger.error(f"Failed to extract features: {str(e)}")
        return {
            "total_usd": 0,
            "num_assets": 0,
            "largest_holding_usd": 0,
            "portfolio_concentration": 0
        }

# === Risk Scoring Model ===
def normalize_portfolio_size(usd_value: float) -> float:
    """
    Normalize portfolio size on a scale of 0-1
    Using log scale to handle large variations in portfolio sizes
    0 = highest risk (small portfolio)
    1 = lowest risk (large portfolio)
    """
    if usd_value <= 0:
        return 0
    
    # Using log scale with thresholds
    MIN_PORTFOLIO = 100      # $100 or less is highest risk
    MAX_PORTFOLIO = 1000000  # $1M or more is lowest risk
    
    log_value = numpy.log10(max(usd_value, 1))
    log_min = numpy.log10(MIN_PORTFOLIO)
    log_max = numpy.log10(MAX_PORTFOLIO)
    
    normalized = (log_value - log_min) / (log_max - log_min)
    return min(max(normalized, 0), 1)

def normalize_diversification(num_assets: int) -> float:
    """
    Normalize diversification score on a scale of 0-1
    0 = highest risk (1 asset)
    1 = lowest risk (15+ assets)
    """
    if num_assets <= 1:
        return 0
    elif num_assets >= 15:
        return 1
    else:
        return (num_assets - 1) / 14

def normalize_concentration(concentration: float) -> float:
    """
    Normalize concentration score on a scale of 0-1
    0 = highest risk (100% in one asset)
    1 = lowest risk (evenly distributed)
    """
    if concentration >= 1:
        return 0
    elif concentration <= 0.1:  # No single asset > 10% of portfolio
        return 1
    else:
        return 1 - concentration

def compute_score(features):
    """
    Calculate risk score from 0-1000 using a weighted combination of normalized features:
    
    Features and Weights:
    1. Portfolio Size (35%):
       - Larger portfolios = lower risk
       - Log-scaled to handle large variations
       - Thresholds: $100 (high risk) to $1M (low risk)
    
    2. Asset Diversification (35%):
       - More unique assets = lower risk
       - Linear scale from 1 to 15 assets
       - 15+ assets considered optimal diversification
    
    3. Concentration Risk (30%):
       - Higher concentration in single asset = higher risk
       - Linear scale based on largest holding percentage
       - <10% in any asset considered optimal
    
    Risk Score Ranges:
    - 0-200: Very Low Risk (Large, well-diversified portfolio)
    - 201-400: Low Risk
    - 401-600: Medium Risk
    - 601-800: High Risk
    - 801-1000: Very High Risk (Small, concentrated portfolio)
    """
    # 1. Normalize individual risk factors (0-1 scale, 0=highest risk, 1=lowest risk)
    size_score = normalize_portfolio_size(features["total_usd"])
    diversity_score = normalize_diversification(features["num_assets"])
    concentration_score = normalize_concentration(features["portfolio_concentration"])
    
    # 2. Apply weights to each factor
    weighted_score = (
        size_score * 0.35 +           # Portfolio Size: 35%
        diversity_score * 0.35 +      # Asset Diversification: 35%
        concentration_score * 0.30     # Concentration Risk: 30%
    )
    
    # 3. Convert to 0-1000 scale and invert (0=lowest risk, 1000=highest risk)
    final_score = round((1 - weighted_score) * 1000)
    
    # 4. Handle edge cases
    if features["total_usd"] == 0:
        final_score = 800  # Empty portfolios are high risk
    
    return max(0, min(1000, final_score))  # Ensure score stays within bounds
    
    # Ensure score stays within bounds
    return max(0, min(1000, round(score)))

# === Main Processing ===
def main():
    results = []
    failed_addresses = []
    start_time = datetime.now()
    
    logger.info("Starting risk analysis process...")
    
    try:
        # Create backup of existing output file if it exists
        if os.path.exists(OUTPUT_CSV):
            backup_file = f"{OUTPUT_CSV}.backup_{start_time.strftime('%Y%m%d_%H%M%S')}"
            os.rename(OUTPUT_CSV, backup_file)
            logger.info(f"Created backup of existing output file: {backup_file}")
        
        # Process wallets with progress bar
        with tqdm(wallet_addresses, desc="Scoring wallets") as pbar:
            for addr in pbar:
                try:
                    # Update progress bar description
                    pbar.set_description(f"Processing {addr[:8]}...")
                    
                    # Fetch and process data
                    data = fetch_wallet_data(addr)
                    if not data:
                        failed_addresses.append((addr, "Failed to fetch data"))
                        results.append({"wallet_id": addr, "score": 0})
                        continue
                    
                    # Extract features and compute score
                    features = extract_features(data)
                    score = compute_score(features)
                    
                    # Save only wallet_id and score
                    results.append({
                        "wallet_id": addr,
                        "score": score
                    })
                    
                    # Politeness delay with jitter
                    time.sleep(0.2 + random.random() * 0.3)
                    
                except Exception as e:
                    logger.error(f"Error processing wallet {addr}: {str(e)}")
                    failed_addresses.append((addr, str(e)))
                    results.append({"wallet_id": addr, "score": 0})
                    continue
        
        # Save full results
        output_df = pd.DataFrame(results)
        output_df.to_csv(OUTPUT_CSV, index=False)
        
        # Save simplified final results (only wallet_id and score)
        final_df = pd.DataFrame(results)[['wallet_id', 'score']]
        final_df.to_csv(FINAL_CSV, index=False)
        
        # Generate summary statistics
        successful = len(results) - len(failed_addresses)
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info("\n=== Analysis Complete ===")
        logger.info(f"Total wallets processed: {len(results)}")
        logger.info(f"Successfully scored: {successful}")
        logger.info(f"Failed to process: {len(failed_addresses)}")
        logger.info(f"Success rate: {successful/len(results)*100:.1f}%")
        logger.info(f"Total duration: {duration:.1f} seconds")
        logger.info(f"Average time per wallet: {duration/len(results):.1f} seconds")
        
        if failed_addresses:
            logger.warning("\nFailed addresses:")
            for addr, reason in failed_addresses[:5]:
                logger.warning(f"- {addr}: {reason}")
            if len(failed_addresses) > 5:
                logger.warning(f"... and {len(failed_addresses) - 5} more")
        
        logger.info(f"\n✅ Full results saved to {OUTPUT_CSV}")
        logger.info(f"✅ Final results (wallet_id and score only) saved to {FINAL_CSV}")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        if results:  # Save partial results if available
            try:
                partial_output = f"{OUTPUT_CSV}.partial_{start_time.strftime('%Y%m%d_%H%M%S')}"
                pd.DataFrame(results).to_csv(partial_output, index=False)
                logger.info(f"Partial results saved to {partial_output}")
            except Exception as save_error:
                logger.error(f"Failed to save partial results: {str(save_error)}")
        raise

if __name__ == "__main__":
    try:
        import random  # For jitter in delays
        main()
    except KeyboardInterrupt:
        logger.warning("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Program failed: {str(e)}")
        sys.exit(1)
