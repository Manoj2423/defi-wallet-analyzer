# Wallet Risk Scoring System

## Overview
This system analyzes cryptocurrency wallet behavior and assigns risk scores from 0-1000, where lower scores indicate lower risk. The system is designed to be scalable, robust, and provide meaningful risk assessments based on wallet activity and portfolio characteristics.

## Getting Started

### Prerequisites
- Python 3.7 or higher
- Covalent API key (get it from [Covalent](https://www.covalenthq.com/platform/auth/register/))

### Setup
1. Clone this repository
2. Create a `.env` file in the project root and add your Covalent API key:
   ```
   COVALENT_API_KEY=your_api_key_here
   ```

### Running the Project
1. Add wallet addresses to analyze in `wallet_risk_scoring.py` under the `WALLETS` list
2. Run the script:
   ```bash
   python wallet_risk_scoring.py
   ```
3. The output will be saved in `final_results.csv` containing wallet IDs and their risk scores

## 1. Data Collection Method

### API Integration
- **Primary Source**: Covalent API
- **Endpoints**: `/v1/{chain_id}/address/{address}/balances_v2/`
- **Chain Coverage**: Support for multiple chains (Ethereum, Polygon, BSC)
- **Data Points**: Token balances, USD values, contract details

### Reliability Features
- Implements exponential backoff for rate limiting
- Multiple retry attempts (3x) for failed requests
- Error handling and logging for failed requests
- Backup data persistence for interrupted processes

## 2. Feature Selection Rationale

### Core Features Selected

1. **Portfolio Total Value (USD)**
   - *Rationale*: Larger portfolios typically indicate more established, sophisticated users
   - *Implementation*: Log-scaled to handle wide value ranges
   - *Risk Indication*: Lower risk for larger portfolios

2. **Asset Diversification (Number of Assets)**
   - *Rationale*: Diversification reduces single-asset risk exposure
   - *Implementation*: Linear scale from 1 to 15+ assets
   - *Risk Indication*: More assets = lower risk

3. **Portfolio Concentration**
   - *Rationale*: Heavy concentration in single assets increases risk
   - *Implementation*: Ratio of largest holding to total portfolio
   - *Risk Indication*: Higher concentration = higher risk

### Feature Weighting
- Portfolio Size: 35%
- Asset Diversification: 35%
- Concentration Risk: 30%

## 3. Scoring Method

### Score Calculation Process

1. **Feature Normalization**
   - Each feature normalized to 0-1 scale
   - 0 = highest risk
   - 1 = lowest risk

2. **Portfolio Size Normalization**
   ```python
   if value <= $100: highest risk (0)
   if value >= $1M: lowest risk (1)
   else: log-scaled between 0-1
   ```

3. **Diversification Normalization**
   ```python
   if assets <= 1: highest risk (0)
   if assets >= 15: lowest risk (1)
   else: linear scale between 0-1
   ```

4. **Concentration Normalization**
   ```python
   if concentration >= 100%: highest risk (0)
   if concentration <= 10%: lowest risk (1)
   else: linear inverse scale
   ```

### Risk Score Ranges
- 0-200: Very Low Risk
- 201-400: Low Risk
- 401-600: Medium Risk
- 601-800: High Risk
- 801-1000: Very High Risk

## 4. Risk Indicator Justification

### Portfolio Size (35% weight)
- **Justification**: Larger portfolios indicate:
  - More financial resources
  - Greater ability to absorb losses
  - More likely to be institutional/sophisticated
- **Scale**: Logarithmic to account for exponential differences
- **Thresholds**: Based on typical retail vs institutional holdings

### Asset Diversification (35% weight)
- **Justification**: Multiple assets provide:
  - Risk distribution
  - Protection against single asset failure
  - Market sector coverage
- **Scale**: Linear up to 15 assets
- **Basis**: Modern Portfolio Theory principles

### Concentration Risk (30% weight)
- **Justification**: High concentration indicates:
  - Increased vulnerability to single asset volatility
  - Potential liquidity risks
  - Less resilience to market shocks
- **Optimal**: No single asset > 10% of portfolio
- **Based on**: Standard portfolio management practices

## 5. System Scalability

### Technical Scalability
- Modular code structure
- Configurable parameters
- Multi-chain support
- Parallel processing capability
- Efficient data caching

### Analytical Scalability
- Framework adaptable to new features
- Configurable risk weights
- Adjustable thresholds
- Extensible scoring model

### Data Management
- Automated backup systems
- Progress tracking
- Failure recovery
- Detailed logging

## 6. Limitations and Considerations

- Limited to on-chain data
- Point-in-time analysis
- No historical trend analysis
- Does not account for:
  - Smart contract risks
  - Network-specific risks
  - Off-chain assets
  - Trading behavior

## 7. Future Improvements

1. Historical data analysis
2. Transaction pattern analysis
3. Smart contract risk assessment
4. Cross-chain activity correlation
5. DeFi protocol interaction analysis
6. Machine learning-based risk prediction
