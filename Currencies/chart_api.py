"""
Chart-specific API endpoints for real-time data
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import engine, Currencies
from database.prices import Price
from security.validators import SecurityUtils
from utils.error_handlers import handle_api_errors, ValidationError
from utils.logging_config import get_logger

logger = get_logger(__file__)

chart_bp = Blueprint('chart_api', __name__)

@chart_bp.route('/chart-data', methods=['POST'])
@SecurityUtils.rate_limit(requests=200, window=60)  # بیشتر برای چارت
@handle_api_errors
def get_chart_data():
    """
    Get optimized data for charts with different time ranges
    ---
    tags:
      - Charts
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              Symbol:
                type: string
                description: Cryptocurrency symbol (e.g., BTC)
              FiatCurrency:
                type: string
                description: Fiat currency (default USD)
              timeframe:
                type: string
                description: Chart timeframe (1h, 1d, 1w, 1m, 3m, 1y)
                enum: [1h, 1d, 1w, 1m, 3m, 6m, 1y]
              points:
                type: integer
                description: Maximum number of data points (default 100)
    responses:
      200:
        description: Chart data retrieved successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                success:
                  type: boolean
                chart_data:
                  type: object
                  properties:
                    symbol:
                      type: string
                    fiat:
                      type: string
                    timeframe:
                      type: string
                    data:
                      type: array
                      items:
                        type: object
                        properties:
                          timestamp:
                            type: string
                            format: date-time
                          price:
                            type: number
                          market_cap:
                            type: number
                          volume_24h:
                            type: number
                          change_1h:
                            type: number
                          change_24h:
                            type: number
                          change_7d:
                            type: number
                points_count:
                  type: integer
                timeframe:
                  type: string
                last_updated:
                  type: string
                  format: date-time
    """
    try:
        data = request.get_json() or {}
        
        # Validate input
        symbol = data.get('Symbol')
        if not symbol:
            raise ValidationError("Symbol is required")
        
        fiat = data.get('FiatCurrency', 'USD')
        timeframe = data.get('timeframe', '1d')
        max_points = data.get('points', 100)
        
        # Validate timeframe
        valid_timeframes = ['1h', '1d', '1w', '1m', '3m', '6m', '1y']
        if timeframe not in valid_timeframes:
            raise ValidationError(f"Invalid timeframe. Use: {', '.join(valid_timeframes)}")
        
        logger.info(f"Chart data request: {symbol}-{fiat} for {timeframe}")
        
        # Get currency ID
        session = Session(bind=engine)
        try:
            currency = session.query(Currencies).filter(
                (Currencies.Symbol == symbol) | (Currencies.CurrencyName == symbol)
            ).first()
            
            if not currency:
                raise ValidationError(f"Currency {symbol} not found")
            
            currency_id = str(currency.CurrencyID)
            
        finally:
            session.close()
        
        # Calculate time range based on timeframe
        end_time = datetime.now()
        time_ranges = {
            '1h': timedelta(hours=24),      # Last 24 hours for 1h chart
            '1d': timedelta(days=30),       # Last 30 days for 1d chart
            '1w': timedelta(days=90),       # Last 3 months for 1w chart
            '1m': timedelta(days=365),      # Last year for 1m chart
            '3m': timedelta(days=1095),     # Last 3 years for 3m chart
            '6m': timedelta(days=1825),     # Last 5 years for 6m chart
            '1y': timedelta(days=3650)      # Last 10 years for 1y chart
        }
        
        start_time = end_time - time_ranges.get(timeframe, timedelta(days=30))
        
        # Get data from database
        session = Session(bind=engine)
        try:
            # Strategy: Get both current and historical data
            query = session.query(Price).filter(
                Price.crypto_id == currency_id,
                Price.currency == fiat
            )
            
            # For short timeframes, include current prices
            if timeframe in ['1h', '1d']:
                # Get recent data (including current prices)
                query = query.filter(Price.last_updated >= start_time)
                query = query.order_by(Price.last_updated.desc())
            else:
                # For longer timeframes, use historical data
                query = query.filter(
                    Price.is_historical == True,
                    Price.timestamp >= start_time
                )
                query = query.order_by(Price.timestamp.desc())
            
            # Limit results and get data
            records = query.limit(max_points * 2).all()  # Get extra for sampling
            
            logger.info(f"Found {len(records)} records for {symbol}-{fiat} {timeframe}")
            
            if not records:
                # No data found, try to fetch fresh data
                logger.info(f"No data found for {symbol}, attempting fresh fetch")
                
                from Currencies.historical_data_service import HistoricalDataService
                service = HistoricalDataService()
                
                fetch_result = service.store_historical_data(
                    currency_ids=[currency.CurrencyID],
                    time_start=start_time.isoformat() + "Z",
                    time_end=end_time.isoformat() + "Z",
                    interval='daily' if timeframe not in ['1h'] else '1h',
                    fiat_currencies=[fiat]
                )
                
                if fetch_result.get('success'):
                    # Retry query after fetch
                    records = query.limit(max_points).all()
                    logger.info(f"After fresh fetch: {len(records)} records")
            
            # Sample data if too many points
            if len(records) > max_points:
                # Sample evenly across time range
                step = len(records) // max_points
                records = records[::step][:max_points]
                logger.debug(f"Sampled down to {len(records)} points")
            
            # Format data for chart
            chart_data = {
                'symbol': symbol,
                'fiat': fiat,
                'timeframe': timeframe,
                'data': []
            }
            
            for record in reversed(records):  # Chronological order
                timestamp = record.timestamp if record.is_historical else record.last_updated
                chart_data['data'].append({
                    'timestamp': timestamp.isoformat() if timestamp else None,
                    'price': float(record.price),
                    'market_cap': float(record.market_cap) if record.market_cap else None,
                    'volume_24h': float(record.volume_24h) if record.volume_24h else None,
                    'change_1h': float(record.change_1h) if record.change_1h else None,
                    'change_24h': float(record.change_24h) if record.change_24h else None,
                    'change_7d': float(record.change_7d) if record.change_7d else None
                })
            
            logger.info(f"Returning {len(chart_data['data'])} chart points for {symbol}-{fiat}")
            
            return jsonify({
                'success': True,
                'chart_data': chart_data,
                'points_count': len(chart_data['data']),
                'timeframe': timeframe,
                'last_updated': datetime.now().isoformat()
            }), 200
            
        finally:
            session.close()
            
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error_type': 'validation_error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error in chart data: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'internal_error',
            'message': str(e)
        }), 500

@chart_bp.route('/chart-live-update', methods=['POST'])
@SecurityUtils.rate_limit(requests=500, window=60)  # بیشتر برای live updates
@handle_api_errors
def get_live_chart_update():
    """
    Get live price update for charts (current price and market data)
    ---
    tags:
      - Charts
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              Symbol:
                type: array
                items:
                  type: string
                description: List of cryptocurrency symbols
              FiatCurrency:
                type: string
                description: Fiat currency (default USD)
    responses:
      200:
        description: Live market data retrieved successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                success:
                  type: boolean
                live_prices:
                  type: object
                  additionalProperties:
                    type: object
                    properties:
                      price:
                        type: number
                      market_cap:
                        type: number
                      volume_24h:
                        type: number
                      change_1h:
                        type: number
                      change_24h:
                        type: number
                      change_7d:
                        type: number
                      last_updated:
                        type: string
                        format: date-time
                fiat_currency:
                  type: string
                timestamp:
                  type: string
                  format: date-time
    """
    try:
        data = request.get_json() or {}
        symbols = data.get('Symbol', [])
        
        if isinstance(symbols, str):
            symbols = [symbols]
        
        if not symbols:
            raise ValidationError("At least one Symbol is required")
        
        fiat = data.get('FiatCurrency', 'USD')
        
        # Get current prices from database
        session = Session(bind=engine)
        try:
            results = {}
            
            for symbol in symbols:
                currency = session.query(Currencies).filter(
                    (Currencies.Symbol == symbol) | (Currencies.CurrencyName == symbol)
                ).first()
                
                if currency:
                    # Get latest price (current, not historical)
                    latest_price = session.query(Price).filter(
                        Price.crypto_id == str(currency.CurrencyID),
                        Price.currency == fiat,
                        Price.is_historical == False
                    ).first()
                    
                    if latest_price:
                        results[symbol] = {
                            'price': float(latest_price.price),
                            'market_cap': float(latest_price.market_cap) if latest_price.market_cap else None,
                            'volume_24h': float(latest_price.volume_24h) if latest_price.volume_24h else None,
                            'change_1h': float(latest_price.change_1h) if latest_price.change_1h else None,
                            'change_24h': float(latest_price.change_24h) if latest_price.change_24h else None,
                            'change_7d': float(latest_price.change_7d) if latest_price.change_7d else None,
                            'last_updated': latest_price.last_updated.isoformat() if latest_price.last_updated else None
                        }
                    else:
                        results[symbol] = None
                else:
                    results[symbol] = None
            
            return jsonify({
                'success': True,
                'live_prices': results,
                'fiat_currency': fiat,
                'timestamp': datetime.now().isoformat()
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error in live chart update: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'internal_error',
            'message': str(e)
        }), 500
